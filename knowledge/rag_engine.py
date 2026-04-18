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
import math
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

# ─── Rutas ───────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "data"


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


# ─── ElectronicsKnowledgeBase ─────────────────────────────────────────────────

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
        self._load_default_data()

    # ── Ingesta ───────────────────────────────────────────────────

    def _load_default_data(self) -> None:
        """Carga datos IPC + componentes automáticamente."""
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

    def ingest_json(self, data: dict, source: str = "custom") -> int:
        """Ingesta un dict arbitrario como chunk."""
        text = _text_from_dict(data)
        self._chunks.append({
            "text": text,
            "source": source,
            "type": "json",
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

    def query(self, question: str, top_k: int = 5,
              chunk_type: Optional[str] = None) -> list[dict]:
        """
        Búsqueda semántica sobre la base de conocimiento.

        Args:
            question:   Consulta en lenguaje natural.
            top_k:      Número de resultados.
            chunk_type: Filtro por tipo ("component","design_rule","support_circuit").

        Returns:
            Lista de dicts {source, type, score, data, excerpt}.
        """
        if not self._fitted or not _SKLEARN_OK:
            return self._keyword_search(question, top_k, chunk_type)

        q_vec = self._vectorizer.transform([question])
        sims  = cosine_similarity(q_vec, self._matrix).flatten()

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
            results.append({
                "source": chunk["source"],
                "type":   chunk["type"],
                "score":  round(score, 4),
                "data":   chunk["data"],
                "excerpt": chunk["text"][:300],
            })

        return results

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

    def search_component(self, query: str, top_k: int = 5,
                         category: Optional[str] = None) -> list[dict]:
        """
        Búsqueda específica de componentes.
        Filtra por categoría si se especifica.
        """
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
        return {
            "total_chunks": len(self._chunks),
            "by_type": by_type,
            "sklearn_available": _SKLEARN_OK,
            "fitted": self._fitted,
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

    print("\n=== Query: 'clearance 50V external uncoated' ===")
    for r in kb.query("clearance 50V external uncoated", top_k=3):
        print(f"  [{r['score']:.3f}] {r['source']}: {r['excerpt'][:100]}...")

    print("\n=== Design Rules for 48V, 2A ===")
    rules = kb.get_design_rules(voltage_v=48.0, current_a=2.0)
    print(f"  Clearance: {rules.get('clearance_mm')}")
    print(f"  Trace width: {rules.get('trace_width_mm')}")
