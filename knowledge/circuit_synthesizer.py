"""
knowledge/circuit_synthesizer.py
=================================
Agente LLM para Generación de Circuitos a partir de lenguaje natural.
Traduce descripciones textuales en una topología (Netlist JSON)
que PulseLab Forge puede renderizar y simular.
"""

import json
import re
from typing import Any

from knowledge.llm_backends import backend_limits, get_backend_client, resolve_backend_name
from knowledge.llm_json import extract_json_text, parse_json_object
from knowledge.llm_prompt_format import chat_options_for_backend, format_system_prompt, format_user_prompt
from knowledge.llm_session_log import new_call_id
from knowledge.ollama_native import normalize_think
from knowledge.pulse_config import cfg, PULSE_LLM_THINK
from knowledge.rag_engine import ElectronicsKnowledgeBase, normalize_part_name
from core.logger import logger

_OBLIGATORIAS_UART_USB = """
REGLAS UART / USB (OBLIGATORIAS):
- Para ESP32-WROOM-32 programación UART: U0TXD=GPIO1, U0RXD=GPIO3.
- CH340/CP2102: TXD del bridge va a RX del MCU; RXD del bridge va a TX del MCU.
- Incluir condensadores de desacople 100nF + 10uF en alimentación del MCU.
- Pines EN del ESP32 requieren pull-up 10k a 3.3V.
- USB D+ y D- deben nombrarse USB_D+ y USB_D- (o D+/D-).
"""

_PROMPT_CORE = """
Eres el 'PulseLab Circuit Engine', un experto en diseño electrónico.
Tu tarea es convertir descripciones de circuitos en un JSON estricto.

REGLAS DE FORMATO:
- Devuelve ÚNICAMENTE un objeto JSON con una clave "circuit" que contenga una lista de componentes.
- Cada componente debe ser un objeto con:
    "etype": "R" (resistencia), "C" (cap), "L" (ind), "V" (fuente), "S" (sw), "GND" (tierra), o "IC", "MCU".
    "value": Valor NUMÉRICO real para pasivos o string para nombre de ICs (ej. "ESP32", "1000").
    "n1", "n2": Nombres de nodos (strings) para componentes de 2 pines (R, C, L, V, S). 'GND' es obligatorio para la referencia.
    "pins": (SOLO PARA IC/MCU) Un objeto que mapea el NÚMERO del pad (string, ej. "1", "2") al nombre de la red. Ej: {"1": "VCC", "2": "GND", "3": "I2C_SDA"}. REVISAR CUIDADOSAMENTE EL NÚMERO CORRECTO EN EL CONTEXTO.
    "unconnected_pins": (OPCIONAL, SOLO PARA IC/MCU) Array de números de pin (strings) que existen físicamente pero se dejan libres A PROPÓSITO en este diseño (ver FIDELIDAD DE PINES abajo).
    "label": Etiqueta descriptiva corta.
    "symbol": (SOLO PARA IC/MCU) Símbolo KiCad extraído del contexto.
    "footprint": (SOLO PARA IC/MCU) Footprint KiCad extraído del contexto.

FIDELIDAD DE PINES (IC/MCU) — OBLIGATORIO:
- Cuando el contexto te dé la tabla de pines completa de un componente (ver "PINOUTS
  RELEVANTES"), tu respuesta debe dar cuenta de TODOS esos pines, no solo de los usados
  en el circuito. Nunca omitas un pin en silencio.
- Para cada pin físico que exista pero NO se use en este diseño (GPIO de expansión libre,
  pin reservado, etc.), decláralo explícitamente de una de estas dos formas equivalentes:
    (a) inclúyelo en "pins" mapeado al valor literal "NC" (ej. {"6": "NC"}), o
    (b) lista su número en un array aparte "unconnected_pins" (ej. ["6", "7", "8"]).
  Usa "NC"/"unconnected_pins" para "no conectado a propósito"; nunca dejes un pin fuera
  de la respuesta solo para ahorrar espacio — con eso no se puede distinguir "decidido
  no usar" de "olvidado por el generador".

EJEMPLOS:
{example_block}
RECUERDA: Devuelve un JSON válido. Usa SIEMPRE "pins" para interconectar módulos complejos, NO uses "S" (switches) para eso.
{obligatorias_block}
Devuelve SOLO el JSON final, sin explicaciones ni bloques de razonamiento.
Si usas razonamiento interno, termina con el objeto JSON en una sola respuesta.
"""


