"""
knowledge/semantic_reviewer.py
==============================
Agente LLM para análisis semántico de circuitos (DRC basado en IA).
Detecta problemas de diseño como GNDs aislados, condensadores de
desacople faltantes, pines flotantes, etc.

Exports:
  - SemanticAIAgent:   Clase legacy (acepta un CircuitGraph directo).
  - SemanticReviewer:  Clase nueva (acepta JSON string de netlist).
"""

import json
from typing import Dict, Any

from knowledge.pulse_config import cfg
from knowledge.llm_backends import get_backend_client, resolve_backend_name
from knowledge.llm_client import get_llm_client
from knowledge.llm_json import llm_output_truncated, parse_llm_result
from core.logger import logger


_SYSTEM_PROMPT = """
Eres un ingeniero electrónico experto revisando una Netlist de PulseLab Forge.
El formato que recibirás detalla componentes, su tipo y a qué nodos conectan (n1, n2 o pines numéricos).

REGLAS DE DISEÑO ESTRICTAS (AI DRC):
1. '0' es la tierra de simulación SPICE. 'GND' es la malla de masa física en KiCad.
   Si un componente está conectado a '0', físicamente quedará AISLADO de 'GND' a menos que haya un alias. Falla siempre si existen ambos y no están alías.
2. Los circuitos integrados (MCU, ICs) necesitan condensadores de desacople de 100nF cerca de los pines VCC/GND.
3. El terminal negativo de una fuente de voltaje (V) DEBE conectarse normalmente a GND o 0 para cerrar el circuito.
4. Cuidado con los pines flotantes en microcontroladores (ej ESP8266 EN, RST).
5. ESP32 EN necesita pull-up 10k a 3.3V. GPIO0 (BOOT) debe poder ir a GND para flash mode.
6. Diseños USB-UART deben incluir nets USB_D+ y USB_D- además de MCU_TX/MCU_RX cruzados correctamente.
7. CH340 TXD conecta a RX del MCU; CH340 RXD conecta a TX del MCU (crossover).

Deberás analizar el circuito y responder ÚNICAMENTE en formato JSON estricto con la siguiente estructura, sin texto adicional:
{
    "issues": [
        {"msg": "Descripción del problema detectado...", "severity": "warning|critical", "proposal": "Acción recomendada..."}
    ]
}
"""


class SemanticAIAgent:
    """
    Agente LLM para analizar la semántica del circuito (rutas lógicas fallidas,
    GNDs aislados, condensadores de desacople faltantes, etc.)
    Usa el LLMClient unificado con health check y retry.
    """
    def __init__(self):
        self.llm = get_llm_client()
        self.system_prompt = _SYSTEM_PROMPT

    def analyze_circuit(self, graph) -> Dict[str, Any]:
        if not self.llm.available:
            return {"error": "Servicio LLM no disponible. ¿Está corriendo Ollama?"}

        # Preparar data
        netlist_desc = "PulseLab Netlist:\n"
        for c in graph.components:
            pins_desc = f"n1={c.n1}, n2={c.n2}" if not c.pins else f"pins={c.pins}"
            netlist_desc += f"- {c.uid} ({c.etype}): value={c.value}, {pins_desc}\n"

        if not graph.components:
            return {"issues": []}

        logger.ai_review("semantic_reviewer", f"analyze_circuit() {len(graph.components)} componentes")

        result = self._chat_review(netlist_desc, session_id=None, meta=None)

        if "error" in result:
            logger.error("semantic_reviewer", f"analyze_circuit() LLM error: {result['error']}")
            return result

        try:
            data = parse_llm_result(result.get("content", ""), result.get("thinking", ""))
            issues = data.get("issues", [])
            critical = sum(1 for i in issues if i.get("severity") == "critical")
            logger.ai_review(
                "semantic_reviewer",
                f"analyze_circuit() {len(issues)} issues ({critical} critical)",
            )
            return {"status": "ok", "issues": issues}
        except json.JSONDecodeError:
            logger.error("semantic_reviewer", f"analyze_circuit() JSON invalido: {result['content'][:100]}")
            return {"error": f"LLM devolvió JSON inválido: {result['content'][:200]}..."}


