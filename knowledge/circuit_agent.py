import json
import re
from typing import Callable, Any
from core.logger import logger
from knowledge.context_budget import ContextBudget, estimate_history_tokens
from knowledge.llm_types import StreamChunk

_STEWARD_SYSTEM_PROMPT = """Eres el 'PulseLab Circuit Steward', un agente inteligente experto en diseño de circuitos electrónicos.
Tu objetivo final es traducir las peticiones del usuario a una topología de circuito en un formato JSON estricto.

HABILIDADES (SKILLS) DISPONIBLES:
No tienes que adivinar los pines de los componentes. Si no conoces con certeza el pinout de un IC, módulo o microcontrolador, PUEDES y DEBES buscarlo usando la habilidad `search_knowledge`.
Para usar una habilidad, emite exactamente este formato XML y DETENTE:
<call_skill name="search_knowledge">NOMBRE DEL COMPONENTE O REGLA</call_skill>

Ejemplo:
<call_skill name="search_knowledge">A4988</call_skill>

El sistema interceptará tu mensaje y te responderá con la tabla de pines o la información relevante.
Puedes hacer tantas llamadas a `search_knowledge` como componentes complejos necesites investigar, pero hazlo de uno en uno o en turnos sucesivos.

GENERACIÓN DEL CIRCUITO:
Cuando tengas toda la información necesaria (o si la petición es tan sencilla que ya la sabes), y SÓLO ENTONCES, genera el circuito final.
Debes encerrar el circuito final en un bloque JSON que tenga exactamente la clave "circuit" en la raíz.

REGLAS DE FORMATO JSON:
- Devuelve ÚNICAMENTE un objeto JSON con una clave "circuit" que contenga una lista de componentes.
- Cada componente debe ser un objeto con:
    "etype": "R" (resistencia), "C" (cap), "L" (ind), "V" (fuente), "S" (sw), "GND" (tierra), o "IC", "MCU".
    "value": Valor NUMÉRICO real para pasivos o string para nombre de ICs (ej. "ESP32", "1000").
    "n1", "n2": Nombres de nodos (strings) para componentes de 2 pines (R, C, L, V, S). 'GND' es obligatorio para la referencia.
    "pins": (SOLO PARA IC/MCU) Un objeto que mapea el NÚMERO del pad (string, ej. "1", "2") al nombre de la red. Ej: {"1": "VCC", "2": "GND", "3": "I2C_SDA"}.
    "unconnected_pins": (OPCIONAL, SOLO PARA IC/MCU) Array de números de pin (strings) que existen físicamente pero se dejan libres A PROPÓSITO en este diseño.
    "label": Etiqueta descriptiva corta.
    "symbol": (SOLO PARA IC/MCU) Símbolo KiCad extraído del contexto (si se proporcionó).
    "footprint": (SOLO PARA IC/MCU) Footprint KiCad extraído del contexto (si se proporcionó).

FIDELIDAD DE PINES (IC/MCU) — OBLIGATORIO:
- Si el sistema te devolvió la tabla de pines completa de un componente a través de `search_knowledge`, tu respuesta debe dar cuenta de TODOS esos pines.
- Para cada pin físico que exista pero NO se use en el diseño, decláralo explícitamente en `pins` como "NC" o inclúyelo en `unconnected_pins`. NUNCA omitas un pin en silencio.

REGLAS DE DISEÑO:
- Los circuitos integrados necesitan condensadores de desacople de 100nF en VCC/GND.
- Las fuentes de voltaje de 2 pines (V) deben cerrar el circuito (ej n2="GND").

Una vez emitido el JSON final válido, el flujo terminará.
"""

# Cuantas coincidencias de search_knowledge se incluyen en el historial por llamada.
# Solo la primera va en detalle completo; el resto de aqui en adelante se omiten (antes
# se incluian TODAS, la primera completa y el resto parcial - eso duplicaba pinouts casi
# identicos de variantes del mismo componente, ej. "ESP32-S3" vs "ESP32-S3-WROOM-1", y era
# una de las mayores fuentes de crecimiento del historial).
_MAX_FULL_PINOUT_MATCHES = 1
_MAX_LISTED_MATCHES = 2


