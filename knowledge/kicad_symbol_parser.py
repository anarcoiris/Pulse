"""
knowledge/kicad_symbol_parser.py
=================================
Parser especializado en archivos ``.kicad_sym`` (formato "packed", KiCad 6+):
un único archivo ``(kicad_symbol_lib ...)`` que contiene N símbolos de nivel
superior ``(symbol "Nombre" ...)``, cada uno con 0..N sub-unidades anidadas
``(symbol "Nombre_U_S" ...)`` que agrupan pines por unidad/alternativa (para
partes multi-unidad como amplificadores operacionales duales/cuádruples,
donde cada mitad del chip es una "unidad" con su propio subconjunto de pines).

Por cada símbolo top-level se extrae:
  - ``lib_id``: nombre del símbolo (ej. "ESP32-WROOM-32").
  - ``library``: nombre del archivo fuente sin extensión (ej. "RF_Module").
  - ``footprint_default`` / ``datasheet`` / ``description`` / ``keywords``:
    propiedades KiCad (``property "Footprint"/"Datasheet"/"Description"/"ki_keywords"``).
  - ``pins``: ``{numero_str: nombre_pin}`` fusionando todas las sub-unidades.
  - ``pin_types``: ``{numero_str: tipo_electrico}`` (power_in, bidirectional,
    input, output, passive, no_connect, ...).

Soporta el patrón ``(extends "Base")`` que usa KiCad para variantes de un
mismo pinout con distinto footprint/descripción (ej. ``LM358`` extends
``LM2904``, ``NE555P`` extends ``NE555D``): cuando un símbolo no define pines
propios, hereda los de la base referenciada dentro del mismo archivo,
siguiendo la cadena de ``extends`` si hace falta (con protección anti-ciclos).
"""
import re
from pathlib import Path


def _find_matching_paren(text: str, start: int) -> int:
    """Devuelve el índice del paréntesis de cierre que balancea el de `start`.

    `start` debe apuntar a un carácter `(`. Ignora paréntesis dentro de
    cadenas `"..."` (con soporte de escapes `\\"`), ya que descripciones o
    datasheets pueden en teoría contener texto con paréntesis.
    """
    depth = 0
    in_string = False
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _extract_blocks(text: str, tag: str) -> list:
    """Extrae todos los bloques ``(tag ...)`` balanceados, en cualquier nivel
    de anidación. Sólo válido para tags que nunca se anidan dentro de sí
    mismos (cierto para ``pin``: un pin nunca contiene otro pin)."""
    blocks = []
    pattern = re.compile(r"\(" + re.escape(tag) + r"(?=[\s)])")
    for m in pattern.finditer(text):
        start = m.start()
        end = _find_matching_paren(text, start)
        if end != -1:
            blocks.append(text[start:end + 1])
    return blocks


