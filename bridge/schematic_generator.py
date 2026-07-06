"""
bridge/schematic_generator.py
=============================
Generador nativo de archivos esquemáticos de KiCad 8 (.kicad_sch)
"""

from __future__ import annotations
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph

from knowledge.pulse_config import cfg


def _sch(key: str, default=None):
    return cfg(f"schematic.{key}", default)


def _grid_scale() -> float:
    return float(_sch("grid_scale_mm", 5.08))


def _offset_x() -> float:
    return float(_sch("offset_x_mm", 50.0))


def _offset_y() -> float:
    return float(_sch("offset_y_mm", 50.0))

VALUE_SYMBOL_MAP = {
    "CH340": "Interface_USB:CH340G",
    "CH340C": "Interface_USB:CH340G",
    "CH340G": "Interface_USB:CH340G",
    "CP2102": "Interface_USB:CP2102N-A02-GQFN28",
    "AMS1117": "Regulator_Linear:AMS1117-3.3",
    "ESP32": "RF_Module:ESP32-WROOM-32",
    "ESP8266": "RF_Module:ESP-12F",
    "ESP32-S2": "MCU_Espressif:ESP32-S2",
    "ESP32-S3": "RF_Module:ESP32-WROOM-32",
    "ESP32-WROOM-32": "RF_Module:ESP32-WROOM-32",
}


class SchematicGenerator:
    def __init__(self, graph: "CircuitGraph"):
        self.graph = graph
        self.wires = []
        self._used_lib_ids: set[str] = set()

        self.comp_map = {
            "R": "Device:R",
            "C": "Device:C",
            "L": "Device:L",
            "V": "Device:Battery_Cell",
            "S": "Switch:SW_Push",
            "GND": "power:GND",
            "IC": "Interface_USB:CH340G",
            "MCU": "RF_Module:ESP32-WROOM-32",
        }

    def _get_uuid(self):
        return str(uuid.uuid4())

    def _net_to_label(self, net: str):
        if not net or net == "0":
            return "GND"
        return net.replace(" ", "_")

    def _grid_to_kicad(self, gc: float, gr: float) -> Tuple[float, float]:
        x = _offset_x() + gc * _grid_scale()
        y = _offset_y() + gr * _grid_scale()
        return round(x, 2), round(y, 2)

    def _resolve_lib_id(self, comp) -> str:
        sym = getattr(comp, "symbol_id", None) or ""
        if sym:
            self._used_lib_ids.add(sym)
            return sym
        val = str(comp.value).upper()
        label = str(getattr(comp, "label", "")).upper()
        for key, lib_id in VALUE_SYMBOL_MAP.items():
            if key.upper() in val or key.upper() in label:
                self._used_lib_ids.add(lib_id)
                return lib_id
        if comp.etype == "MCU":
            lib_id = "RF_Module:ESP32-WROOM-32"
        elif comp.etype == "IC":
            lib_id = "Interface_USB:CH340G"
        elif comp.etype == "L" and isinstance(comp.value, (int, float)) and comp.value < 1:
            lib_id = "Device:LED"
        else:
            lib_id = self.comp_map.get(comp.etype, "Device:R")
        self._used_lib_ids.add(lib_id)
        return lib_id

    def _add_wire(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        pts = f"(xy {p1[0]} {p1[1]}) (xy {p2[0]} {p2[1]})"
        self.wires.append(
            f'  (wire (pts {pts})\n'
            f'    (stroke (width 0) (type default)) (uuid "{self._get_uuid()}")\n  )'
        )

    def generate(self) -> str:
        s = []
        s.append('(kicad_sch (version 20231120) (generator "PulseLab_Forge")')
        s.append(f'  (uuid "{self._get_uuid()}")')
        s.append('  (paper "A4")')

        ref_counters = {}
        symbol_lines = []

        for c in self.graph.components:
            cx, cy = self._grid_to_kicad(c.grid_c, c.grid_r)
            angle = 90 if c.orientation == "H" else 0
            lib_id = self._resolve_lib_id(c)

            base = c.etype
            if base == "GND":
                ref = f"#PWR{self._get_uuid()[:4]}"
            else:
                ref_counters[base] = ref_counters.get(base, 0) + 1
                ref = getattr(c, "label", None) or f"{base}{ref_counters[base]}"

            val = str(c.value) if c.etype != "GND" else "GND"

            if c.etype in ("IC", "MCU") and c.pins:
                for p_gc, p_gr, p_id in c.get_pins_layout():
                    net_name = c.pins.get(p_id, "")
                    if net_name:
                        px, py = self._grid_to_kicad(p_gc, p_gr)
                        label = self._net_to_label(net_name)
                        symbol_lines.append(
                            f'  (label "{label}" (at {px} {py} 0) (fields_autoplaced)\n'
                            f'    (effects (font (size 1.27 1.27)) (justify left bottom))\n'
                            f'    (uuid "{self._get_uuid()}")\n  )'
                        )

            symbol_lines.append(
                f'  (symbol (lib_id "{lib_id}") (at {cx} {cy} {angle}) (unit 1)\n'
                f'    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)\n'
                f'    (uuid "{self._get_uuid()}")\n'
                f'    (property "Reference" "{ref}" (at {cx} {cy - 2.54} 0)\n'
                f'      (effects (font (size 1.27 1.27)) (justify right)))\n'
                f'    (property "Value" "{val}" (at {cx} {cy + 2.54} 0)\n'
                f'      (effects (font (size 1.27 1.27)) (justify right)))\n'
                f'  )'
            )

        all_libs = self._used_lib_ids | set(self.comp_map.values())
        s.append("  (lib_symbols")
        for lib_id in sorted(all_libs):
            s.append(
                f'    (symbol "{lib_id}" (pin_numbers hide) (pin_names (offset 1.016) hide)\n'
                f'      (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
                f'      (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))\n'
                f'      (property "Value" "Val" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))\n'
                f'      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
                f'      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
                f'    )'
            )
        s.append("  )")

        s.extend(symbol_lines)

        for wire in self.graph.wires:
            path = wire.path
            for i in range(len(path) - 1):
                p1 = self._grid_to_kicad(path[i][0], path[i][1])
                p2 = self._grid_to_kicad(path[i + 1][0], path[i + 1][1])
                self._add_wire(p1, p2)

        s.extend(self.wires)
        s.append(")")
        return "\n".join(s)

    def save(self, output_path: str):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")
        return path
