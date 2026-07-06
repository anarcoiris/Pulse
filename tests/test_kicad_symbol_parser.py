"""Tests unitarios para knowledge/kicad_symbol_parser.py contra fixtures reales
extraidos de la instalacion local de KiCad 10.0 (ver tests/fixtures/kicad_sym/)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "kicad_sym"


def _parse(filename):
    from knowledge.kicad_symbol_parser import KiCadSymbolParser
    parser = KiCadSymbolParser()
    symbols = parser.parse_library(str(FIXTURES_DIR / filename))
    return {s["lib_id"]: s for s in symbols}


def test_lm358_multi_unit_and_extends():
    """LM358 (dual op-amp) extiende LM2904 y no define pines propios: debe
    heredar los 8 pines fusionados de las 3 sub-unidades de LM2904
    (2 amplificadores + 1 unidad de alimentacion compartida)."""
    by_id = _parse("lm358.kicad_sym")
    assert "LM2904" in by_id and "LM358" in by_id

    lm2904 = by_id["LM2904"]
    assert len(lm2904["pins"]) == 8, f"LM2904 deberia tener 8 pines, tiene {len(lm2904['pins'])}"
    assert lm2904["pins"]["2"] == "-"
    assert lm2904["pins"]["3"] == "+"
    assert lm2904["pins"]["4"] == "V-"
    assert lm2904["pins"]["8"] == "V+"
    assert lm2904["pin_types"]["4"] == "power_in"
    assert lm2904["pin_types"]["1"] == "output"

    lm358 = by_id["LM358"]
    assert len(lm358["pins"]) == 8, "LM358 deberia heredar los 8 pines de LM2904 via extends"
    assert lm358["pins"] == lm2904["pins"], "LM358 deberia heredar exactamente los pines de LM2904"
    # Pero conserva sus propias propiedades (no las de la base)
    assert "Low-Power" in lm358["description"]
    assert lm358["description"] != lm2904["description"]
    assert lm358["library"] == "lm358"
    print("LM358 multi-unidad + extends: PASS")


def test_ne555p_extends_single_unit():
    """NE555P (DIP-8) extiende NE555D (SOIC-8): mismo pinout de 8 pines,
    heredado integramente pese a que el footprint difiere."""
    by_id = _parse("ne555p.kicad_sym")
    assert "NE555D" in by_id and "NE555P" in by_id

    ne555d = by_id["NE555D"]
    assert len(ne555d["pins"]) == 8
    assert ne555d["pins"]["1"] == "GND"
    assert ne555d["pins"]["8"] == "VCC"
    assert ne555d["pins"]["3"] == "OUT"
    assert ne555d["pin_types"]["1"] == "power_in"

    ne555p = by_id["NE555P"]
    assert ne555p["pins"] == ne555d["pins"], "NE555P deberia heredar el pinout de NE555D"
    assert ne555p["footprint_default"] == "Package_DIP:DIP-8_W7.62mm"
    assert ne555d["footprint_default"] == "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
    print("NE555P extends NE555D: PASS")


def test_esp32_wroom_32_full_pinout():
    """ESP32-WROOM-32 no usa extends (símbolo autocontenido): 39 pines propios,
    incluyendo el pin 32 marcado explícitamente como no_connect (NC de fábrica,
    distinto de los `NC_*` sintéticos que genera el LLM para pines no usados)."""
    by_id = _parse("esp32_wroom_32.kicad_sym")
    assert "ESP32-WROOM-32" in by_id

    esp32 = by_id["ESP32-WROOM-32"]
    assert len(esp32["pins"]) == 39, f"ESP32-WROOM-32 deberia tener 39 pines, tiene {len(esp32['pins'])}"
    assert esp32["pins"]["1"] == "GND"
    assert esp32["pins"]["2"] == "VDD"
    assert esp32["pins"]["34"] == "RXD0/IO3"
    assert esp32["pin_types"]["32"] == "no_connect"
    assert esp32["pins"]["32"] == "NC"
    assert "RF Module" in esp32["description"]
    assert "ESP32" in esp32["keywords"]
    assert esp32["footprint_default"] == "RF_Module:ESP32-WROOM-32"
    assert esp32["datasheet"].startswith("https://www.espressif.com")
    print("ESP32-WROOM-32 pinout completo (39 pines): PASS")


if __name__ == "__main__":
    test_lm358_multi_unit_and_extends()
    test_ne555p_extends_single_unit()
    test_esp32_wroom_32_full_pinout()
    print("\nTodos los tests de kicad_symbol_parser: PASS")
