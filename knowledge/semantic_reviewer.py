import os
import json
from typing import Dict, Any, List

class SemanticAIAgent:
    """
    Agente LLM para analizar la semántica del circuito (rutas lógicas fallidas,
    GNDs aislados, condensadores de desacople faltantes, etc.)
    Usa OpenAI API o Ollama Local de fallback.
    """
    def __init__(self):
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            
            if api_key:
                # Prefer OpenAPI si hay API_KEY
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o"  # O gpt-4-turbo
                self.is_local = False
            else:
                # Fallback a Ollama en puerto 11434 por defecto
                self.client = OpenAI(
                    base_url="http://localhost:11434/v1",
                    api_key="ollama" # Requerido pero ignorado por Ollama
                )
                self.model = "deepseek-coder:latest" # o qwen2.5-coder
                self.is_local = True
                
        except ImportError:
            self.client = None
            self.model = None
            
        self.system_prompt = """
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

    def analyze_circuit(self, graph) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Librería 'openai' no instalada."}
            
        # Preparar data
        netlist_desc = "PulseLab Netlist:\n"
        for c in graph.components:
            pins_desc = f"n1={c.n1}, n2={c.n2}" if not c.pins else f"pins={c.pins}"
            netlist_desc += f"- {c.uid} ({c.etype}): value={c.value}, {pins_desc}\n"
            
        if not graph.components:
            return {"issues": []}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": netlist_desc}
                ],
                max_tokens=800,
                temperature=0.1,
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            return {"status": "ok", "issues": data.get("issues", [])}
            
        except Exception as e:
            return {"error": f"Error contactando al LLM ({'Local' if self.is_local else 'Cloud'}): {str(e)}"}
