import json
import re
from typing import Callable, Any
from core.logger import logger
from knowledge.context_budget import ContextBudget, estimate_history_tokens
from knowledge.llm_types import StreamChunk

_STEWARD_SYSTEM_PROMPT = """Eres el 'PulseLab Circuit Steward', un agente inteligente experto en diseño de circuitos electrónicos.
Tu objetivo final es traducir las peticiones del usuario a una topología de circuito en un formato JSON estricto.

HABILIDADES (SKILLS) DISPONIBLES:

1. BÚSQUEDA DE CONOCIMIENTO:
Si no conoces con certeza el pinout de un IC, módulo o microcontrolador, DEBES buscarlo usando `search_knowledge`:
<call_skill name="search_knowledge">NOMBRE DEL COMPONENTE O REGLA</call_skill>

REGLAS DE BÚSQUEDA Y COMPONENTES GENÉRICOS:
- Haz búsquedas SOLO para ICs, microcontroladores o módulos complejos (ej: ESP32-S3, SSD1306, PN532, CC1101).
- NO busques pinouts para componentes pasivos o elementos genéricos como pulsadores, resistores, capacitores o conectores de expansión.

2. CONSTRUCCIÓN ITERATIVA DEL CIRCUITO (¡RECOMENDADO!):
Puedes ir construyendo el circuito paso a paso agregando uno o varios componentes a la vez. Esto evita errores de truncamiento y permite mayor precisión.
Usa la habilidad `add_components` enviando un objeto JSON o una Lista JSON de componentes:
<call_skill name="add_components">
[
  {"etype": "MCU", "value": "ESP32-S3", "label": "U1", "pins": {"1": "3V3", "2": "GND"}},
  {"etype": "C", "value": "100nF", "label": "C1", "n1": "3V3", "n2": "GND"}
]
</call_skill>

3. FINALIZAR CIRCUITO:
Cuando hayas agregado todos los componentes necesarios al Scratchpad y el circuito esté completo, finalízalo con:
<call_skill name="finish_circuit">listo</call_skill>

REGLAS DE FORMATO DE COMPONENTES:
Cada componente debe ser un objeto con:
- "etype": "R" (resistencia), "C" (cap), "L" (ind), "V" (fuente), "S" (sw), "GND" (tierra), o "IC", "MCU".
- "value": Valor NUMÉRICO real para pasivos o string para nombre de ICs (ej. "10k", "100nF", "ESP32-S3").
- "label": Etiqueta descriptiva corta (ej: "U1", "R1", "C1").
- "n1", "n2": Nombres de nodos (strings) para componentes de 2 pines (R, C, L, V, S). 'GND' es obligatorio para la referencia.
- "pins": (SOLO PARA IC/MCU) Un objeto que mapea el NÚMERO del pad (string, ej. "1", "2") al nombre de la red. Ej: {"1": "VCC", "2": "GND", "3": "I2C_SDA"}.
- "unconnected_pins": (OPCIONAL, SOLO PARA IC/MCU) Array de números de pin (strings) que se dejan libres A PROPÓSITO.
- "symbol": (SOLO PARA IC/MCU) Símbolo KiCad extraído del contexto (si aplica).
- "footprint": (SOLO PARA IC/MCU) Footprint KiCad extraído del contexto (si aplica).

FIDELIDAD DE PINES (IC/MCU) — OBLIGATORIO:
- Si el sistema te devolvió la tabla de pines completa de un componente a través de `search_knowledge`, tu respuesta debe dar cuenta de TODOS esos pines.
"""

_MAX_FULL_PINOUT_MATCHES = 1
_MAX_LISTED_MATCHES = 2


def strip_think_tags(text: str) -> str:
    """Strips reasoning <think>...</think> tags from text to keep history token-clean."""
    if not text:
        return ""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'<think>.*$', '', cleaned, flags=re.DOTALL)
    return cleaned.strip()