class SemanticReviewer:
    """
    Variante que acepta un JSON string de netlist en lugar de un CircuitGraph.
    Usada desde el ForgeController donde el graph ya está serializado.

    Session 4d: routes via `llm_backends.resolve_backend_name(task="review")`
    instead of always using the primary client directly, so `Pulse_cfg.json`'s
    `llm.routing.review_backend` (and `--review-backend` in the validation
    harness) can send review traffic to `atomic` (fast JSON, think=off) while
    synthesis stays on `primary` (long-context reasoning) — see
    docs/calibration_forge/llm_output_pipeline.md §Session 4d.
    """
    def __init__(self, backend: str = "auto"):
        self.backend_pref = backend
        self.backend_name, self.llm = self._resolve_backend()
        self.system_prompt = _SYSTEM_PROMPT

    def _resolve_backend(self) -> tuple[str, Any]:
        name = resolve_backend_name(task="review", prefer=self.backend_pref)
        return name, get_backend_client(name)

    def _chat_review(
        self,
        netlist_desc: str,
        *,
        session_id: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        max_tokens = int(cfg("llm.agents.semantic_reviewer.max_tokens", 8192))
        return self.llm.chat(
            system=self.system_prompt,
            user=netlist_desc,
            temperature=float(cfg("llm.agents.semantic_reviewer.temperature", 0.1)),
            max_tokens=max_tokens,
            json_mode=True,
            disable_thinking=True,
            caller="semantic_reviewer",
            session_id=session_id,
            meta={**(meta or {}), "backend": self.backend_name},
        )

    def review_netlist(
        self,
        circuit_json: str,
        *,
        session_id: str | None = None,
        meta: dict | None = None,
    ) -> Dict[str, Any]:
        """Revisa un circuito a partir de su representación JSON serializada."""
        if not self.llm.available:
            return {"error": "Servicio LLM no disponible. ¿Está corriendo Ollama?"}

        try:
            data = json.loads(circuit_json)
        except json.JSONDecodeError:
            return {"error": "JSON de circuito inválido."}

        components = data.get("components", [])
        if not components:
            return {"issues": []}

        # Formatear netlist para el LLM
        netlist_desc = "PulseLab Netlist:\n"
        for c in components:
            pins = c.get("pins", {})
            if pins:
                pins_desc = f"pins={pins}"
            else:
                pins_desc = f"n1={c.get('n1', '?')}, n2={c.get('n2', '?')}"
            netlist_desc += f"- {c.get('uid', '?')} ({c.get('etype', '?')}): value={c.get('value', 0)}, {pins_desc}\n"

        logger.ai_review("semantic_reviewer", f"review_netlist() {len(components)} componentes")

        result = self._chat_review(netlist_desc, session_id=session_id, meta=meta)

        if "error" in result:
            logger.error("semantic_reviewer", f"review_netlist() LLM error: {result['error']}")
            return {**result, "backend": self.backend_name}

        if llm_output_truncated(result):
            reason = result.get("done_reason") or "unknown"
            logger.error(
                "semantic_reviewer",
                f"review_netlist() truncado (done_reason={reason})",
            )
            return {"error": f"LLM truncado (done_reason={reason})", "backend": self.backend_name}

        try:
            resp_data = parse_llm_result(result.get("content", ""), result.get("thinking", ""))
            issues = resp_data.get("issues", [])
            critical = sum(1 for i in issues if i.get("severity") == "critical")
            logger.ai_review(
                "semantic_reviewer",
                f"review_netlist() {len(issues)} issues ({critical} critical)",
            )
            return {"status": "ok", "issues": issues, "backend": self.backend_name}
        except json.JSONDecodeError:
            logger.error("semantic_reviewer", f"review_netlist() JSON invalido: {result['content'][:100]}")
            return {
                "error": f"LLM devolvió JSON inválido: {result['content'][:200]}...",
                "backend": self.backend_name,
            }
