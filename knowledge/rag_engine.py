"""
knowledge/rag_engine.py
=======================
Motor RAG (Retrieval-Augmented Generation) liviano para electrónica.

Usa TF-IDF (scikit-learn) para búsqueda semántica sobre:
  - Reglas de diseño IPC (ipc_2221.json)
  - Base de datos de componentes (components.json)
  - Notas de aplicación y texto libre ingresado

Ventajas vs sentence-transformers:
  - Sin descarga de modelos pesados (~400MB)
  - Funciona offline completamente
  - Suficiente para búsquedas técnicas en inglés y español

Para escalar a embeddings semánticos completos, reemplazar _vectorize()
con el modelo sentence-transformers/all-MiniLM-L6-v2.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _SKLEARN_OK = True
except ImportError:
    _SKLEARN_OK = False
    np = None

from knowledge.pulse_config import PULSE_RAG_BACKEND, cfg

# ─── Rutas ───────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "data"
_EMBED_DIR = _DATA / "embeddings"
_EMBED_MATRIX = _EMBED_DIR / "vectors.npy"
_EMBED_MANIFEST = _EMBED_DIR / "manifest.json"


# ─── Chunking ────────────────────────────────────────────────────────────────

def _text_from_dict(d: dict, prefix: str = "") -> str:
    """Convierte dict recursivamente a texto plano para indexación."""
    parts = []
    for k, v in d.items():
        if k.startswith("_"):
            continue
        key_str = f"{prefix}{k}".replace("_", " ")
        if isinstance(v, dict):
            parts.append(_text_from_dict(v, f"{key_str} "))
        elif isinstance(v, list):
            parts.append(key_str + " " + " ".join(str(i) for i in v))
        else:
            parts.append(f"{key_str} {v}")
    return " ".join(parts)


def _chunk_component(comp: dict) -> list[dict]:
    """Genera chunks buscables a partir de un componente JSON."""
    chunks = []
    text = _text_from_dict(comp)
    chunks.append({
        "text": text,
        "source": f"ComponentDB:{comp.get('id', 'unknown')}",
        "type": "component",
        "data": comp,
    })
    # Chunk adicional para los circuitos de soporte
    support = comp.get("support_circuits", {})
    if support:
        sup_text = f"{comp.get('id','')} support circuits: " + _text_from_dict(support)
        chunks.append({
            "text": sup_text,
            "source": f"ComponentDB:{comp.get('id', 'unknown')}#support",
            "type": "support_circuit",
            "data": {"id": comp.get("id"), "support_circuits": support},
        })
    return chunks


def _chunk_ipc(ipc: dict) -> list[dict]:
    """Genera chunks buscables desde el JSON IPC-2221."""
    chunks = []
    std = ipc.get("_meta", {}).get("standard", "IPC")
    for section_key, section_val in ipc.items():
        if section_key.startswith("_"):
            continue
        if isinstance(section_val, dict):
            desc = section_val.get("description", section_key.replace("_", " "))
            text = f"{std} {desc}: " + _text_from_dict(section_val)
            chunks.append({
                "text": text,
                "source": f"IPC-2221B:{section_key}",
                "type": "design_rule",
                "data": {section_key: section_val},
            })
    return chunks


def _summarize_circuit_data(data: dict) -> str:
    """Build searchable text from a training/ingested circuit dict."""
    circuit = data.get("circuit", data)
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    parts = []
    prompt = metadata.get("prompt", "")
    if prompt:
        parts.append(f"design_intent: {prompt}")
    parts.append(data.get("source") or metadata.get("source", ""))
    parts.append(data.get("original_file", ""))

    if isinstance(circuit, dict):
        if circuit.get("description"):
            parts.append(f"description: {circuit['description']}")
        if circuit.get("notes"):
            parts.append("notes: " + " | ".join(circuit["notes"][:40]))
        if circuit.get("net_labels"):
            parts.append("nets: " + " ".join(circuit["net_labels"][:60]))

        comps = circuit.get("components", [])
        if comps:
            for c in comps[:40]:
                parts.append(
                    f"{c.get('etype', '?')} {c.get('label', c.get('uid', ''))} "
                    f"{c.get('value_raw', c.get('value', ''))} {c.get('lib_id', '')}"
                )
        else:
            parts.append(_text_from_dict(circuit)[:2000])
    elif isinstance(circuit, list):
        parts.append(json.dumps(circuit)[:2000])
    return " ".join(str(p) for p in parts if p)


_DESCRIPTION_MARKERS = ("design_intent:", "description:", "notes:", "nets:")


def _text_has_description_density(text: str) -> bool:
    """True if indexed text carries design-intent/schematic context beyond a bare
    component list (etype + label + value + lib_id).

    All `circuit_example` chunk text is produced by `_summarize_circuit_data()`,
    which prefixes any real design-intent/description/notes/net-name content with
    one of these literal markers — so checking for the markers is both precise and
    sufficient (no false positives from lowercase runs inside lib_id strings like
    "antmicroResistors0402", which a generic "has a real word" heuristic would trigger on).
    """
    low = text.lower()
    return any(marker in low for marker in _DESCRIPTION_MARKERS)


def _chunk_training_sample(sample: dict, source_name: str) -> dict:
    text = _summarize_circuit_data(sample)
    return {
        "text": text,
        "source": f"Training:{source_name}",
        "type": "circuit_example",
        "data": sample,
    }


def normalize_part_name(name: str) -> str:
    """Normaliza un nombre de parte para comparación tolerante a variantes de
    formato (ej. "LM2596S-5.0" vs "LM2596S-5", "NE555" vs "NE555P").

    Usado para decidir cuándo un override de `pinouts_library.json` debe
    reemplazar (no duplicar) un chunk `pinout` ya generado desde el índice de
    símbolos KiCad real — ver `ElectronicsKnowledgeBase._load_symbol_index()`.
    Sólo colapsa separadores/mayúsculas; no resuelve el drift de nombres reales
    documentado en docs/calibration_forge/kicad_symbol_kb.md (ej. "NE555" no
    normaliza a lo mismo que "NE555P" — son partes distintas a propósito).
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())

