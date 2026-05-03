"""
knowledge/circuit_synthesizer.py
=================================
Agente LLM para Generación de Circuitos a partir de lenguaje natural.
Traduce descripciones textuales en una topología (Netlist JSON)
que PulseLab Forge puede renderizar y simular.
"""

import json
import re

from knowledge.llm_client import get_llm_client
from knowledge.rag_engine import ElectronicsKnowledgeBase

class CircuitSynthesizer:
    def __init__(self):
        self.llm = get_llm_client()
        self.rag = ElectronicsKnowledgeBase()
        self.pinouts_db = self._load_pinouts()

        self.base_system_prompt = """
Eres el 'PulseLab Circuit Engine', un experto en diseño electrónico.
Tu tarea es convertir descripciones de circuitos en un JSON estricto.

REGLAS DE FORMATO:
- Devuelve ÚNICAMENTE un objeto JSON con una clave "circuit" que contenga una lista de componentes.
- Cada componente debe ser un objeto con:
    "etype": "R" (resistencia), "C" (cap), "L" (ind), "V" (fuente), "S" (sw), "GND" (tierra), o "IC", "MCU".
    "value": Valor NUMÉRICO real para pasivos o string para nombre de ICs (ej. "ESP32", "1000").
    "n1", "n2": Nombres de nodos (strings) para componentes de 2 pines (R, C, L, V, S). 'GND' es obligatorio para la referencia.
    "pins": (SOLO PARA IC/MCU) Un objeto que mapea el NÚMERO del pad (string, ej. "1", "2") al nombre de la red. Ej: {"1": "VCC", "2": "GND", "3": "I2C_SDA"}. REVISAR CUIDADOSAMENTE EL NÚMERO CORRECTO EN EL CONTEXTO.
    "label": Etiqueta descriptiva corta.
    "symbol": (SOLO PARA IC/MCU) Símbolo KiCad extraído del contexto.
    "footprint": (SOLO PARA IC/MCU) Footprint KiCad extraído del contexto.

EJEMPLOS ESTATICOS:
Usuario: "Un ESP32 conectado a una pantalla I2C y a un resistor pull-up a 3.3V"
Respuesta:
{
  "circuit": [
    {"etype": "V", "value": 3.3, "n1": "3.3V", "n2": "GND", "label": "V1"},
    {"etype": "MCU", "value": "ESP32-S3", "symbol": "RF_Module:ESP32-WROOM-32", "footprint": "RF_Module:ESP32-WROOM-32", "pins": {"2": "3.3V", "1": "GND", "33": "I2C_SDA", "36": "I2C_SCL"}, "label": "U1"},
    {"etype": "IC", "value": "SSD1306", "symbol": "Connector_Generic:Conn_01x04", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "pins": {"2": "3.3V", "1": "GND", "4": "I2C_SDA", "3": "I2C_SCL"}, "label": "OLED"},
    {"etype": "R", "value": 4700.0, "n1": "3.3V", "n2": "I2C_SDA", "label": "R_PULLUP_SDA"}
  ]
}

RECUERDA: Devuelve un JSON válido. Usa SIEMPRE "pins" para interconectar módulos complejos, NO uses "S" (switches) para eso.
"""

    def _load_pinouts(self):
        try:
            import os
            path = os.path.join(os.path.dirname(__file__), "pinouts_library.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _get_pinouts_context(self) -> str:
        if self.pinouts_db:
            return "\nLIBRERÍA DE PINOUTS HARDWARE:\n" + json.dumps(self.pinouts_db, indent=2) + "\n"
        return ""


    def generate_circuit_json(self, description: str) -> dict:
        if not self.llm.available:
            return {"error": "Servicio LLM no disponible. ¿Está corriendo Ollama?"}

        # 1. Recuperar contexto RAG (circuitos similares parseados previamente)
        dynamic_prompt = self.base_system_prompt
        dynamic_prompt += self._get_pinouts_context()
        rag_results = self.rag.query(description, top_k=2, chunk_type="circuit_example")
        
        if rag_results:
            dynamic_prompt += "\nEJEMPLOS DINÁMICOS RECUPERADOS:\n"
            for res in rag_results:
                circuit_data = res["data"].get("circuit", [])
                source = res.get("source", "Ejemplo")
                dynamic_prompt += f"\n- Contexto ({source}):\n"
                dynamic_prompt += json.dumps({"circuit": circuit_data}, indent=2) + "\n"

        result = self.llm.chat(
            system=dynamic_prompt,
            user=f"Genera este circuito: {description}",
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        if "error" in result:
            return result

        try:
            raw_content = result["content"].strip()
            
            # Limpiar posible markdown wrapper de codeblock a pesar de json_object
            if raw_content.startswith("```"):
                raw_content = re.sub(r'^```(json)?|```$', '', raw_content, flags=re.MULTILINE).strip()

            try:
                data = json.loads(raw_content)
            except json.JSONDecodeError as je:
                return {"error": f"Crash decoding JSON: {je}. Respuesta: {raw_content[:100]}..."}

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

            return {"status": "ok", "components": components}

        except Exception as e:
            return {"error": f"Crash: {str(e)}"}
