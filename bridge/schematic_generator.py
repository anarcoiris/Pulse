"""
bridge/schematic_generator.py
=============================
Generador nativo de archivos esquemáticos de KiCad 10 (.kicad_sch)
"""

from __future__ import annotations
import uuid
import re
from pathlib import Path
from typing import TYPE_CHECKING, Tuple, Optional

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph

from knowledge.pulse_config import cfg
from core.component_types import VALUE_SYMBOL_MAP, KICAD_SYMBOLS, VALUE_FMT
from bridge.kicad_bridge import find_kicad_symbol_dir


def _sch(key: str, default=None):
    return cfg(f"schematic.{key}", default)


def _grid_scale() -> float:
    return float(_sch("grid_scale_mm", 5.08))


class SchematicGenerator:
    def __init__(self, graph: "CircuitGraph"):
        self.graph = graph
        self.wires = []
        self._used_lib_ids: dict[str, dict] = {}
        self.schematic_uuid = self._get_uuid()

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

    def _extract_raw_kicad_symbol(self, lib_id: str, visited: set | None = None) -> list[str]:
        """Intenta extraer la S-expression del símbolo (y sus padres `extends`) desde las librerías oficiales de KiCad 10."""
        if visited is None:
            visited = set()
        if lib_id in visited:
            return []
        visited.add(lib_id)

        sym_dir = find_kicad_symbol_dir()
        if not sym_dir or ':' not in lib_id:
            return []
        lib_name, sym_name = lib_id.split(':', 1)
        lib_file = sym_dir / f"{lib_name}.kicad_sym"
        if not lib_file.exists():
            return []

        results = []
        try:
            content = lib_file.read_text(encoding='utf-8')
            pattern = re.compile(rf'\n\t\(symbol "{re.escape(sym_name)}"\s+.*?\n\t\)', re.DOTALL)
            m = pattern.search(content)
            if m:
                raw_sym = m.group(0).strip()
                # Verificar si extiende a otro símbolo
                ext_m = re.search(r'\(extends "([^"]+)"\)', raw_sym)
                if ext_m:
                    parent_name = ext_m.group(1)
                    parent_lib_id = f"{lib_name}:{parent_name}"
                    parent_results = self._extract_raw_kicad_symbol(parent_lib_id, visited=visited)
                    results.extend(parent_results)
                    raw_sym = raw_sym.replace(f'(extends "{parent_name}")', f'(extends "{parent_lib_id}")')

                raw_sym = raw_sym.replace(f'(symbol "{sym_name}"', f'(symbol "{lib_id}"', 1)
                results.append(f"    {raw_sym}")
        except Exception:
            pass
        return results


    def generate(self) -> str:
        s = []
        s.append('(kicad_sch (version 20241228) (generator "PulseLab_Forge") (generator_version "10.0.0")')
        s.append(f'  (uuid "{self.schematic_uuid}")')
        s.append('  (paper "A4")')

        symbol_lines = []
        comps = self.graph.components

        # Check if coordinates are flat linear
        is_flat = all(c.grid_r == 0 for c in comps) or (max(c.grid_r for c in comps) == 0)

        from bridge.island_layout import compute_layout
        positions, total_w, total_h = compute_layout(comps, mode='schematic')

        if is_flat:
            for c in comps:
                cx, cy = positions.get(c.uid, (0.0, 0.0))
                c.grid_c = int(round(cx))
                c.grid_r = int(round(cy))

        gs = _grid_scale()
        total_w_mm = total_w * gs
        total_h_mm = total_h * gs
        dyn_offset_x = max(10.0, (297.0 - total_w_mm) / 2.0)
        dyn_offset_y = max(10.0, (210.0 - total_h_mm) / 2.0)

        for i, c in enumerate(comps):
            # Centro del componente en KiCad
            comp_w = getattr(c, "width", 2)
            comp_h = getattr(c, "height", 2)
            center_gc = c.grid_c + comp_w / 2.0
            center_gr = c.grid_r + comp_h / 2.0
            cx, cy = self._grid_to_kicad(center_gc, center_gr, offset_x=dyn_offset_x, offset_y=dyn_offset_y)

            angle = 90 if c.orientation == "H" else 0
            lib_id = self._resolve_lib_id(c)
            fp_id = getattr(c, "footprint_id", None) or getattr(c, "footprint", "") or ""
            comp_uuid = self._get_uuid()

            # Registrar para lib_symbols
            if lib_id not in self._used_lib_ids:
                self._used_lib_ids[lib_id] = {
                    "etype": c.etype,
                    "pins": {},
                    "width": comp_w,
                    "height": comp_h
                }
            if getattr(c, "pins", None):
                for p_id in c.pins:
                    self._used_lib_ids[lib_id]["pins"][str(p_id)] = c.pins[p_id]
            elif c.etype in ("R", "C", "L", "D", "V", "S"):
                self._used_lib_ids[lib_id]["pins"]["1"] = getattr(c, "n1", "1")
                self._used_lib_ids[lib_id]["pins"]["2"] = getattr(c, "n2", "2")

            base = c.etype
            if base == "GND":
                ref = f"#PWR{self._get_uuid()[:4]}"
            else:
                ref = c.uid if hasattr(c, "uid") and c.uid else getattr(c, "label", None) or f"{base}{i+1}"

            val = self._format_val(c)

            if getattr(c, "pins", None):
                # Generar cables de conexión (wire stubs) y etiquetas de red
                num_pins = len(c.pins)
                half = max(1, num_pins // 2)
                pin_ids = sorted(c.pins.keys(), key=lambda x: int(x) if x.isdigit() else x)
                for i_pin, p_id in enumerate(pin_ids):
                    net_name = c.pins.get(p_id, "")
                    if net_name:
                        is_left = (i_pin < half)
                        p_gc = c.grid_c if is_left else c.grid_c + comp_w
                        p_gr = c.grid_r + (i_pin if is_left else (num_pins - 1 - i_pin))

                        stub_gc = p_gc - 1 if is_left else p_gc + 1

                        px, py = self._grid_to_kicad(p_gc, p_gr, offset_x=dyn_offset_x, offset_y=dyn_offset_y)
                        sx, sy = self._grid_to_kicad(stub_gc, p_gr, offset_x=dyn_offset_x, offset_y=dyn_offset_y)

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
                f'    (uuid "{comp_uuid}")\n'
                f'    (property "Reference" "{ref}" (at {cx} {cy - 2.54} 0)\n'
                f'      (effects (font (size 1.27 1.27)) (justify right)))\n'
                f'    (property "Value" "{val}" (at {cx} {cy + 2.54} 0)\n'
                f'      (effects (font (size 1.27 1.27)) (justify right)))\n'
                f'    (property "Footprint" "{fp_id}" (at {cx} {cy} 0)\n'
                f'      (effects (font (size 1.27 1.27)) hide))\n'
                f'    (instances\n'
                f'      (project "board"\n'
                f'        (path "/{self.schematic_uuid}/{comp_uuid}" (reference "{ref}") (unit 1))\n'
                f'      )\n'
                f'    )\n'
                f'  )'
            )

        s.append("  (lib_symbols")
        added_symbols = set()
        for lib_id, info in self._used_lib_ids.items():
            if lib_id in added_symbols:
                continue
            raw_sexprs = self._extract_raw_kicad_symbol(lib_id)
            if raw_sexprs:
                for expr in raw_sexprs:
                    sym_m = re.search(r'\(symbol "([^"]+)"', expr)
                    if sym_m:
                        sym_k = sym_m.group(1)
                        if sym_k not in added_symbols:
                            added_symbols.add(sym_k)
                            s.append(expr)
            else:
                added_symbols.add(lib_id)
                # Generar símbolo dinámico con pines alineados espacialmente
                sub_name = f"{lib_id.split(':')[-1]}_0_1" if ":" in lib_id else f"{lib_id}_0_1"
                pins_data = info.get("pins", {})
                if not pins_data:
                    pins_data = {"1": "1", "2": "2"}

                comp_w = info.get("width", 2)
                comp_h = info.get("height", 2)

                num_pins = len(pins_data)
                half = max(1, num_pins // 2)
                pin_ids = sorted(pins_data.keys(), key=lambda x: int(x) if x.isdigit() else x)

                pin_lines = []
                for i_pin, p_num in enumerate(pin_ids):
                    is_left = (i_pin < half)
                    rel_x = round((-comp_w / 2.0 if is_left else comp_w / 2.0) * gs, 2)
                    pin_row = i_pin if is_left else (num_pins - 1 - i_pin)
                    rel_y = round((pin_row - comp_h / 2.0) * gs, 2)
                    orient = 0 if is_left else 180

                    pin_lines.append(
                        f'        (pin passive line (at {rel_x} {rel_y} {orient}) (length 2.54)\n'
                        f'          (name "~" (effects (font (size 1.27 1.27))))\n'
                        f'          (number "{p_num}" (effects (font (size 1.27 1.27))))\n'
                        f'        )'
                    )

                pins_str = "\n".join(pin_lines)
                s.append(
                    f'    (symbol "{lib_id}" (pin_numbers hide) (pin_names (offset 1.016) hide)\n'
                    f'      (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
                    f'      (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))\n'
                    f'      (property "Value" "Val" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))\n'
                    f'      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
                    f'      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
                    f'      (symbol "{sub_name}"\n'
                    f'{pins_str}\n'
                    f'      )\n'
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
        s.append('  (sheet_instances\n    (path "/" (page "1"))\n  )')
        s.append(")")
        return "\n".join(s)

    def save(self, output_path: str):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")
        return path