class CircuitScratchpad:
    """Tracks component status, pinout resolutions, accumulated circuit, and agent synthesis phase."""
    def __init__(self, prompt: str):
        self.prompt = prompt
        self.resolved_pinouts: dict[str, dict] = {}
        self.generic_components: set[str] = set()
        self.search_history: list[str] = []
        self.circuit: list[dict] = []
        self.phase: str = "RESEARCH"  # RESEARCH | SYNTHESIS

    def record_search(self, term: str, matches: list) -> bool:
        term_norm = term.strip().lower()
        self.search_history.append(term_norm)
        if matches:
            first_key, entry = matches[0]
            self.resolved_pinouts[term_norm] = entry
            return True
        else:
            self.generic_components.add(term_norm)
            return False

    def add_components(self, raw_data: Any) -> tuple[int, list[str]]:
        """Añade uno o varios componentes al circuito acumulado."""
        items = raw_data if isinstance(raw_data, list) else [raw_data]
        added_count = 0
        warnings = []
        for item in items:
            if not isinstance(item, dict):
                warnings.append(f"Elemento ignorado por no ser un objeto JSON: {item}")
                continue
            if "etype" not in item and "type" in item:
                item["etype"] = item.pop("type")
            if "etype" not in item:
                item["etype"] = "IC" if "pins" in item else "R"
            if "label" not in item:
                item["label"] = f"{item['etype']}{len(self.circuit) + 1}"
            self.circuit.append(item)
            added_count += 1
        if self.circuit:
            self.phase = "SYNTHESIS"
        return added_count, warnings

    def get_summary(self) -> str:
        res_keys = ", ".join(self.resolved_pinouts.keys()) or "Ninguno"
        gen_keys = ", ".join(self.generic_components) or "Ninguno"
        
        comp_summary_items = []
        for c in self.circuit[-10:]: # últimos 10
            lbl = c.get("label", "?")
            val = c.get("value", "")
            etype = c.get("etype", "")
            comp_summary_items.append(f"{lbl} ({val or etype})")
        comp_str = ", ".join(comp_summary_items) or "Ninguno"
        if len(self.circuit) > 10:
            comp_str = f"...(+{len(self.circuit)-10} anteriores), " + comp_str

        return (
            f"[SCRATCHPAD DE ESTADO]\n"
            f"- Fase Actual: {self.phase}\n"
            f"- Pinouts Resueltos: {res_keys}\n"
            f"- Elementos Genéricos: {gen_keys}\n"
            f"- Componentes Acumulados ({len(self.circuit)} total): [{comp_str}]"
        )


