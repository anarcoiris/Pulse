"""
knowledge/firmware_synthesizer.py
=================================
Agente LLM para Mapeo e Inyección Cross-Domain (HW -> SW).
Analiza el árbol de netlist del CircuitGraph para localizar MCU/IC
(ej. ESP8266) e inferir qué pines manejan actuadores/sensores, y 
posteriormente escribe el boilerplate de MicroPython `main.py`
que pone en marcha la red de Hardware creada.
"""

import os
import json
from pathlib import Path

class FirmwareSynthesizer:
    def __init__(self):
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            
            if api_key:
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o"
                self.is_local = False
            else:
                self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
                self.model = "deepseek-coder:latest"
                self.is_local = True
        except ImportError:
            self.client = None

        self.prompt_template = \"\"\"
Eres el 'PulseLab Firmware Engine'.
Se te entregará la Topología de Hardware (Netlist Pura) de una placa IoT acabada de forjar.
TU TAREA es escribir un script `main.py` en MicroPython completo y funcional para el MCU extraído.

INSTRUCCIONES CLAVES:
1. Detecta qué MCU hay en la Netlist (Ej: ESP8266EX).
2. Deduce los GPIO conectando LEDs, Servos, Lecturas ADC, o Sensores en base a los PINS del Hardware.
3. Devuelve ÚNICAMENTE el código en MicroPython dentro de un bloque ```python ... ```.
4. Documenta los alias de los PINS utilizando el atributo "label" que el usuario haya dejado.
5. Inicia un bucle try/except KeyboardInterrupt básico si hay flujo repetitivo.

NETLIST DEL PRODUCTO DISEÑADO:
{topology_netlist}
\"\"\"

    def _extract_topology(self, graph) -> str:
        s = []
        for c in graph.components:
            pstr = str(c.pins) if c.pins else f"[{c.n1} -- {c.n2}]"
            s.append(f"TAG: {c.uid} | Categoria: {c.etype} | Value/Chip_ID: {c.value} | Label_UI: {c.label} | PINS_Conectados: {pstr}")
        return "\n".join(s)

    def generate_firmware(self, graph, output_file: str) -> dict:
        if not self.client:
            return {"error": "Librería OpenAI no disponible para Síntesis de Firmware."}

        topo = self._extract_topology(graph)
        sys_prompt = self.prompt_template.format(topology_netlist=topo)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": sys_prompt}],
                max_tokens=2048,
                temperature=0.3
            )
            code_out = response.choices[0].message.content
            
            # Limpiar bloque markdown
            lines = code_out.splitlines()
            py_lines = []
            capture = False
            for line in lines:
                if line.startswith("```python"):
                    capture = True
                    continue
                elif line.startswith("```") and capture:
                    break
                if capture:
                    py_lines.append(line)
            
            final_code = "\n".join(py_lines) if py_lines else code_out
            
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(final_code, encoding="utf-8")
            
            return {"status": "ok", "path": str(path), "bytes": len(final_code)}

        except Exception as e:
            return {"error": str(e)}
