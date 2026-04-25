"""
knowledge/circuit_synthesizer.py
=================================
Agente LLM para Generación de Circuitos a partir de lenguaje natural.
Traduce descripciones textuales en una topología (Netlist JSON)
que PulseLab Forge puede renderizar y simular.
"""

import os
import json

class CircuitSynthesizer:
    def __init__(self):
        try:
            from openai import OpenAI
            # El usuario se quedó sin tokens, usamos Ollama (qwen2.5:3b) de forma predeterminada
            self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
            self.model = "qwen2.5:3b"
            self.is_local = True
        except ImportError:
            self.client = None

        self.system_prompt = """
Eres el 'PulseLab Circuit Engine'.
Tu tarea es convertir descripciones de circuitos en una lista de componentes en formato JSON estricto.
Esa lista se usará en `create_circuit_json()`.

FORMATO REQUERIDO DE CADA COMPONENTE:
{
    "etype": "R" | "C" | "L" | "V" | "S" | "MCU" | "IC",
    "value": "Valor numérico o ID string",
    "n1": "Nodo terminal 1 (string, ej: VCC, IN, GND)",
    "n2": "Nodo terminal 2 (string, ej: GND, OUT)",
    "label": "Etiqueta opcional",
    "footprint_id": "Opcional. Ej: Package_QFP:LQFP-48_7x7mm_P0.5mm"
}

REGLAS ESTRICTAS:
1. Devuelve ÚNICAMENTE un array JSON, nada más. Sin bloques markdown (```json ... ```).
2. Usa 'GND' para la tierra.
3. Asegúrate que los circuitos estén cerrados lógicamente (ej: fuente V entre VCC y GND).
4. Para filtros RC/RLC, usa nodos intermedios con sentido.

Ejemplo para filtro RC pasabajos:
[
  {"etype": "V", "value": 5.0, "n1": "IN", "n2": "GND", "label": "Vin"},
  {"etype": "R", "value": 1000, "n1": "IN", "n2": "OUT", "label": "R1 1k"},
  {"etype": "C", "value": 0.000001, "n1": "OUT", "n2": "GND", "label": "C1 1uF"}
]
"""

    def generate_circuit_json(self, description: str) -> dict:
        if not self.client:
            return {"error": "OpenAI no disponible. Revisa tus dependencias."}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Genera este circuito: {description}"}
                ],
                max_tokens=1500,
                temperature=0.2,
                response_format={ "type": "json_object" } if not self.is_local else None
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
                
            data = json.loads(content)
            # If wrapped in a dictionary, extract the list
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        data = v
                        break
            
            return {"status": "ok", "components": data}
            
        except Exception as e:
            return {"error": str(e)}