class CircuitStewardAgent:
    def __init__(self, synthesizer: Any, max_turns: int = 16):
        self.synth = synthesizer
        self.max_turns = max_turns
        self._budget: ContextBudget | None = None

    def _get_budget(self) -> ContextBudget:
        if self._budget is None:
            try:
                backend_name = self.synth._resolve_backend()[0]
                self._budget = ContextBudget.from_backend(backend_name)
            except Exception:
                self._budget = ContextBudget(num_ctx=131072, num_predict=16384)
            logger.info(
                "steward_agent",
                f"Context budget: {self._budget.history_budget_tokens} tokens "
                f"(ctx={self._budget.num_ctx}, predict={self._budget.num_predict})",
            )
        return self._budget

    def run_agent_loop(
        self,
        prompt: str,
        session_id: str,
        history: list[dict],
        on_chunk: Callable[[StreamChunk], None] | None = None,
        on_turn_end: Callable[[int, str], None] | None = None,
    ) -> dict:
        """
        Executes a multi-turn agent loop with Scratchpad & reasoning-free history.
        Supports stateful iterative component building via skills.
        """
        scratchpad = CircuitScratchpad(prompt)

        if not history:
            history.append({"role": "system", "content": _STEWARD_SYSTEM_PROMPT})
            history.append({"role": "user", "content": prompt})

        seen_skill_lookups: set[str] = set()
        budget = self._get_budget()

        turn = 0
        while turn < self.max_turns:
            turn += 1

            if budget.should_compact(history):
                before = len(history)
                history[:] = budget.compact(history)
                utilization = budget.utilization(history)
                logger.info(
                    "steward_agent",
                    f"[Turn {turn}] Compacted: {before} → {len(history)} msgs "
                    f"(utilization {utilization:.0%})",
                )

            token_est = estimate_history_tokens(history)
            if on_turn_end:
                on_turn_end(turn, f"INFERRING ({token_est} tok est, {budget.utilization(history):.0%} budget)")

            backend_name, llm = self.synth._resolve_backend()
            if not getattr(llm, 'available', True):
                return {"error": f"LLM backend '{backend_name}' no disponible."}

            sys_prompt = history[0]["content"]
            current_history = history[1:-1] if len(history) > 2 else None
            last_user_msg = history[-1]["content"] if history[-1]["role"] == "user" else "Continúa."
            
            result = llm.chat_stream(
                system=sys_prompt,
                user=last_user_msg,
                history=current_history,
                json_mode=False,
                session_id=session_id,
                caller="steward_agent",
                on_chunk=on_chunk
            ) if on_chunk else llm.chat(
                system=sys_prompt,
                user=last_user_msg,
                history=current_history,
                json_mode=False,
                session_id=session_id,
                caller="steward_agent"
            )

            if "error" in result:
                return result

            content = result.get("content", "")

            from knowledge.llm_json import llm_output_truncated
            if llm_output_truncated(result):
                done_reason = result.get("done_reason", "unknown")
                logger.warning(
                    "steward_agent",
                    f"[Turn {turn}] Output truncated (done_reason={done_reason}), "
                    f"history={estimate_history_tokens(history)} tok",
                )
                if scratchpad.circuit:
                    # Si ya tenemos componentes acumulados en el scratchpad, podemos usarlos
                    if on_turn_end:
                        on_turn_end(turn, "DONE (recovered from scratchpad)")
                    return {
                        "status": "ok",
                        "components": scratchpad.circuit,
                        "backend": result.get("backend"),
                        "turns": turn,
                        "recovered": True
                    }
                if turn < self.max_turns:
                    if content:
                        history.append({"role": "assistant", "content": content})
                    history.append({
                        "role": "user",
                        "content": (
                            "Tu respuesta fue TRUNCADA. Usa la habilidad `<call_skill name=\"add_components\">` "
                            "para ir agregando componentes de pocos en pocos al Scratchpad."
                        ),
                    })
                    continue

            clean_content = strip_think_tags(content)
            if clean_content:
                history.append({"role": "assistant", "content": clean_content})

            # 1. Check for Skill Calls (search_knowledge, add_components, finish_circuit)
            skill_match = re.search(r'<call_skill\s+name="([^"]+)">([\s\S]*?)</call_skill>', content)
            if skill_match:
                skill_name = skill_match.group(1).strip()
                skill_body = skill_match.group(2).strip()

                if on_turn_end:
                    on_turn_end(turn, f"SKILL_CALL: {skill_name}")

                if skill_name in ("add_components", "add_component"):
                    from knowledge.llm_json import parse_json_object
                    try:
                        parsed = parse_json_object(skill_body)
                        if isinstance(parsed, dict):
                            if "components" in parsed:
                                parsed = parsed["components"]
                            elif "circuit" in parsed:
                                parsed = parsed["circuit"]
                        added, warnings = scratchpad.add_components(parsed)
                        msg = f"SYSTEM_SKILL_RESPONSE: Se añadieron {added} componente(s) al circuito exitosamente."
                        if warnings:
                            msg += "\nAdvertencias: " + "; ".join(warnings)
                    except Exception as e:
                        msg = f"SYSTEM_SKILL_ERROR: Fallo al parsear JSON de componentes ({e}). Pasa un objeto o lista JSON bien formado."
                    
                    sp_info = scratchpad.get_summary()
                    history.append({"role": "user", "content": f"{msg}\n\n{sp_info}\n\nContinúa agregando componentes o usa `<call_skill name=\"finish_circuit\">listo</call_skill>` si terminaste."})
                    continue

                elif skill_name == "finish_circuit":
                    if on_turn_end:
                        on_turn_end(turn, "DONE")
                    return {
                        "status": "ok",
                        "components": scratchpad.circuit,
                        "backend": result.get("backend"),
                        "turns": turn
                    }

                elif skill_name == "search_knowledge":
                    skill_arg = skill_body
                    lookup_key = skill_arg.strip().lower()
                    seen_skill_lookups.add(lookup_key)

                    matches = self.synth._match_pinouts(skill_arg)
                    scratchpad.record_search(skill_arg, matches)

                    if not matches:
                        rag_results = self.synth.rag.query(skill_arg, top_k=3, chunk_type="concept")
                        if rag_results:
                            resp_text = "Resultados de conocimiento general:\n"
                            for r in rag_results:
                                resp_text += f"- {r['data'].get('name', 'Info')}: {r['data'].get('content', '')}\n"
                        else:
                            resp_text = (
                                f"No se encontró información en la base de conocimientos para: '{skill_arg}'. "
                                "Procede a agregar los componentes al circuito con `add_components`."
                            )
                    else:
                        resp_text = "Resultados de pinouts encontrados:\n"
                        shown = matches[:_MAX_LISTED_MATCHES]
                        for i, (key, entry) in enumerate(shown):
                            compact = self.synth._compact_pinout(entry, full=(i < _MAX_FULL_PINOUT_MATCHES))
                            resp_text += f"--- {key} ---\n{json.dumps(compact, indent=2, ensure_ascii=False)}\n"

                    sp_info = scratchpad.get_summary()
                    history.append({
                        "role": "user",
                        "content": f"SYSTEM_SKILL_RESPONSE:\n{resp_text}\n\n{sp_info}\n\n(Puedes hacer otra búsqueda, añadir componentes con `add_components` o finalizar con `finish_circuit`)."
                    })
                    continue
                else:
                    history.append({"role": "user", "content": f"SYSTEM_SKILL_ERROR: Habilidad desconocida '{skill_name}'"})
                    continue

            # 2. Backwards compatibility: Check if the model generated the final circuit in a raw JSON block
            if '"circuit"' in content and ("{" in content and "[" in content):
                from knowledge.llm_json import parse_llm_result
                try:
                    data = parse_llm_result(content, result.get("thinking", ""))
                    if "circuit" in data:
                        scratchpad.add_components(data["circuit"])
                        if on_turn_end:
                            on_turn_end(turn, "DONE")
                        return {"status": "ok", "components": scratchpad.circuit, "backend": result.get("backend"), "turns": turn}
                except Exception as e:
                    history.append({"role": "user", "content": f"El JSON generado es inválido: {e}. Usa `<call_skill name=\"add_components\">` para agregar componentes limpiamente."})
                    continue

            sp_info = scratchpad.get_summary()
            history.append({
                "role": "user",
                "content": f"No detecté una llamada a skill.\n{sp_info}\nUsa `<call_skill name=\"add_components\">` para añadir componentes, o `<call_skill name=\"finish_circuit\">` para concluir."
            })

        if scratchpad.circuit:
            return {"status": "ok", "components": scratchpad.circuit, "backend": "fallback_scratchpad", "turns": turn}

        return {"error": f"Se alcanzó el límite máximo de {self.max_turns} turnos sin un resultado válido."}