class CircuitStewardAgent:
    def __init__(self, synthesizer: Any, max_turns: int = 8):
        # We take a reference to CircuitSynthesizer to reuse its RAG and DB
        self.synth = synthesizer
        self.max_turns = max_turns
        # Context budget derived from the actual backend limits (token-based,
        # not char-based).  Created lazily on first call to run_agent_loop so
        # that backend_limits() is resolved after config is fully loaded.
        self._budget: ContextBudget | None = None

    def _get_budget(self) -> ContextBudget:
        if self._budget is None:
            try:
                backend_name = self.synth._resolve_backend()[0]
                self._budget = ContextBudget.from_backend(backend_name)
            except Exception:
                # Fallback: 96k context, 8k output
                self._budget = ContextBudget(num_ctx=98304, num_predict=8192)
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
        Executes a multi-turn agent loop.
        Updates `history` in-place.
        Returns the final JSON parsing result or error.
        """
        if not history:
            history.append({"role": "system", "content": _STEWARD_SYSTEM_PROMPT})
            history.append({"role": "user", "content": prompt})

        # Terminos de search_knowledge ya consultados en esta sesion (normalizado), para
        # no volver a volcar el mismo pinout completo si el modelo repite la busqueda.
        seen_skill_lookups: set[str] = set()

        budget = self._get_budget()

        turn = 0
        while turn < self.max_turns:
            turn += 1

            # ── Pre-turn compaction (mirrors Tiny Steward) ────────────
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

            # Resolve LLM client
            backend_name, llm = self.synth._resolve_backend()
            if not getattr(llm, 'available', True):
                return {"error": f"LLM backend '{backend_name}' no disponible."}

            # Convert history to the format expected by llm.chat
            sys_prompt = history[0]["content"]
            
            # Combine history messages for chat
            # Note: since llm.chat expects `system`, `user` and `history`, we pass it like this:
            current_history = history[1:-1] if len(history) > 2 else None
            last_user_msg = history[-1]["content"] if history[-1]["role"] == "user" else "Continúa."
            
            # Bypass generate_circuit_json and talk to LLM directly
            result = llm.chat_stream(
                system=sys_prompt,
                user=last_user_msg,
                history=current_history,
                json_mode=False, # We don't force JSON mode yet because it might use XML tools
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

            # ── Truncation detection (P1/P3 fix) ─────────────────────
            from knowledge.llm_json import llm_output_truncated
            if llm_output_truncated(result):
                done_reason = result.get("done_reason", "unknown")
                logger.warning(
                    "steward_agent",
                    f"[Turn {turn}] Output truncated (done_reason={done_reason}), "
                    f"history={estimate_history_tokens(history)} tok",
                )
                # If the truncated output looks like it contains a partial circuit,
                # ask the model to finish just the JSON in a new turn
                if '"circuit"' in content or '"etype"' in content:
                    history.append({"role": "assistant", "content": content})
                    history.append({
                        "role": "user",
                        "content": (
                            "Tu respuesta anterior fue TRUNCADA (superó el límite de tokens). "
                            "Por favor, genera el JSON completo del circuito de forma más concisa. "
                            "Omite explicaciones. Solo el JSON con clave 'circuit'."
                        ),
                    })
                    continue
                # Otherwise, return the truncation as an error
                return {
                    "error": f"Output truncado (done_reason={done_reason}) en turno {turn}",
                    "turns": turn,
                    "truncated": True,
                }

            history.append({"role": "assistant", "content": content})

            # 1. Check if the model generated the final circuit
            if '"circuit"' in content and ("{" in content and "[" in content):
                from knowledge.llm_json import parse_llm_result
                try:
                    data = parse_llm_result(content, result.get("thinking", ""))
                    if "circuit" in data:
                        if on_turn_end:
                            on_turn_end(turn, "DONE")
                        return {"status": "ok", "components": data["circuit"], "backend": result.get("backend"), "turns": turn}
                except Exception as e:
                    history.append({"role": "user", "content": f"El JSON generado es inválido: {e}. Por favor, corrígelo y devuelve sólo el JSON estricto."})
                    continue

            # 2. Check if the model called a skill
            skill_match = re.search(r'<call_skill\s+name="([^"]+)">([^<]+)</call_skill>', content)
            if skill_match:
                skill_name = skill_match.group(1)
                skill_arg = skill_match.group(2).strip()
                
                if on_turn_end:
                    on_turn_end(turn, f"SKILL_CALL: {skill_name}({skill_arg})")

                if skill_name == "search_knowledge":
                    lookup_key = skill_arg.strip().lower()
                    already_seen = lookup_key in seen_skill_lookups
                    seen_skill_lookups.add(lookup_key)

                    # Delegate to the synthesizer's RAG and pinout matcher
                    matches = self.synth._match_pinouts(skill_arg)
                    if not matches:
                        # Try a generic RAG query if it's not a pinout
                        rag_results = self.synth.rag.query(skill_arg, top_k=3, chunk_type="concept")
                        if rag_results:
                            resp_text = "Resultados de conocimiento general:\n"
                            for r in rag_results:
                                resp_text += f"- {r['data'].get('name', 'Info')}: {r['data'].get('content', '')}\n"
                        else:
                            resp_text = f"No se encontró información en la base de conocimientos para: {skill_arg}"
                    elif already_seen:
                        # Mismo termino ya buscado antes en esta sesion: no volver a inflar
                        # el historial con el mismo dump completo, solo confirmar que ya lo tiene.
                        keys = ", ".join(key for key, _ in matches[:_MAX_LISTED_MATCHES])
                        resp_text = (
                            f"Ya consultaste '{skill_arg}' en un turno anterior de esta misma sesión "
                            f"(coincidencias: {keys}). Usa los pines que ya te di antes; no hace falta "
                            "repetir la búsqueda."
                        )
                    else:
                        resp_text = "Resultados de pinouts encontrados:\n"
                        shown = matches[:_MAX_LISTED_MATCHES]
                        for i, (key, entry) in enumerate(shown):
                            compact = self.synth._compact_pinout(entry, full=(i < _MAX_FULL_PINOUT_MATCHES))
                            resp_text += f"--- {key} ---\n{json.dumps(compact, indent=2, ensure_ascii=False)}\n"
                        extra = len(matches) - len(shown)
                        if extra > 0:
                            resp_text += (
                                f"\n(+{extra} coincidencias adicionales omitidas por espacio; "
                                "pide un nombre más específico si ninguna de las anteriores es la correcta.)\n"
                            )
                    
                    history.append({"role": "user", "content": f"SYSTEM_SKILL_RESPONSE:\n{resp_text}\n\n(Puedes hacer otra llamada a skill o generar el JSON final si ya tienes todo lo necesario)."})
                else:
                    history.append({"role": "user", "content": f"SYSTEM_SKILL_ERROR: Habilidad desconocida '{skill_name}'"})
                
                continue

            # If no skill was called and no valid circuit JSON was found, prompt the model to continue or fix formatting
            history.append({"role": "user", "content": "No detecté una llamada a skill ni un bloque JSON válido con la clave 'circuit'. Si necesitas información, usa <call_skill name=\"search_knowledge\">. Si ya terminaste, devuelve el JSON."})

        return {"error": f"Se alcanzó el límite máximo de {self.max_turns} turnos sin un resultado válido."}