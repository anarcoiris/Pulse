"""
knowledge/firmware_synthesizer.py
=================================
Agente LLM para Mapeo e Inyección Cross-Domain (HW -> SW).
Analiza el árbol de netlist del CircuitGraph para localizar MCU/IC
(ej. ESP8266) e inferir qué pines manejan actuadores/sensores, y 
posteriormente escribe el boilerplate de MicroPython `main.py`
que pone en marcha la red de Hardware creada.
"""

from pathlib import Path

from knowledge.pulse_config import cfg
from knowledge.llm_client import get_llm_client


class FirmwareSynthesizer:
    def __init__(self):
        self.llm = get_llm_client()

        self.prompt_template = """
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
"""

    def _extract_topology(self, graph) -> str:
        s = []
        for c in graph.components:
            pstr = str(c.pins) if c.pins else f"[{c.n1} -- {c.n2}]"
            s.append(f"TAG: {c.uid} | Categoria: {c.etype} | Value/Chip_ID: {c.value} | Label_UI: {c.label} | PINS_Conectados: {pstr}")
        return "\n".join(s)

    def generate_firmware(self, graph, output_file: str) -> dict:
        if not self.llm.available:
            return {"error": "Servicio LLM no disponible para Síntesis de Firmware. ¿Está corriendo Ollama?"}

        topo = self._extract_topology(graph)
        sys_prompt = self.prompt_template.format(topology_netlist=topo)

        result = self.llm.chat(
            system=sys_prompt,
            user="Genera el firmware MicroPython para esta topología de hardware.",
            temperature=float(cfg("llm.agents.firmware_synthesizer.temperature", 0.3)),
            max_tokens=int(cfg("llm.agents.firmware_synthesizer.max_tokens", 8192)),
            caller="firmware_synthesizer",
        )

        if "error" in result:
            return result

        try:
            code_out = result["content"]

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
