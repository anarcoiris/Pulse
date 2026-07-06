import re
import json
from pathlib import Path

class KiCadSchematicImporter:
    """
    Parsea archivos .kicad_sch (S-Expressions) y los convierte
    al formato CircuitGraph de PulseLab para entrenamiento.
    """
    
    def __init__(self):
        self.comp_map = {
            "R": "R", "Resistor": "R",
            "C": "C", "Capacitor": "C",
            "L": "L", "Inductor": "L",
            "D": "S", "Diode": "S", # Mapeamos diodo a Switch/Semiconductor por ahora
            "V": "V", "Battery": "V",
            "GND": "GND"
        }

    def parse_file(self, file_path: str) -> dict:
        content = Path(file_path).read_text(encoding="utf-8")
        
        # Extracción simplificada usando Regex (en lugar de un parser S-Exp completo)
        # Buscamos símbolos: (symbol (lib_id "Device:R") ... (at x y rev) ... (property "Reference" "R1") ...)
        symbols = re.findall(r'\(symbol\s+\(lib_id\s+"([^"]+)"\).*?\(at\s+([\d\.-]+)\s+([\d\.-]+).*?\(property\s+"Reference"\s+"([^"]+)"\)', content, re.DOTALL)
        
        components = []
        for lib_id, x, y, ref in symbols:
            etype_code = lib_id.split(":")[-1][0].upper()
            etype = self.comp_map.get(etype_code, "IC")
            
            components.append({
                "uid": ref,
                "etype": etype,
                "grid_c": int(float(x) / 2.54), # Normalizar a rejilla de 0.1 pulgadas
                "grid_r": int(float(y) / 2.54),
                "orientation": "H",
                "value": 0, # Necesitaríamos parsear el campo 'Value'
                "label": ref,
                "n1": "NET_?", # El ruteado en esquemáticos requiere parsear el bloque 'wire'
                "n2": "NET_?"
            })
            
        return {
            "version": "1.2",
            "components": components,
            "wires": [] # TODO: Parsear (wire (pts (at x1 y1) (at x2 y2)))
        }

if __name__ == "__main__":
    # Test (si existe algún archivo .kicad_sch cerca)
    importer = KiCadSchematicImporter()
    # print(importer.parse_file("ejemplo.kicad_sch"))
