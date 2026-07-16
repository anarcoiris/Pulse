"""
bridge/schematic_generator.py
=============================
Generador nativo de archivos esquemáticos de KiCad 8/10 (.kicad_sch)
"""

from __future__ import annotations
import uuid
import math
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph

from knowledge.pulse_config import cfg
from core.component_types import VALUE_SYMBOL_MAP, KICAD_SYMBOLS, VALUE_FMT


def _sch(key: str, default=None):
    return cfg(f"schematic.{key}", default)


def _grid_scale() -> float:
    return float(_sch("grid_scale_mm", 5.08))


def _offset_x() -> float:
    return float(_sch("offset_x_mm", 50.0))


def _offset_y() -> float:
    return float(_sch("offset_y_mm", 50.0))


class SchematicGenerator:
    def __init__(self, graph: "CircuitGraph"):
        self.graph = graph
        self.wires = []
        self._used_lib_ids: dict[str, dict] = {} # lib_id -> pin info dict

    def _get_uuid(self):
        return str(uuid.uuid4())

    def _net_to_label(self, net: str):
        if not net or net == "0":
            return "GND"
        return net.replace(" ", "_")

    def _grid_to_kicad(self, gc: float, gr: float, offset_x: float = 50.0, offset_y: float = 50.0) -> Tuple[float, float]:
        x = offset_x + gc * _grid_scale()
        y = offset_y + gr * _grid_scale()
        return round(x, 2), round(y, 2)

    def _resolve_lib_id(self, comp) -> str:
        sym = getattr(comp, "symbol_id", None) or ""
        if sym:
            return sym
        val = str(comp.value).upper()
        label = str(getattr(comp, "label", "")).upper()
        for key, lib_id in VALUE_SYMBOL_MAP.items():
            if key.upper() in val or key.upper() in label:
                return lib_id
        if comp.etype == "MCU":
            return "RF_Module:ESP32-S3-WROOM-1"
        elif comp.etype == "IC":
            return "Interface_USB:CH340G"
        elif comp.etype == "L" and isinstance(comp.value, (int, float)) and comp.value < 1:
            return "Device:LED"
        else:
            return KICAD_SYMBOLS.get(comp.etype, "Device:R")

    def _add_wire(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        pts = f"(xy {p1[0]} {p1[1]}) (xy {p2[0]} {p2[1]})"
        self.wires.append(
            f'  (wire (pts {pts})\n'
            f'    (stroke (width 0) (type default)) (uuid "{self._get_uuid()}")\n  )'
        )
        
    def _format_val(self, c) -> str:
        if c.etype == "GND":
            return "GND"
        if c.etype in VALUE_FMT:
            fmt = VALUE_FMT[c.etype]
            try:
                v = float(c.value)
                return fmt.format(v)
            except:
                return str(c.value)
        return str(c.value)

    def generate(self) -> str:
        s = []
        s.append('(kicad_sch (version 20241228) (generator "PulseLab_Forge")')
        s.append(f'  (uuid "{self._get_uuid()}")')
        s.append('  (paper "A4")')

        ref_counters = {}
        symbol_lines = []
        
        comps = self.graph.components
        
        # Check if coordinates are flat linear (auto-assigned default grid_r=0)
        # If so, regenerate them using the Hierarchical Island Packing algorithm
        is_flat = all(c.grid_r == 0 for c in comps) or (max(c.grid_r for c in comps) == 0)
        
        # We compute layout bounds to center the schematic on A4
        from bridge.island_layout import compute_layout
        positions, total_w, total_h = compute_layout(comps, mode='schematic')
        
        if is_flat:
            for c in comps:
                cx, cy = positions.get(c.uid, (0.0, 0.0))
                c.grid_c = int(round(cx))
                c.grid_r = int(round(cy))
        
        # Center on A4 paper (297 x 210 mm)
        # grid_scale is typically 5.08mm
        gs = _grid_scale()
        total_w_mm = total_w * gs
        total_h_mm = total_h * gs
        dyn_offset_x = max(10.0, (297.0 - total_w_mm) / 2.0)
        dyn_offset_y = max(10.0, (210.0 - total_h_mm) / 2.0)
        
        for i, c in enumerate(comps):
            cx, cy = self._grid_to_kicad(c.grid_c, c.grid_r, offset_x=dyn_offset_x, offset_y=dyn_offset_y)
            angle = 90 if c.orientation == "H" else 0
            lib_id = self._resolve_lib_id(c)
            
            # Register pins for lib_symbols
            if lib_id not in self._used_lib_ids:
                self._used_lib_ids[lib_id] = {"etype": c.etype, "pins": {}}
            if getattr(c, "pins", None):
                for p_id in c.pins:
                    self._used_lib_ids[lib_id]["pins"][str(p_id)] = c.pins[p_id]

            base = c.etype
            if base == "GND":
                ref = f"#PWR{self._get_uuid()[:4]}"
            else:
                ref_counters[base] = ref_counters.get(base, 0) + 1
                ref = getattr(c, "label", None) or f"{base}{ref_counters[base]}"

            val = self._format_val(c)

            if c.etype in ("IC", "MCU") and getattr(c, "pins", None):
                # Place net labels around ICs with a short wire stub
                num_pins = len(c.pins)
                half = num_pins // 2
                pin_ids = sorted(c.pins.keys(), key=lambda x: int(x) if x.isdigit() else x)
                for i, p_id in enumerate(pin_ids):
                    net_name = c.pins.get(p_id, "")
                    if net_name:
                        # get_pins_layout() returns absolute grid_c, grid_r
                        is_left = (i < half)
                        p_gc = c.grid_c if is_left else c.grid_c + c.width
                        p_gr = c.grid_r + i if is_left else c.grid_r + (num_pins - 1 - i)
                        
                        # Draw wire stub outward
                        stub_gc = p_gc - 1 if is_left else p_gc + 1
                        
                        px, py = self._grid_to_kicad(p_gc, p_gr, offset_x=dyn_offset_x, offset_y=dyn_offset_y)
                        sx, sy = self._grid_to_kicad(stub_gc, p_gr, offset_x=dyn_offset_x, offset_y=dyn_offset_y)
                        
                        # Add wire stub
                        self.wires.append(
                            f'  (wire (pts (xy {px} {py}) (xy {sx} {sy}))\n'
                            f'    (stroke (width 0) (type default)) (uuid "{self._get_uuid()}")\n  )'
                        )

                        label = self._net_to_label(net_name)
                        justify = "right" if is_left else "left"
                        symbol_lines.append(
                            f'  (label "{label}" (at {sx} {sy} 0) (fields_autoplaced)\n'
                            f'    (effects (font (size 1.27 1.27)) (justify {justify} bottom))\n'
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

        s.append("  (lib_symbols")
        for lib_id, info in self._used_lib_ids.items():
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
                p1 = self._grid_to_kicad(path[i][0], path[i][1], offset_x=dyn_offset_x, offset_y=dyn_offset_y)
                p2 = self._grid_to_kicad(path[i + 1][0], path[i + 1][1], offset_x=dyn_offset_x, offset_y=dyn_offset_y)
                self._add_wire(p1, p2)

        s.extend(self.wires)
        s.append(")")
        return "\n".join(s)

    def save(self, output_path: str):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")
        return path
