import re
import json
from pathlib import Path

class KiCadLayoutParser:
    """
    Parser especializado en archivos .kicad_pcb (Layouts reales).
    Extrae la posición física (X, Y) que un humano decidió para cada componente.
    """
    
    def __init__(self):
        # Mapeo de footprints comunes a tipos PulseLab
        self.type_patterns = {
            r'Resistor': 'R',
            r'Capacitor': 'C',
            r'Inductor': 'L',
            r'LED': 'S',
            r'Diode': 'S',
            r'Battery': 'V',
            r'VCC': 'V',
            r'GND': 'GND'
        }

    def parse_pcb(self, file_path: str) -> dict:
        content = Path(file_path).read_text(encoding="utf-8")
        
        # 1. Extraer Módulos/Huellas (Footprints)
        # (footprint "..." (at X Y ANGLE) ... (property "Reference" "REF") ...)
        footprints = re.findall(r'\(footprint\s+"([^"]+)"\s+\(at\s+([\d\.-]+)\s+([\d\.-]+).*?\(property\s+"Reference"\s+"([^"]+)"\)', content, re.DOTALL)
        
        components = []
        for fp_id, x, y, ref in footprints:
            # Determinar tipo por el ID de la huella
            etype = "IC"
            for pattern, code in self.type_patterns.items():
                if re.search(pattern, fp_id, re.I):
                    etype = code
                    break
            
            components.append({
                "uid": ref,
                "etype": etype,
                "grid_c": int(float(x) / 2.54), # Normalizar a pulgadas/10
                "grid_r": int(float(y) / 2.54),
                "orientation": "H", # TODO: Parsear ángulo
                "value": 0,
                "label": ref,
                "footprint": fp_id
            })
            
        # 2. Extraer Conexiones (Nets)
        # (segment (start X Y) (end X Y) (net ID))
        # Esto es más complejo, por ahora usaremos una aproximación basada en el bloque 'net'
        
        return {
            "source": Path(file_path).name,
            "components": components,
            "version": "1.2"
        }

if __name__ == "__main__":
    parser = KiCadLayoutParser()
    # test_file = "knowledge/data/raw_kicad/arduino_uno.kicad_pcb"
    # data = parser.parse_pcb(test_file)
    # print(json.dumps(data, indent=2))
