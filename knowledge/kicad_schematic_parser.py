import re
from pathlib import Path

class KiCadSchematicParser:
    """
    Parser especializado en archivos .kicad_sch (Esquemáticos).
    Extrae componentes lógicos y sus valores, además de contexto de diseño:
    title_block (título/comentarios), anotaciones de texto libres y nombres de
    red de label/hierarchical_label/global_label. Extraer la topología completa
    (nets) vía análisis geométrico de los cables (wires) sigue fuera de alcance;
    los nombres de red declarados explícitamente (labels) sí se capturan.
    """
    
    def __init__(self):
        from core.component_types import SYMBOL_TO_ETYPE_PATTERNS
        self.type_patterns = SYMBOL_TO_ETYPE_PATTERNS

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

        # 2. Extraer contexto de diseño: title_block, anotaciones de texto libres y
        # nombres de red (label/hierarchical_label/global_label). Esto es lo que le da
        # "intención de diseño" a un esquemático humano más allá de la lista de componentes.
        description = self._extract_description(content)
        notes = self._extract_notes(content)
        net_labels = self._extract_net_labels(content)

        return {
            "source": Path(file_path).name,
            "description": description,
            "notes": notes,
            "net_labels": net_labels,
            "components": components,
            "version": "1.1"
        }

    def _extract_description(self, content: str) -> str:
        """Extrae (title_block (title "...") (company "...") (comment N "...") ...)."""
        title = re.search(r'\(title\s+"([^"]*)"\)', content)
        company = re.search(r'\(company\s+"([^"]*)"\)', content)
        comments = re.findall(r'\(comment\s+\d+\s+"([^"]*)"\)', content)
        parts = [title.group(1) if title else "", company.group(1) if company else "", *comments]
        return " — ".join(p for p in parts if p)

    def _extract_notes(self, content: str) -> list:
        """Extrae anotaciones de texto libre (text "...") sueltas en el esquemático.

        Filtra notas triviales (1-2 caracteres, ej. "L"/"H" de tablas de verdad)
        que no aportan señal semántica, y deduplica preservando el orden.
        """
        raw_notes = re.findall(r'\(text\s+"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
        seen = set()
        notes = []
        for note in raw_notes:
            clean = note.replace("\\n", " ").replace("\\t", " ").strip()
            if len(clean) <= 2 or clean in seen:
                continue
            seen.add(clean)
            notes.append(clean)
        return notes[:40]

    def _extract_net_labels(self, content: str) -> list:
        """Extrae nombres de red de (label ...), (hierarchical_label ...) y (global_label ...).

        Estos son nombres semánticos (ej. I2C_SDA, USB_D+) que hoy se descartan por
        completo pese a ser señal de alto valor para retrieval.
        """
        seen = set()
        net_labels = []
        for pattern in (
            r'\(label\s+"([^"]+)"',
            r'\(hierarchical_label\s+"([^"]+)"',
            r'\(global_label\s+"([^"]+)"',
        ):
            for name in re.findall(pattern, content):
                if name not in seen:
                    seen.add(name)
                    net_labels.append(name)
        return net_labels[:60]
        
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

    _test_file = Path(__file__).resolve().parent / "data" / "raw_kicad" / "KiCad_kicad-source-mirror_usb_dp.kicad_sch"
    if _test_file.exists():
        result = parser.parse_schematic(str(_test_file))
        print(f"\n=== Self-test: {_test_file.name} ===")
        print(f"  components: {len(result['components'])}")
        print(f"  description: {result['description']}")
        print(f"  notes ({len(result['notes'])}): {result['notes'][:5]}")
        print(f"  net_labels ({len(result['net_labels'])}): {result['net_labels'][:8]}")
        assert "Antmicro" in result["description"], "title_block extraction failed"
        assert any("USB" in n or "Display port" in n for n in result["notes"]), "notes extraction failed"
        assert "USBSS1_RX_C_N" in result["net_labels"], "net_labels extraction failed"
        print("  Self-test: PASS")
    else:
        print(f"\n(Skipping self-test — {_test_file} not found)")