class ElectronicsKnowledgeBase:
    """
    Base de conocimiento RAG para electrónica.

    Métodos principales:
        query(question, top_k)         — búsqueda semántica
        get_design_rules(voltage, ...)  — reglas IPC directas
        search_component(query, ...)    — búsqueda de componentes
        ingest_text(text, source, type) — añadir texto libre

    Uso::

        kb = ElectronicsKnowledgeBase()
        results = kb.query("clearance para 50V en placa sin revestir")
        comp = kb.search_component("MCU con 3 UART")
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = Path(data_dir) if data_dir else _DATA
        self._chunks: list[dict] = []
        self._vectorizer = None
        self._matrix = None
        self._fitted = False
        self._embed_matrix = None
        self._embed_client = None
        self._backend = PULSE_RAG_BACKEND
        self._load_default_data()
        self._load_embed_cache()

    # ── Ingesta ───────────────────────────────────────────────────

    def _compute_chunks_hash(self) -> str:
        """Compute SHA-256 fingerprint of current chunks for strict vector cache validation."""
        import hashlib
        h = hashlib.sha256()
        for c in self._chunks:
            h.update(c.get("text", "").encode("utf-8"))
            h.update(c.get("source", "").encode("utf-8"))
        return h.hexdigest()

    def _load_training_examples(self) -> None:
        """Load parsed KiCad training JSON as circuit_example chunks, filtering QA error test fixtures."""
        train_dir = self._data_dir / "training"
        if not train_dir.exists():
            return
        loaded = 0
        excluded_keywords = (
            "_error", "bugtest", "erc_", "noconnect", "no_connect",
            "topology_mismatch", "issue", "test_", "untitled", "test1243"
        )
        for path in sorted(train_dir.glob("*.json")):
            stem_low = path.stem.lower()
            if any(kw in stem_low for kw in excluded_keywords):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    sample = json.load(f)
                self._chunks.append(_chunk_training_sample(sample, path.stem))
                loaded += 1
            except (json.JSONDecodeError, OSError):
                continue
        if loaded:
            pass  # _fit() called by _load_default_data after this

    def _load_experiences(self) -> None:
        """Load previously recorded design experiences as design_experience chunks (Strict Gatekeeper)."""
        exp_dir = _HERE / "experiences"
        if not exp_dir.exists():
            return
        for path in sorted(exp_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    exp = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            # Strict Gatekeeper assertion
            if not exp.get("passed", False) or exp.get("drc_violations", 0) > 0:
                continue

            board_id = exp.get("board_id", path.stem)
            mcu = exp.get("mcu", "")
            for lesson in exp.get("lessons_learned", []) or []:
                clean_lesson = str(lesson).strip()
                if not clean_lesson or clean_lesson.lower().startswith("remediated issue:"):
                    continue
                self._chunks.append({
                    "text": f"Design experience {board_id} MCU {mcu}: {clean_lesson}",
                    "source": f"Experience:{board_id}",
                    "type": "design_experience",
                    "data": {"text": clean_lesson, "board_id": board_id, "mcu": mcu},
                })
            for rule in exp.get("component_placement_rules", []) or []:
                clean_rule = str(rule).strip()
                if not clean_rule:
                    continue
                self._chunks.append({
                    "text": f"Placement rule {board_id}: {clean_rule}",
                    "source": f"Experience:{board_id}#placement",
                    "type": "design_experience",
                    "data": {"text": clean_rule, "board_id": board_id, "mcu": mcu},
                })

    def _load_symbol_index(self) -> None:
        """Carga `knowledge/data/symbols_index.json` (construido por
        `python -m knowledge.build_symbol_index` desde una instalación real de
        KiCad, ver docs/calibration_forge/kicad_symbol_kb.md) como chunks
        `chunk_type="pinout"`, uno por símbolo con pines conocidos.

        Después carga `knowledge/pinouts_library.json` (datos curados a mano)
        también como chunks `pinout`, pero con prioridad: si el nombre de parte
        normalizado (`normalize_part_name`) ya tiene un chunk generado desde el
        índice KiCad, el override lo REEMPLAZA en vez de duplicarlo — así
        `_match_pinouts()`/`kb.query(chunk_type="pinout")` no necesitan lógica
        especial de prioridad, el override ya "gana" por ser lo último indexado
        bajo la misma clave. Esto preserva el comportamiento de Sesión 3 para
        las partes que `pinouts_library.json` ya cubre (incluyendo enriquecidos
        como `uart_programming`), mientras extiende la cobertura de pinout a
        cientos de MCUs/reguladores/drivers reales que antes no existían en
        ningún lado del sistema.
        """
        pinout_chunks: dict[str, dict] = {}
        order: list[str] = []

        index_file = self._data_dir / "symbols_index.json"
        if index_file.exists():
            try:
                with open(index_file, encoding="utf-8") as f:
                    index = json.load(f)
            except (json.JSONDecodeError, OSError):
                index = {}
            for sym in index.get("symbols", []) or []:
                lib_id = sym.get("lib_id")
                pins = sym.get("pins") or {}
                if not lib_id or not pins:
                    continue
                key = normalize_part_name(lib_id)
                library = sym.get("library", "")
                text = " ".join(str(p) for p in (
                    lib_id, library, sym.get("description", ""), sym.get("keywords", ""),
                ) if p)
                data = {
                    "name": lib_id,
                    "symbol": f"{library}:{lib_id}" if library else lib_id,
                    "footprint": sym.get("footprint_default", ""),
                    "description": sym.get("description", ""),
                    "pins": pins,
                }
                if key not in pinout_chunks:
                    order.append(key)
                pinout_chunks[key] = {
                    "text": text,
                    "source": f"KiCadSymbol:{library}:{lib_id}",
                    "type": "pinout",
                    "data": data,
                }

        manual_file = _HERE / "pinouts_library.json"
        if manual_file.exists():
            try:
                with open(manual_file, encoding="utf-8") as f:
                    manual = json.load(f)
            except (json.JSONDecodeError, OSError):
                manual = {}
            for name, entry in (manual or {}).items():
                if not isinstance(entry, dict):
                    continue
                key = normalize_part_name(name)
                text = " ".join(str(p) for p in (
                    name, entry.get("type", ""), entry.get("description", ""),
                ) if p)
                data = dict(entry)
                data["name"] = name
                if key not in pinout_chunks:
                    order.append(key)
                pinout_chunks[key] = {
                    "text": text,
                    "source": f"Override:{name}",
                    "type": "pinout",
                    "data": data,
                }

        for key in order:
            self._chunks.append(pinout_chunks[key])

    def _load_embed_cache(self) -> None:
        """Load persisted dense vectors if manifest matches chunk count and SHA-256 fingerprint."""
        if not _SKLEARN_OK or np is None:
            return
        if not _EMBED_MATRIX.exists() or not _EMBED_MANIFEST.exists():
            return
        try:
            with open(_EMBED_MANIFEST, encoding="utf-8") as f:
                manifest = json.load(f)
            if manifest.get("chunk_count") != len(self._chunks):
                return
            manifest_hash = manifest.get("content_hash", "")
            if manifest_hash and manifest_hash != self._compute_chunks_hash():
                return  # Cache is stale due to chunk content modifications
            self._embed_matrix = np.load(_EMBED_MATRIX)
        except (OSError, ValueError, json.JSONDecodeError):
            self._embed_matrix = None

    def _get_embed_client(self):
        if self._embed_client is None:
            from knowledge.embed_client import get_embed_client
            self._embed_client = get_embed_client()
        return self._embed_client

    def rebuild_embed_index(self, force: bool = False) -> dict:
        """Embed all chunks via Ollama and persist to disk with SHA-256 fingerprinting."""
        client = self._get_embed_client()
        if not client.available:
            return {"error": client.status().get("last_error", "embed unavailable")}
        texts = [c["text"] for c in self._chunks]
        vectors = []
        batch_size = 100
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            batch_vecs = client.embed_batch(batch)
            if len(batch_vecs) != len(batch):
                return {
                    "error": (
                        f"embedding batch incomplete at offset {start}: "
                        f"got {len(batch_vecs)}/{len(batch)} — "
                        f"{client.status().get('last_error', 'unknown')}"
                    )
                }
            vectors.extend(batch_vecs)
        if len(vectors) != len(texts):
            return {"error": "embedding batch incomplete"}
        _EMBED_DIR.mkdir(parents=True, exist_ok=True)
        mat = np.stack(vectors, axis=0)
        np.save(_EMBED_MATRIX, mat)
        manifest = {
            "chunk_count": len(self._chunks),
            "content_hash": self._compute_chunks_hash(),
            "model": client.model,
            "sources": [c["source"] for c in self._chunks],
        }
        _EMBED_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._embed_matrix = mat
        return {"indexed": len(vectors), "path": str(_EMBED_MATRIX)}

    def _load_default_data(self) -> None:
        """Carga datos IPC + componentes + training examples."""
        comp_file = self._data_dir / "components.json"
        ipc_file  = self._data_dir / "ipc_2221.json"

        if comp_file.exists():
            with open(comp_file, encoding="utf-8") as f:
                comps = json.load(f)
            for c in comps:
                self._chunks.extend(_chunk_component(c))

        if ipc_file.exists():
            with open(ipc_file, encoding="utf-8") as f:
                ipc = json.load(f)
            self._chunks.extend(_chunk_ipc(ipc))

        self._load_training_examples()
        self._load_experiences()
        self._load_symbol_index()
        self._fit()

    def ingest_text(self, text: str, source: str = "user",
                    chunk_type: str = "note") -> int:
        """
        Añade texto libre a la base.
        Útil para añadir application notes, textos de diseño, etc.
        """
        # Dividir en chunks de ~300 palabras
        words  = text.split()
        size   = 300
        stride = 250
        n      = 0
        for i in range(0, max(1, len(words) - size + 1), stride):
            chunk_text = " ".join(words[i:i + size])
            self._chunks.append({
                "text": chunk_text,
                "source": source,
                "type": chunk_type,
                "data": {"text": chunk_text},
            })
            n += 1
        self._fit()
        return n

    def ingest_json(self, data: dict, source: str = "custom",
                    chunk_type: str = "json") -> int:
        """Ingesta un dict arbitrario como chunk."""
        text = _text_from_dict(data) if chunk_type != "circuit_example" else _summarize_circuit_data(data)
        self._chunks.append({
            "text": text,
            "source": source,
            "type": chunk_type,
            "data": data,
        })
        self._fit()
        return 1

    def _fit(self) -> None:
        """Entrena el vectorizador TF-IDF sobre todos los chunks."""
        if not _SKLEARN_OK or not self._chunks:
            return
        texts = [c["text"] for c in self._chunks]
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_df=0.85,
            min_df=1,
            lowercase=True,
            strip_accents="unicode",
        )
        self._matrix = self._vectorizer.fit_transform(texts)
        self._fitted = True

    # ── Búsqueda ──────────────────────────────────────────────────

    def query(self, question: str, top_k: int | None = None,
              chunk_type: Optional[str] = None) -> list[dict]:
        """
        Búsqueda semántica sobre la base de conocimiento.
        Uses hybrid TF-IDF + dense embeddings when available.
        """
        if top_k is None:
            top_k = int(cfg("rag.default_top_k", 5))
        backend = self._backend
        use_dense = backend in ("hybrid", "dense") and self._embed_matrix is not None
        use_tfidf = backend in ("hybrid", "tfidf")

        dense_results: list[dict] = []
        tfidf_results: list[dict] = []

        if use_dense and _SKLEARN_OK and np is not None:
            dense_results = self._dense_search(question, top_k * 3, chunk_type)

        if use_tfidf and self._fitted and _SKLEARN_OK:
            tfidf_results = self._tfidf_search(question, top_k * 3, chunk_type)
        elif use_tfidf and not self._fitted:
            tfidf_results = self._keyword_search(question, top_k * 3, chunk_type)

        if backend == "dense" and dense_results:
            merged = dense_results[:top_k]
        elif backend == "tfidf" or not dense_results:
            merged = (tfidf_results or self._keyword_search(question, top_k, chunk_type))[:top_k]
        else:
            merged = self._merge_results(dense_results, tfidf_results, top_k, chunk_type)

        merged = self._rerank_by_overlap(question, merged)
        merged = self._inject_filename_hits(question, merged, chunk_type, top_k)
        return merged[:top_k]

    def _inject_filename_hits(self, question: str, results: list[dict],
                            chunk_type: Optional[str], top_k: int) -> list[dict]:
        """Ensure TF-IDF filename matches (e.g. usb_dp) appear for domain queries."""
        q = question.lower()
        keywords = []
        if "usb" in q:
            keywords.append("usb")
        if not keywords or not self._fitted:
            return results
        tfidf = self._tfidf_search(question, top_k * 8, chunk_type)
        filename_hits = [
            r for r in tfidf
            if any(k in r["source"].lower() for k in keywords)
        ]
        if not filename_hits:
            return results
        seen = {r["source"] for r in results}
        combined = list(results)
        for r in filename_hits:
            if r["source"] not in seen:
                combined.append(r)
                seen.add(r["source"])
        return self._rerank_by_overlap(question, combined)

    def _rerank_by_overlap(self, question: str, results: list[dict]) -> list[dict]:
        """Boost results whose source/excerpt share query tokens (helps USB filename hits)."""
        tokens = [t for t in re.findall(r'\w+', question.lower()) if len(t) > 2]
        if not tokens:
            return results
        for r in results:
            hay = (r["source"] + " " + r.get("excerpt", "")).lower()
            boost = sum(0.08 for t in tokens if t in hay)
            r["score"] = round(r["score"] + boost, 4)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _tfidf_search(self, question: str, top_k: int,
                      chunk_type: Optional[str] = None) -> list[dict]:
        q_vec = self._vectorizer.transform([question])
        sims = cosine_similarity(q_vec, self._matrix).flatten()
        indices = sims.argsort()[::-1]
        results = []
        for i in indices:
            if len(results) >= top_k:
                break
            chunk = self._chunks[i]
            if chunk_type and chunk["type"] != chunk_type:
                continue
            score = float(sims[i])
            if score < 0.01:
                break
            results.append(self._result_dict(chunk, score))
        return results

    def _dense_search(self, question: str, top_k: int,
                      chunk_type: Optional[str] = None) -> list[dict]:
        client = self._get_embed_client()
        q_vec = client.embed_one(question)
        if q_vec is None or self._embed_matrix is None:
            return []
        sims = self._embed_matrix @ q_vec
        indices = sims.argsort()[::-1]
        results = []
        for i in indices:
            if len(results) >= top_k:
                break
            chunk = self._chunks[i]
            if chunk_type and chunk["type"] != chunk_type:
                continue
            score = float(sims[i])
            if score < 0.05:
                break
            results.append(self._result_dict(chunk, score))
        return results

    def _merge_results(self, dense: list[dict], tfidf: list[dict],
                       top_k: int, chunk_type: Optional[str]) -> list[dict]:
        combined: dict[str, dict] = {}
        for r in dense:
            key = r["source"]
            combined[key] = {**r, "score": r["score"] * 0.6}
        for r in tfidf:
            key = r["source"]
            if key in combined:
                combined[key]["score"] = round(combined[key]["score"] + r["score"] * 0.4, 4)
            else:
                combined[key] = {**r, "score": round(r["score"] * 0.4, 4)}
        merged = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
        if chunk_type:
            merged = [m for m in merged if m["type"] == chunk_type]
        return merged[:top_k]

    @staticmethod
    def _result_dict(chunk: dict, score: float) -> dict:
        return {
            "source": chunk["source"],
            "type": chunk["type"],
            "score": round(score, 4),
            "data": chunk["data"],
            "excerpt": chunk["text"][:300],
        }

    def _keyword_search(self, question: str, top_k: int,
                         chunk_type: Optional[str] = None) -> list[dict]:
        """Fallback sin sklearn: búsqueda por palabras clave."""
        tokens = set(re.findall(r'\w+', question.lower()))
        results = []
        for chunk in self._chunks:
            if chunk_type and chunk["type"] != chunk_type:
                continue
            text_tokens = set(re.findall(r'\w+', chunk["text"].lower()))
            score = len(tokens & text_tokens) / max(len(tokens), 1)
            if score > 0:
                results.append({
                    "source": chunk["source"],
                    "type":   chunk["type"],
                    "score":  round(score, 4),
                    "data":   chunk["data"],
                    "excerpt": chunk["text"][:300],
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ── Búsquedas especializadas ───────────────────────────────────

    def search_component(self, query: str, top_k: int | None = None,
                         category: Optional[str] = None) -> list[dict]:
        """
        Búsqueda específica de componentes.
        Filtra por categoría si se especifica.
        """
        if top_k is None:
            top_k = int(cfg("rag.default_top_k", 5))
        results = self.query(query, top_k=top_k * 2,
                             chunk_type="component")
        if category:
            results = [r for r in results
                       if r["data"].get("category", "").lower() == category.lower()]
        return results[:top_k]

    def get_design_rules(self, voltage_v: Optional[float] = None,
                         current_a: Optional[float] = None,
                         category: str = "all") -> dict:
        """
        Devuelve reglas de diseño IPC-2221 aplicables.

        Args:
            voltage_v: Voltaje máx. entre conductores (V).
            current_a: Corriente máxima (A).
            category:  "clearance", "trace_width", "via", "all".

        Returns:
            dict con reglas aplicables.
        """
        ipc_file = self._data_dir / "ipc_2221.json"
        if not ipc_file.exists():
            return {"error": "ipc_2221.json no encontrado"}

        with open(ipc_file, encoding="utf-8") as f:
            ipc = json.load(f)

        rules = {}

        if voltage_v is not None and category in ("clearance", "all"):
            # Buscar en la tabla de espaciados
            for k in ["conductor_spacing_internal",
                       "conductor_spacing_external_coated",
                       "conductor_spacing_external_uncoated"]:
                table = ipc.get(k, {}).get("voltage_range", {})
                for rng, val in table.items():
                    lo, hi = map(float, rng.split("-"))
                    if lo <= voltage_v <= hi:
                        rules.setdefault("clearance_mm", {})[k] = val
                        break

        if current_a is not None and category in ("trace_width", "all"):
            # Buscar en tabla de anchura de pista
            for k in ["trace_width_external_1oz", "trace_width_internal_1oz"]:
                table = ipc.get(k, {}).get("current_a", {})
                # Mantener clave original del JSON para el lookup
                items = sorted(table.items(), key=lambda kv: float(kv[0]))
                for orig_key, val in items:
                    if float(orig_key) >= current_a:
                        rules.setdefault("trace_width_mm", {})[k] = val
                        break

        if category in ("via", "all"):
            rules["via"] = ipc.get("via_rules", {})

        if category in ("board_edge", "all"):
            rules["board_edge_clearance"] = ipc.get("board_edge_clearance", {})

        rules["substrates"] = list(ipc.get("common_substrates", {}).keys())
        rules["ref"] = "IPC-2221B"

        return rules

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        by_type: dict[str, int] = {}
        for c in self._chunks:
            by_type[c["type"]] = by_type.get(c["type"], 0) + 1

        circuit_examples = [c for c in self._chunks if c["type"] == "circuit_example"]
        total_ce = len(circuit_examples)
        with_desc = sum(1 for c in circuit_examples if _text_has_description_density(c["text"]))

        embed_ok = self._embed_matrix is not None
        if not embed_ok:
            client = self._get_embed_client()
            embed_ok = client.available
        return {
            "total_chunks": len(self._chunks),
            "by_type": by_type,
            "sklearn_available": _SKLEARN_OK,
            "fitted": self._fitted,
            "rag_backend": self._backend,
            "embed_index_loaded": self._embed_matrix is not None,
            "embed_index_path": str(_EMBED_MATRIX) if _EMBED_MATRIX.exists() else None,
            "embed_client_available": embed_ok,
            "circuit_example_description_density": {
                "total": total_ce,
                "with_description": with_desc,
                "ratio": round(with_desc / total_ce, 4) if total_ce else 0.0,
            },
        }


# ─── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kb = ElectronicsKnowledgeBase()
    print("=== Knowledge Base Stats ===")
    s = kb.stats()
    for k, v in s.items():
        print(f"  {k}: {v}")

    print("\n=== Query: 'ESP32 WiFi decoupling capacitor' ===")
    for r in kb.query("ESP32 WiFi decoupling capacitor", top_k=3):
        print(f"  [{r['score']:.3f}] {r['source']}: {r['excerpt'][:100]}...")

    print("\n=== Query: 'RF pulse receiver induction LED' (design-intent fidelity check) ===")
    for r in kb.query("RF pulse receiver induction LED", top_k=3, chunk_type="circuit_example"):
        print(f"  [{r['score']:.3f}] {r['source']}: {r['excerpt'][:160]}...")

    print("\n=== Query: 'clearance 50V external uncoated' ===")
    for r in kb.query("clearance 50V external uncoated", top_k=3):
        print(f"  [{r['score']:.3f}] {r['source']}: {r['excerpt'][:100]}...")

    print("\n=== Design Rules for 48V, 2A ===")
    rules = kb.get_design_rules(voltage_v=48.0, current_a=2.0)
    print(f"  Clearance: {rules.get('clearance_mm')}")
    print(f"  Trace width: {rules.get('trace_width_mm')}")