class CircuitSynthesizer:
    def __init__(self, backend: str = "auto", ab_variant: str = "a"):
        self.backend_pref = backend
        self.ab_variant = ab_variant if ab_variant in ("a", "b") else "a"
        self.rag = ElectronicsKnowledgeBase()
        self.pinouts_db = self._load_pinouts()
        self.base_system_prompt = self._build_base_system_prompt()

    def _build_base_system_prompt(self) -> str:
        obligatorias = _OBLIGATORIAS_UART_USB if self.ab_variant == "a" else ""
        return _PROMPT_CORE.replace("{example_block}", self._build_examples_block()).replace(
            "{obligatorias_block}", obligatorias
        )

    JSON_USER_SUFFIX = (
        "\n\nResponde UNICAMENTE con el objeto JSON. "
        "Sin markdown, sin texto antes ni despues. Clave raiz: \"circuit\"."
    )

    def _resolve_backend(self) -> tuple[str, Any]:
        name = resolve_backend_name(task="circuit", prefer=self.backend_pref)
        return name, get_backend_client(name)

    def _max_system_chars(self, backend: str) -> int:
        return int(backend_limits(backend)["prompt_max_chars"])

    @property
    def _max_rag_components(self) -> int:
        return int(cfg("llm.agents.circuit_synthesizer.rag_max_components", 8))

    @property
    def _max_pinout_entries(self) -> int:
        return int(cfg("llm.agents.circuit_synthesizer.max_pinout_entries", 2))

    @property
    def _max_pinout_pins(self) -> int:
        return int(cfg("llm.agents.circuit_synthesizer.max_pinout_pins", 14))

    def _circuit_example_rag_top_k(self) -> int:
        """Variant-aware top_k for chunk_type=circuit_example (Session 4b A/B)."""
        if self.ab_variant == "b":
            key = "llm.agents.circuit_synthesizer.rag_top_k_variant_b"
            default = 4
        else:
            key = "llm.agents.circuit_synthesizer.rag_top_k"
            default = 1
        raw = cfg(key, default)
        top_k = int(raw)
        if top_k < 1:
            logger.warning(
                "circuit_synthesizer",
                f"rag_top_k truncado a 0 desde cfg {key}={raw!r}; usando 1",
            )
            top_k = 1
        return top_k

    _STATIC_EXAMPLE = """Usuario: "Un ESP32 conectado a una pantalla I2C y a un resistor pull-up a 3.3V"
Respuesta:
{
  "circuit": [
    {"etype": "V", "value": 3.3, "n1": "3.3V", "n2": "GND", "label": "V1"},
    {"etype": "MCU", "value": "ESP32-S3", "symbol": "RF_Module:ESP32-WROOM-32", "footprint": "RF_Module:ESP32-WROOM-32", "pins": {"2": "3.3V", "1": "GND", "33": "I2C_SDA", "36": "I2C_SCL"}, "label": "U1"},
    {"etype": "IC", "value": "SSD1306", "symbol": "Connector_Generic:Conn_01x04", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "pins": {"2": "3.3V", "1": "GND", "4": "I2C_SDA", "3": "I2C_SCL"}, "label": "OLED"},
    {"etype": "R", "value": 4700.0, "n1": "3.3V", "n2": "I2C_SDA", "label": "R_PULLUP_SDA"}
  ]
}
NOTA: este ejemplo es deliberadamente corto para ilustrar el esquema JSON base; NO uses
su MCU (solo 4 pines) como referencia de cuántos pines declarar. Mira el ejemplo dinámico
de cobertura completa a continuación para eso."""

    def _build_dynamic_pinout_example(self) -> str:
        """Worked example generated from the 'golden' esp32_usb_devkit preset, enriched
        with the full ESP32-WROOM-32 pin table so unused physical pins are shown declared
        as "NC" instead of silently missing. This exists because the old static example
        (4/39 ESP32 pins) was the strongest style anchor in the prompt despite being the
        least complete circuit in the system (docs/calibration_forge/pin_model_coverage.md).
        """
        try:
            from presets.esp32_usb_devkit import load as load_golden_preset
        except Exception:
            return ""
        try:
            graph = load_golden_preset()
        except Exception:
            return ""

        mcu_full_pins = (self.pinouts_db.get("ESP32-WROOM-32") or {}).get("pins") or {}
        circuit = []
        for comp in graph.components:
            entry: dict = {"etype": comp.etype, "value": comp.value, "label": comp.label}
            if comp.symbol_id:
                entry["symbol"] = comp.symbol_id
            if comp.footprint_id:
                entry["footprint"] = comp.footprint_id
            if comp.etype in ("IC", "MCU"):
                pins = dict(comp.pins or {})
                if comp.value == "ESP32-WROOM-32":
                    for pin_num in mcu_full_pins:
                        pins.setdefault(pin_num, "NC")
                entry["pins"] = pins
            elif comp.etype != "GND":
                entry["n1"] = comp.n1
                entry["n2"] = comp.n2
            circuit.append(entry)

        example = {"circuit": circuit}
        return (
            'Usuario: "Diseña una placa devkit con ESP32-WROOM-32, alimentación 5V USB '
            'regulada a 3.3V con AMS1117, puente USB-UART CH340G, pull-up EN 10k, '
            'condensadores de desacople y headers GPIO"\n'
            "Respuesta:\n"
            + json.dumps(example, ensure_ascii=False)
            + "\nNOTA: observa que el MCU declara sus 39 pines físicos; los que no participan "
            "en este diseño quedan marcados \"NC\" en vez de omitirse."
        )

    def _build_examples_block(self) -> str:
        dynamic = self._build_dynamic_pinout_example()
        if not dynamic:
            return self._STATIC_EXAMPLE + "\n"
        return (
            "EJEMPLO DE COBERTURA COMPLETA (preset golden esp32_usb_devkit):\n"
            + dynamic
            + "\n\nEJEMPLO MINIMO DE ESQUEMA (circuito corto):\n"
            + self._STATIC_EXAMPLE
            + "\n"
        )

    def _load_pinouts(self):
        """Carga `pinouts_library.json` directo (sin pasar por el RAG).

        Desde Sesión 4a, `_match_pinouts()` ya no usa `self.pinouts_db` para
        retrieval (migrado a `self.rag.query(chunk_type="pinout")`); se mantiene
        esta carga sólo porque `_build_dynamic_pinout_example()` necesita lookup
        directo por nombre exacto (`self.pinouts_db.get("ESP32-WROOM-32")`) para
        construir el ejemplo estático de cobertura completa embebido en el prompt.
        """
        try:
            import os
            path = os.path.join(os.path.dirname(__file__), "pinouts_library.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _match_pinouts(self, description: str) -> list[tuple[str, dict]]:
        """Return at most `_max_pinout_entries` best-matching pinout entries, ordered
        best-first (avoid dumping all ESP32 variants) via RAG semantic search over the
        unified `chunk_type="pinout"` index (real KiCad symbols + curated overrides from
        `pinouts_library.json`, see `ElectronicsKnowledgeBase._load_symbol_index()`). The
        first item is the high-confidence/primary match; any others are secondary/
        low-confidence and get compacted in `_compact_pinout` instead of a full pin dump.

        Migrated in Sesión 4a from an exact-substring match against `self.pinouts_db` (kept
        below only for `_build_dynamic_pinout_example`'s direct name lookup) to TF-IDF/dense
        retrieval — this lets natural-language descriptions find parts by description/
        keywords even when the exact lib_id never appears verbatim in the prompt (ver drift
        de nombres hand-curado vs. real en docs/calibration_forge/kicad_symbol_kb.md).

        Pure semantic ranking alone regressed the exact-name case: with ~5300 real KiCad
        chunks now in the index, a literal part number in the description (ej. "BME280",
        "SSD1306") could lose to a semantically-similar-but-wrong part (ej. "TMP1075D", also
        an "I2C digital sensor") whose indexed description/keywords happen to share more
        vocabulary with the query — confirmed empirically via a live regression run where
        `ESP32-WROOM-32`/`BME280` dropped out of the top matches entirely for a prompt that
        names them verbatim. To fix this without losing the new semantic fallback, we fetch
        a wider candidate pool from RAG and re-rank with an exact-normalized-name boost
        (mirrors the old scorer's `if kl in desc: score += 100 + len(kl)` bonus) layered on
        top of the base RAG score — literal name matches win when present, semantic
        similarity still decides everything else (drifted/undocumented names).
        """
        if not description:
            return []
        pool_size = max(self._max_pinout_entries * 5, 10)
        results = self.rag.query(description, top_k=pool_size, chunk_type="pinout")
        if not results:
            return []
        desc_norm = normalize_part_name(description)

        def _boosted_score(r: dict) -> float:
            name = (r.get("data") or {}).get("name", "")
            key_norm = normalize_part_name(name)
            score = r["score"]
            if key_norm and key_norm in desc_norm:
                score += 100 + len(key_norm)
            return score

        results.sort(key=_boosted_score, reverse=True)
        matched: list[tuple[str, dict]] = []
        for r in results[: self._max_pinout_entries]:
            entry = r.get("data") or {}
            key = entry.get("name") or r.get("source", "")
            matched.append((key, entry))
        return matched

    def _compact_pinout(self, entry: dict, full: bool = False) -> dict:
        """Pinout snippet for prompt injection.

        `full=True` (primary/high-confidence match, see `_match_pinouts`) always includes
        the complete pin table regardless of size — the old behavior silently dropped the
        ENTIRE table once it exceeded `max_pinout_pins`, which is why generated circuits
        only ever showed a handful of pins (see pin_model_coverage.md). Secondary/
        low-confidence matches (`full=False`) keep the old size-capped compaction to save
        prompt budget on entries that are unlikely to be the actual part used.
        """
        out: dict = {}
        for field in ("symbol", "footprint", "description"):
            if entry.get(field):
                out[field] = entry[field]
        for field in ("uart_programming", "usb", "i2c_default"):
            if entry.get(field):
                out[field] = entry[field]
        pins = entry.get("pins") or {}
        if pins and (full or len(pins) <= self._max_pinout_pins):
            out["pins"] = pins
        return out

    def _compact_component(self, comp: dict) -> dict:
        out = {
            "etype": comp.get("etype"),
            "value": comp.get("value"),
            "label": comp.get("label"),
        }
        if comp.get("symbol"):
            out["symbol"] = comp["symbol"]
        if comp.get("footprint"):
            out["footprint"] = comp["footprint"]
        if comp.get("pins"):
            out["pins"] = comp["pins"]
        elif comp.get("n1") is not None:
            out["n1"] = comp["n1"]
            out["n2"] = comp.get("n2")
        return out

    def _get_pinouts_context(self, description: str = "") -> str:
        if not self.pinouts_db:
            return ""
        matched = self._match_pinouts(description) if description else []
        if not matched:
            return ""
        compact = {
            key: self._compact_pinout(entry, full=(idx == 0))
            for idx, (key, entry) in enumerate(matched)
        }
        note = (
            "\nNOTA: el componente de mayor coincidencia arriba incluye su tabla de pines "
            "COMPLETA. Marca como \"NC\" (o en \"unconnected_pins\") cualquier pin de esa "
            "tabla que decidas dejar libre en este diseño, en vez de omitirlo.\n"
        )
        return "\nPINOUTS RELEVANTES:\n" + json.dumps(compact, ensure_ascii=False) + "\n" + note

    def _normalize_unconnected_pins(self, components: list) -> None:
        """Resolve the "NC"/"unconnected_pins" convention (see base_system_prompt and
        ATOMIC_JSON_SUFFIX) into unique per-pin net names.

        Naively passing a literal "NC" (or any single shared label) into `pins` for
        several different pins would make downstream consumers (schematic_generator.py,
        the PCB autorouter) treat them as ONE shared net — i.e. it would electrically
        short together pins that are each individually unconnected. To keep "declared
        intentionally floating" from becoming "silently wired together", each declared
        NC pin is rewritten to its own unique net name before leaving this module.
        """
        for comp in components:
            if comp.get("etype") not in ("IC", "MCU"):
                continue
            label = comp.get("label") or comp.get("value") or "U"
            pins = comp.get("pins")
            if isinstance(pins, dict):
                for pin_num, net in list(pins.items()):
                    if isinstance(net, str) and net.strip().upper() == "NC":
                        pins[pin_num] = f"NC_{label}_{pin_num}"
            unconnected = comp.pop("unconnected_pins", None)
            if unconnected:
                if not isinstance(pins, dict):
                    pins = {}
                    comp["pins"] = pins
                for pin_num in unconnected:
                    pin_key = str(pin_num)
                    if pin_key not in pins:
                        pins[pin_key] = f"NC_{label}_{pin_key}"

    def _extract_circuit_list(self, data: dict) -> list:
        circuit = data.get("circuit", data)
        if isinstance(circuit, list):
            return circuit
        if isinstance(circuit, dict):
            for v in circuit.values():
                if isinstance(v, list):
                    return v
        return []

    def _build_system_prompt(self, description: str, include_rag: bool, backend: str) -> str:
        prompt = self.base_system_prompt + self._get_pinouts_context(description)
        budget = self._max_system_chars(backend)
        if not include_rag:
            return prompt[:budget]

        rag_results = self.rag.query(
            description,
            top_k=self._circuit_example_rag_top_k(),
            chunk_type="circuit_example",
        )
        for res in rag_results:
            raw = self._extract_circuit_list(res.get("data", {}))
            circuit_data = [
                self._compact_component(c)
                for c in raw[: self._max_rag_components]
                if isinstance(c, dict)
            ]
            if not circuit_data:
                continue
            chunk = (
                f"\nEJEMPLO SIMILAR ({res.get('source', 'RAG')}):\n"
                + json.dumps({"circuit": circuit_data}, ensure_ascii=False)
                + "\n"
            )
            if len(prompt) + len(chunk) > budget:
                break
            prompt += chunk
        return format_system_prompt(prompt[:budget], backend)

    def _call_llm(
        self,
        system: str,
        user_msg: str,
        *,
        backend: str,
        llm,
        session_id: str,
        meta: dict | None = None,
        attempt: int = 1,
    ) -> dict:
        opts = chat_options_for_backend(backend)
        return llm.chat(
            system=system,
            user=user_msg,
            temperature=float(cfg("llm.agents.circuit_synthesizer.temperature", 0.1)),
            max_tokens=opts["max_tokens"],
            json_mode=opts["json_mode"],
            disable_thinking=opts["disable_thinking"],
            caller="circuit_synthesizer",
            session_id=session_id,
            meta={**(meta or {}), "attempt": attempt, "backend": backend},
        )


    def generate_circuit_json(
        self,
        description: str,
        *,
        session_id: str | None = None,
        meta: dict | None = None,
        backend: str | None = None,
    ) -> dict:
        if backend:
            self.backend_pref = backend
        backend_name, llm = self._resolve_backend()
        if not llm.available:
            return {"error": f"LLM backend '{backend_name}' no disponible."}

        session_id = session_id or new_call_id()
        run_meta = {
            "description": description[: int(cfg("llm.agents.circuit_synthesizer.description_meta_max_chars", 2000))],
            "backend": backend_name,
            "ab_variant": self.ab_variant,
            **(meta or {}),
        }

        logger.ai_review(
            "circuit_synthesizer",
            f"generate_circuit_json() backend={backend_name} session={session_id} "
            f"desc='{description[:120]}'",
        )

        use_rag = backend_name == "primary" and normalize_think(PULSE_LLM_THINK) not in (False,)
        user_msg = format_user_prompt(
            f"Genera este circuito: {description}{self.JSON_USER_SUFFIX}",
            backend_name,
        )

        system_prompt = self._build_system_prompt(description, include_rag=use_rag, backend=backend_name)
        result = self._call_llm(
            system_prompt, user_msg,
            backend=backend_name, llm=llm,
            session_id=session_id, meta=run_meta, attempt=1,
        )

        if "error" in result:
            logger.error("circuit_synthesizer", f"session={session_id} attempt=1 LLM error: {result['error']}")
            return result

        try:
            raw_content = result.get("content", "")
            try:
                data = parse_json_object(raw_content)
            except json.JSONDecodeError as je:
                logger.warning(
                    "circuit_synthesizer",
                    f"session={session_id} attempt=1 JSON invalido ({je}); reintentando con RAG completo",
                )
                # Retry with one compact RAG example, still capped.
                # Inject the recent AI-context buffer so the model can see what
                # happened right before the parse failure (logging_strategy.md
                # "AI Context Buffer").
                rag_prompt = self._build_system_prompt(description, include_rag=True, backend=backend_name)
                recent_context = "\n".join(logger.get_context().splitlines()[-20:])
                if recent_context:
                    rag_prompt += (
                        "\n\nHISTORIAL DE EJECUCION RECIENTE (para depurar el intento anterior fallido):\n"
                        f"{recent_context}\n"
                    )
                retry = self._call_llm(
                    rag_prompt, user_msg,
                    backend=backend_name, llm=llm,
                    session_id=session_id, meta=run_meta, attempt=2,
                )
                if "error" in retry:
                    logger.error("circuit_synthesizer", f"session={session_id} attempt=2 LLM error: {retry['error']}")
                    snippet = extract_json_text(raw_content) or raw_content
                    return {
                        "error": f"Crash decoding JSON: {je}. Respuesta: {(snippet or '(vacio)')[:200]}..."
                    }
                raw_content = retry.get("content", "")
                try:
                    data = parse_json_object(raw_content)
                except json.JSONDecodeError as je2:
                    logger.error("circuit_synthesizer", f"session={session_id} attempt=2 JSON invalido: {je2}")
                    snippet = extract_json_text(raw_content) or raw_content
                    return {
                        "error": f"Crash decoding JSON: {je2}. Respuesta: {(snippet or '(vacio)')[:200]}..."
                    }

            # Extraer la lista de componentes desde la clave "circuit"
            components = data.get("circuit", data)
            
            if isinstance(components, dict):
                # Fallback si no retornó {"circuit": [...]} sino el array directo (raro con json_object)
                for k, v in components.items():
                    if isinstance(v, list):
                        components = v
                        break
                        
            if not isinstance(components, list):
                return {"error": "Formato inesperado: Se esperaba una lista de componentes en 'circuit'."}

            # Inyectar atributos físicos desde la base de datos de pinouts
            for comp in components:
                val = str(comp.get("value", ""))
                if val in self.pinouts_db:
                    db_entry = self.pinouts_db[val]
                    if "symbol" in db_entry and not comp.get("symbol"):
                        comp["symbol"] = db_entry["symbol"]
                    if "footprint" in db_entry and not comp.get("footprint"):
                        comp["footprint"] = db_entry["footprint"]

            self._normalize_unconnected_pins(components)

            logger.ai_review(
                "circuit_synthesizer",
                f"session={session_id} generado OK: {len(components)} componentes",
            )
            return {
                "status": "ok",
                "components": components,
                "session_id": session_id,
                "log_path": result.get("log_path"),
                "session_dir": result.get("session_dir"),
                "backend": backend_name,
                "ab_variant": self.ab_variant,
            }

        except Exception as e:
            logger.error("circuit_synthesizer", f"session={session_id} crash: {e}")
            return {"error": f"Crash: {str(e)}"}
