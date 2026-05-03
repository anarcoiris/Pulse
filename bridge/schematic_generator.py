"""
bridge/schematic_generator.py
=============================
Generador nativo de archivos esquemáticos de KiCad 8 (.kicad_sch)
Traduce el CircuitGraph visual de PulseLab (grid X, Y y wires) directamente
a las coordenadas espaciales requeridas por el editor de esquemas de KiCad.
"""

from __future__ import annotations
import uuid
import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Tuple

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph, PlacedComponent, Wire

SCALE = 5.08  # 1 unidad de grid de PulseLab = 5.08 mm en KiCad (standard 0.2 inch)
OFFSET_X = 50.0 # Margen izquierdo papel A4
OFFSET_Y = 50.0 # Margen superior papel A4

class SchematicGenerator:
    def __init__(self, graph: "CircuitGraph"):
        self.graph = graph
        self.symbols = []
        self.wires = []
        self.junctions = []
        self.labels = []
        
        self.comp_map = {
            "R": "Device:R",
            "C": "Device:C",
            "L": "Device:L",
            "V": "Device:Battery_Cell",
            "S": "Switch:SW_Push",
            "GND": "power:GND",
            "IC": "MCU_Espressif:ESP8266EX",
            "MCU": "MCU_Espressif:ESP8266EX"
        }

    def _get_uuid(self):
        return str(uuid.uuid4())

    def _net_to_label(self, net: str):
        if not net or net == "0":
            return "GND"
        return net.replace(" ", "_")

    def _grid_to_kicad(self, gc: float, gr: float) -> Tuple[float, float]:
        # KiCad orig is top-left, pulse is top-left
        x = OFFSET_X + gc * SCALE
        y = OFFSET_Y + gr * SCALE
        return round(x, 2), round(y, 2)

    def _add_wire(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        pts = f"(xy {p1[0]} {p1[1]}) (xy {p2[0]} {p2[1]})"
        self.wires.append(f'  (wire (pts {pts})\n    (stroke (width 0) (type default)) (uuid "{self._get_uuid()}")\n  )')

    def generate(self) -> str:
        s = []
        # Header (Minimal header for v8)
        s.append(f'(kicad_sch (version 20231120) (generator "PulseLab_Forge")')
        s.append(f'  (uuid "{self._get_uuid()}")')
        s.append(f'  (paper "A4")')

        # Dummy lib_symbols block (KiCad 8 will attempt to auto-relink from system)
        # We define empty shells just enough so it parses and invokes the library rescue
        s.append(f'  (lib_symbols')
        for k, v in set(self.comp_map.items()):
            s.append(f'    (symbol "{v}" (pin_numbers hide) (pin_names (offset 1.016) hide) (exclude_from_sim no) (in_bom yes) (on_board yes)')
            s.append(f'      (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))')
            s.append(f'      (property "Value" "Val" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))')
            s.append(f'      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
            s.append(f'      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
            s.append(f'    )')
        s.append(f'  )')

        # Component placement
        ref_counters = {}
        for c in self.graph.components:
            cx, cy = self._grid_to_kicad(c.grid_c, c.grid_r)
            
            # Orientation
            angle = 0
            if c.orientation == 'H':
                angle = 90
            
            lib_id = self.comp_map.get(c.etype, "Device:R")
            
            base = c.etype
            if base == "GND":
                ref = f"#PWR{self._get_uuid()[:4]}"
            else:
                ref_counters[base] = ref_counters.get(base, 0) + 1
                ref = f"{base}{ref_counters[base]}"

            val = str(c.value) if c.etype != "GND" else "GND"
            
            # Component placement and pin labels
            if c.etype in ('IC', 'MCU'):
                for p_gc, p_gr, p_id in c.get_pins_layout():
                    net_name = c.pins.get(p_id, "")
                    if net_name:
                        px, py = self._grid_to_kicad(p_gc, p_gr)
                        label = self._net_to_label(net_name)
                        s.append(f'  (label "{label}" (at {px} {py} 0) (fields_autoplaced)\n'
                                 f'    (effects (font (size 1.27 1.27)) (justify left bottom))\n'
                                 f'    (uuid "{self._get_uuid()}")\n  )')
            
            s_comp = []
            s_comp.append(f'  (symbol (lib_id "{lib_id}") (at {cx} {cy} {angle}) (unit 1)')
            s_comp.append(f'    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)')
            s_comp.append(f'    (uuid "{self._get_uuid()}")')
            s_comp.append(f'    (property "Reference" "{ref}" (at {cx} {cy-2.54} 0)')
            s_comp.append(f'      (effects (font (size 1.27 1.27)) (justify right))')
            s_comp.append(f'    )')
            s_comp.append(f'    (property "Value" "{val}" (at {cx} {cy+2.54} 0)')
            s_comp.append(f'      (effects (font (size 1.27 1.27)) (justify right))')
            s_comp.append(f'    )')
            s_comp.append(f'  )')
            s.append("\n".join(s_comp))

        # Wire placement
        for wire in self.graph.wires:
            path = wire.path
            for i in range(len(path) - 1):
                p1 = self._grid_to_kicad(path[i][0], path[i][1])
                p2 = self._grid_to_kicad(path[i+1][0], path[i+1][1])
                self._add_wire(p1, p2)
        
        for w in self.wires:
            s.append(w)

        s.append(f')') # End kicad_sch
        return "\n".join(s)

    def save(self, output_path: str):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")
        return path
