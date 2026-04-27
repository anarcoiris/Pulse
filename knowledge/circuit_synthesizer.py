"""
knowledge/circuit_synthesizer.py
=================================
Agente LLM para Generación de Circuitos a partir de lenguaje natural.
Traduce descripciones textuales en una topología (Netlist JSON)
que PulseLab Forge puede renderizar y simular.
"""

import os
import json
import re

class CircuitSynthesizer:
    def __init__(self):
        try:
            from openai import OpenAI
            # El usuario se quedó sin tokens, usamos Ollama (qwen2.5:3b) de forma predeterminada
            self.client = OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
            self.model = "qwen2.5:3b"
            self.is_local = True
        except ImportError:
            self.client = None

        self.system_prompt = """
Eeres el 'PulseLab Circuit Engine', un experto en diseño electrónico.
Tu tarea es convertir descripciones de circuitos en una lista JSON estricta de componentes.

REGLAS DE FORMATO:
- Devuelve ÚNICAMENTE el array JSON. Sin explicaciones, sin markdown (```json).
- Cada componente debe ser un objeto con:
    "etype": "R" (resistencia), "C" (cap), "L" (ind), "V" (fuente), "S" (sw), "GND" (tierra).
    "value": Valor NUMÉRICO real (ej: 1000 en vez de "1k"). SIEMPRE usa floats o ints.
    "n1", "n2": Nombres de nodos (strings). 'GND' es obligatorio para la referencia.
    "label": Etiqueta descriptiva corta.

EJEMPLOS:

Usuario: "Divisor de tension con 5V y dos resistencias de 10k"
Respuesta:
[
  {"etype": "V", "value": 5.0, "n1": "VCC", "n2": "GND", "label": "V1"},
  {"etype": "R", "value": 10000.0, "n1": "VCC", "n2": "OUT", "label": "R1"},
  {"etype": "R", "value": 10000.0, "n1": "OUT", "n2": "GND", "label": "R2"}
]

Usuario: "Rectificador de media onda"
Respuesta:
[
  {"etype": "V", "value": 10.0, "n1": "AC", "n2": "GND", "label": "Vac"},
  {"etype": "S", "value": 0.0, "n1": "AC", "n2": "DC", "label": "D1"},
  {"etype": "R", "value": 1000.0, "n1": "DC", "n2": "GND", "label": "Load"}
]

Usuario: "Filtro RC pasabajos"
Respuesta:
[
  {"etype": "V", "value": 5.0, "n1": "IN", "n2": "GND", "label": "Vin"},
  {"etype": "R", "value": 1000.0, "n1": "IN", "n2": "OUT", "label": "R1"},
  {"etype": "C", "value": 0.000001, "n1": "OUT", "n2": "GND", "label": "C1"}
]

RECUERDA: Solo JSON. Sin texto adicional.
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
                temperature=0.1,
                response_format={ "type": "json_object" } if not self.is_local else None
            )
            
            raw_content = response.choices[0].message.content.strip()
            
            # Limpieza robusta de JSON
            # 1. Encontrar el bloque de array o objeto
            match = re.search(r'(\[.*\]|\{.*\})', raw_content, re.DOTALL)
            if not match:
                return {"error": f"La IA no devolvió un JSON válido. Respuesta: {raw_content[:100]}..."}
            
            content = match.group(1)
            
            # 2. Quitar comentarios estilo // o #
            content = re.sub(r'//.*', '', content)
            content = re.sub(r'#.*', '', content)
            
            # 3. Quitar comas sobrantes en arrays [a,b,] -> [a,b]
            content = re.sub(r',\s*\]', ']', content)
            content = re.sub(r',\s*\}', '}', content)
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError as je:
                # Intento final: quitar cualquier cosa que no sea parte del JSON
                # A veces el modelo pone texto después del bloque JSON
                return {"error": f"Crash: {je}. JSON sospechoso: {content[:100]}..."}
                
            # Extraer la lista de componentes
            if isinstance(data, dict):
                # Buscar cualquier campo que sea una lista
                for k, v in data.items():
                    if isinstance(v, list):
                        data = v
                        break
                # Si sigue siendo un dict, quizá el dict ES el componente (error del modelo)
                if isinstance(data, dict):
                    data = [data]
            
            if not isinstance(data, list):
                return {"error": "Formato inesperado: Se esperaba una lista de componentes."}
            
            return {"status": "ok", "components": data}
            
        except Exception as e:
            return {"error": f"Crash: {str(e)}"}
