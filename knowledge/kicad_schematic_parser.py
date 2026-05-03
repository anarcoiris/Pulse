import re
from pathlib import Path

class KiCadSchematicParser:
    """
    Parser especializado en archivos .kicad_sch (Esquemáticos).
    Extrae componentes lógicos y sus valores. Extraer la topología (nets) de 
    esquemáticos puros requiere análisis geométrico de los cables (wires), 
    por lo que nos enfocamos en los componentes y valores como base.
    """
    
    def __init__(self):
        # Mapeo de librerías comunes a tipos lógicos
        self.type_patterns = {
            r'Device:R': 'R',
            r'Device:C': 'C',
            r'Device:L': 'L',
            r'Device:LED': 'S',
            r'Device:D': 'S',
            r'Device:Battery': 'V',
            r'power:VCC': 'V',
            r'power:GND': 'GND'
        }

    def parse_schematic(self, file_path: str) -> dict:
        content = Path(file_path).read_text(encoding="utf-8")
        
        # 1. Extraer Símbolos (Componentes)
        # Buscar bloques de símbolos que contienen (lib_id "...") y propiedades Reference/Value
        # Un símbolo típico: (symbol (lib_id "Device:R") (at 127 88.9 0) ... (property "Reference" "R1" ...) (property "Value" "10k" ...) ...)
        
        # Como los bloques S-expression pueden tener saltos de línea y estar anidados, usaremos regex más flexibles.
        # Encontramos todos los bloques de symbol.
        symbol_blocks = re.findall(r'\(symbol\s+\(lib_id\s+"([^"]+)".*?\(property\s+"Reference"\s+"([^"]+)".*?\(property\s+"Value"\s+"([^"]+)"', content, re.DOTALL)
        
        components = []
        for lib_id, ref, value in symbol_blocks:
            etype = "IC"
            for pattern, code in self.type_patterns.items():
                if re.search(pattern, lib_id, re.I):
                    etype = code
                    break
            
            # Limpiar valor (ej: "10k" -> 10000.0)
            numeric_val = self._parse_value(value)
            
            components.append({
                "uid": ref,
                "etype": etype,
                "value": numeric_val,
                "value_raw": value,
                "label": ref,
                "lib_id": lib_id
            })
            
        return {
            "source": Path(file_path).name,
            "components": components,
            "version": "1.0"
        }
        
    def _parse_value(self, val_str: str) -> float:
        """Convierte strings como '10k', '4.7u', '100n' a floats reales."""
        val_str = val_str.lower().strip()
        # Eliminar unidades como F, H, Ohm, r
        val_str = re.sub(r'[fhohmr\u03a9]', '', val_str)
        
        multipliers = {
            'p': 1e-12,
            'n': 1e-9,
            'u': 1e-6,
            'm': 1e-3,
            'k': 1e3,
            'meg': 1e6,
            'g': 1e9
        }
        
        match = re.match(r'^([\d\.]+)([pnumkmeg]*)$', val_str)
        if match:
            num = float(match.group(1))
            mult = match.group(2)
            if mult in multipliers:
                num *= multipliers[mult]
            return num
            
        try:
            return float(val_str)
        except ValueError:
            return 0.0

if __name__ == "__main__":
    parser = KiCadSchematicParser()
    print("Parser de esquemáticos inicializado.")