def _iter_top_level_symbol_blocks(content: str) -> list:
    """Extrae los bloques ``(symbol "Nombre" ...)`` que son hijos directos de
    ``(kicad_symbol_lib ...)`` (profundidad 2 respecto al inicio del
    archivo), ignorando las sub-unidades anidadas dentro de cada símbolo
    (profundidad 3+, ej. ``(symbol "Nombre_1_1" ...)``)."""
    lib_match = re.search(r"\(kicad_symbol_lib\b", content)
    if not lib_match:
        return []

    blocks = []
    depth = 0
    in_string = False
    block_start = None
    i = lib_match.start()
    n = len(content)
    while i < n:
        c = content[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "(":
            depth += 1
            if depth == 2 and block_start is None and re.match(r'\(symbol\s+"', content[i:i + 40]):
                block_start = i
            i += 1
            continue
        if c == ")":
            depth -= 1
            if depth == 1 and block_start is not None:
                blocks.append(content[block_start:i + 1])
                block_start = None
            if depth == 0:
                break
            i += 1
            continue
        i += 1
    return blocks


_OVERBAR_RE = re.compile(r"~\{([^}]*)\}")


def _clean_pin_name(name: str) -> str:
    """Convierte la sintaxis de barra superior de KiCad ``~{RST}`` (señal
    activa-baja) a un prefijo ``~`` más legible/portable (``~RST``)."""
    return _OVERBAR_RE.sub(lambda m: "~" + m.group(1), name)


class KiCadSymbolParser:
    """Parser de librerías ``.kicad_sym`` (formato packed) a estructuras Python."""

    _PROPERTY_RE_TEMPLATE = r'\(property\s+"{name}"\s+"((?:[^"\\]|\\.)*)"'

    def parse_library(self, file_path: str) -> list:
        """Parsea un archivo ``.kicad_sym`` completo.

        Devuelve una lista de dicts (uno por símbolo top-level), en el orden
        en que aparecen en el archivo, con ``extends`` ya resueltos contra
        otros símbolos del mismo archivo.
        """
        content = Path(file_path).read_text(encoding="utf-8")
        library_name = Path(file_path).stem
        return self._parse_content(content, library_name)

    def _parse_content(self, content: str, library_name: str) -> list:
        raw_blocks = _iter_top_level_symbol_blocks(content)
        symbols = {}
        order = []
        for block in raw_blocks:
            parsed = self._parse_symbol_block(block, library_name)
            if parsed is None:
                continue
            symbols[parsed["lib_id"]] = parsed
            order.append(parsed["lib_id"])

        for lib_id in order:
            sym = symbols[lib_id]
            if sym["pins"]:
                continue
            base_name = sym.get("_extends")
            visited = {lib_id}
            while base_name and base_name not in visited:
                visited.add(base_name)
                base = symbols.get(base_name)
                if base is None:
                    break
                if base["pins"]:
                    sym["pins"] = dict(base["pins"])
                    sym["pin_types"] = dict(base["pin_types"])
                    break
                base_name = base.get("_extends")

        for sym in symbols.values():
            sym.pop("_extends", None)

        return [symbols[lib_id] for lib_id in order]

    def _parse_symbol_block(self, block: str, library_name: str) -> dict:
        name_match = re.match(r'\(symbol\s+"((?:[^"\\]|\\.)*)"', block)
        if not name_match:
            return None
        lib_id = name_match.group(1)

        extends_match = re.search(r'\(extends\s+"((?:[^"\\]|\\.)*)"', block)

        def _prop(name: str) -> str:
            m = re.search(self._PROPERTY_RE_TEMPLATE.format(name=re.escape(name)), block)
            return m.group(1) if m else ""

        pins = {}
        pin_types = {}
        for pin_block in _extract_blocks(block, "pin"):
            type_match = re.match(r"\(pin\s+(\S+)", pin_block)
            number_match = re.search(r'\(number\s+"((?:[^"\\]|\\.)*)"', pin_block)
            name_match_pin = re.search(r'\(name\s+"((?:[^"\\]|\\.)*)"', pin_block)
            if not number_match:
                continue
            number = number_match.group(1)
            name = _clean_pin_name(name_match_pin.group(1)) if name_match_pin else ""
            ptype = type_match.group(1) if type_match else "unspecified"
            existing = pins.get(number)
            if number not in pins or (not existing and name):
                pins[number] = name
                pin_types[number] = ptype

        return {
            "lib_id": lib_id,
            "library": library_name,
            "footprint_default": _prop("Footprint"),
            "datasheet": _prop("Datasheet"),
            "description": _prop("Description"),
            "keywords": _prop("ki_keywords"),
            "pins": pins,
            "pin_types": pin_types,
            "_extends": extends_match.group(1) if extends_match else None,
        }


if __name__ == "__main__":
    parser = KiCadSymbolParser()
    print("Parser de símbolos KiCad inicializado.")

    _fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "kicad_sym"
    _lm358 = _fixtures_dir / "lm358.kicad_sym"
    if _lm358.exists():
        symbols = parser.parse_library(str(_lm358))
        by_id = {s["lib_id"]: s for s in symbols}
        print(f"\n=== Self-test: {_lm358.name} ===")
        print(f"  symbols: {list(by_id.keys())}")
        assert "LM358" in by_id, "LM358 no encontrado"
        assert len(by_id["LM358"]["pins"]) == 8, f"LM358 debería tener 8 pines, tiene {len(by_id['LM358']['pins'])}"
        assert by_id["LM358"]["pins"]["8"] == "V+", "pin 8 de LM358 (heredado de LM2904) debería ser V+"
        assert "Low-Power" in by_id["LM358"]["description"], "descripción propia de LM358 no capturada"
        print("  Self-test: PASS (herencia extends + fusión multi-unidad)")
    else:
        print(f"\n(Skipping self-test — {_lm358} not found)")
