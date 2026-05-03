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

from knowledge.llm_client import get_llm_client


_SYSTEM_PROMPT = """
Eres un ingeniero electrónico experto revisando una Netlist de PulseLab Forge.
El formato que recibirás detalla componentes, su tipo y a qué nodos conectan (n1, n2 o pines numéricos).

REGLAS DE DISEÑO ESTRICTAS (AI DRC):
1. '0' es la tierra de simulación SPICE. 'GND' es la malla de masa física en KiCad.
   Si un componente está conectado a '0', físicamente quedará AISLADO de 'GND' a menos que haya un alias. Falla siempre si existen ambos y no están alías.
2. Los circuitos integrados (MCU, ICs) necesitan condensadores de desacople de 100nF cerca de los pines VCC/GND.
3. El terminal negativo de una fuente de voltaje (V) DEBE conectarse normalmente a GND o 0 para cerrar el circuito.
4. Cuidado con los pines flotantes en microcontroladores (ej ESP8266 EN, RST).

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

        result = self.llm.chat(
            system=self.system_prompt,
            user=netlist_desc,
            temperature=0.1,
            max_tokens=800,
        )

        if "error" in result:
            return result

        try:
            data = json.loads(result["content"])
            return {"status": "ok", "issues": data.get("issues", [])}
        except json.JSONDecodeError:
            return {"error": f"LLM devolvió JSON inválido: {result['content'][:100]}..."}


class SemanticReviewer:
    """
    Variante que acepta un JSON string de netlist en lugar de un CircuitGraph.
    Usada desde el ForgeController donde el graph ya está serializado.
    """
    def __init__(self):
        self.llm = get_llm_client()
        self.system_prompt = _SYSTEM_PROMPT

    def review_netlist(self, circuit_json: str) -> Dict[str, Any]:
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

        result = self.llm.chat(
            system=self.system_prompt,
            user=netlist_desc,
            temperature=0.1,
            max_tokens=800,
        )

        if "error" in result:
            return result

        try:
            resp_data = json.loads(result["content"])
            return {"status": "ok", "issues": resp_data.get("issues", [])}
        except json.JSONDecodeError:
            return {"error": f"LLM devolvió JSON inválido: {result['content'][:100]}..."}
