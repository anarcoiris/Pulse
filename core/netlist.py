"""
core/netlist.py
===============
Conversión de CircuitGraph a formatos de netlist:
  - KiCad Netlist (.net, formato S-expression)
  - SKiDL Python script generado automáticamente
  - BOM texto / CSV

Ref: KiCad Netlist Format: https://dev-docs.kicad.org/en/file-formats/netlist/
"""

from __future__ import annotations
import json
import csv
import io
import re
import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ui.editor import CircuitGraph, PlacedComponent

# Mapeado de etypes de PulseLab → símbolo KiCad y valor
_KICAD_SYMBOLS: dict[str, str] = {
    "R":   "Device:R",
    "C":   "Device:C",
    "L":   "Device:L",
    "V":   "Device:Battery",
    "S":   "Device:SW_SPST",
    "GND": "power:GND",
}

_DEFAULT_FOOTPRINTS: dict[str, str] = {
    "R":   "Resistor_SMD:R_0805_2012Metric",
    "C":   "Capacitor_SMD:C_0805_2012Metric",
    "L":   "Inductor_SMD:L_0805_2012Metric",
    "V":   "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "S":   "Button_Switch_THT:SW_PUSH_6mm",
    "GND": "TestPoint:TestPoint_Pad_D1.0mm",
}

_VALUE_FMT: dict[str, str] = {
    "R": "{:.4g}Ω",
    "C": "{:.4g}F",
    "L": "{:.4g}H",
    "V": "{:.4g}V",
    "S": "SW",
    "GND": "GND",
}


def _fmt_value(etype: str, value: float) -> str:
    fmt = _VALUE_FMT.get(etype, "{:.4g}")
    try:
        return fmt.format(value)
    except Exception:
        return str(value)


class NetlistGenerator:
    """
    Genera netlists y BOM desde un CircuitGraph.

    Uso::

        from core.netlist import NetlistGenerator
        ng = NetlistGenerator(graph)
        net_str = ng.to_kicad_netlist()
        with open("design.net", "w") as f:
            f.write(net_str)
    """

    def __init__(self, graph: "CircuitGraph"):
        self.graph = graph

    # ── Numeración de referencias ──────────────────────────────────

    def _assign_refs(self) -> dict[str, str]:
        """Asigna referencias únicas (R1, C1, etc.) a cada componente."""
        counters: dict[str, int] = {}
        refs: dict[str, str] = {}
        for c in self.graph.components:
            if c.etype == "GND":
                continue
            base = c.etype
            counters[base] = counters.get(base, 0) + 1
            refs[c.uid] = f"{base}{counters[base]}"
        return refs

    # ── KiCad Netlist (S-expression) ──────────────────────────────

    def to_kicad_netlist(self,
                         source_name: str = "PulseLab",
                         tool_ver: str = "PulseLab-Forge-1.0") -> str:
        """
        Genera netlist en formato KiCad (S-expression, compatible con KiCad 6+).

        Ref: https://dev-docs.kicad.org/en/file-formats/netlist/
        """
        refs = self._assign_refs()
        now  = datetime.datetime.now().strftime("%m/%d/%Y %H:%M %p")

        lines = []
        lines.append("(export (version D)")
        lines.append(f"  (design")
        lines.append(f"    (source \"{source_name}\")")
        lines.append(f"    (date \"{now}\")")
        lines.append(f"    (tool \"{tool_ver}\"))")
        lines.append("  (components")

        for c in self.graph.components:
            if c.etype == "GND":
                continue
            ref  = refs[c.uid]
            sym  = _KICAD_SYMBOLS.get(c.etype, "Device:R")
            fp   = _DEFAULT_FOOTPRINTS.get(c.etype, "")
            val  = _fmt_value(c.etype, c.value)
            # Sanitize label for kicad (no special chars)
            label = re.sub(r'[^\w\-]', '_', c.label)
            lines.append(f"    (comp (ref \"{ref}\")")
            lines.append(f"      (value \"{val}\")")
            lines.append(f"      (footprint \"{fp}\")")
            lines.append(f"      (description \"{label}\")")
            lines.append(f"      (fields (field (name uid) \"{c.uid}\"))")
            lines.append(f"      (libsource (lib Device) (part {c.etype}))")
            lines.append(f"      (sheetpath (names /{ref}) (tstamps /{ref})))")

        lines.append("  )")  # /components

        # Nets
        # Build net→pins mapping
        net_map: dict[str, list[tuple[str, str]]] = {}
        for c in self.graph.components:
            if c.etype == "GND":
                net_map.setdefault("GND", []).append((refs.get(c.uid, c.uid), "1"))
                continue
            ref = refs[c.uid]
            net_map.setdefault(c.n1, []).append((ref, "1"))
            net_map.setdefault(c.n2, []).append((ref, "2"))

        lines.append("  (nets")
        for code, (net_name, nodes) in enumerate(net_map.items(), start=1):
            lines.append(f"    (net (code {code}) (name \"{net_name}\")")
            for ref, pin in nodes:
                lines.append(f"      (node (ref \"{ref}\") (pin \"{pin}\"))")
            lines.append("    )")
        lines.append("  )")  # /nets
        lines.append(")")   # /export

        return "\n".join(lines)

    # ── SKiDL Script ──────────────────────────────────────────────

    def to_skidl_script(self) -> str:
        """
        Genera un script Python SKiDL equivalente al CircuitGraph.
        El script puede ejecutarse directamente para generar la netlist.
        """
        refs = self._assign_refs()
        lines = []
        lines.append("#!/usr/bin/env python3")
        lines.append('"""')
        lines.append("SKiDL circuit script — generado por PulseLab Forge.")
        lines.append(f"Generado: {datetime.datetime.now().isoformat()}")
        lines.append('"""')
        lines.append("from skidl import *")
        lines.append("")
        lines.append("# ── Nets ──────────────────────────────────────────────")

        # Collect unique nets
        nets = set()
        for c in self.graph.components:
            if c.etype != "GND":
                nets.add(c.n1)
                nets.add(c.n2)
        nets.discard("GND")

        for n in sorted(nets):
            safe = re.sub(r'[^\w]', '_', n)
            lines.append(f"{safe} = Net('{n}')")
        lines.append("gnd = Net('GND')")
        lines.append("")
        lines.append("# ── Components ────────────────────────────────────────")

        for c in self.graph.components:
            if c.etype == "GND":
                continue
            ref    = refs[c.uid]
            sym    = _KICAD_SYMBOLS.get(c.etype, "Device:R")
            fp     = _DEFAULT_FOOTPRINTS.get(c.etype, "")
            val    = _fmt_value(c.etype, c.value)
            lib, part = sym.split(":") if ":" in sym else ("Device", sym)
            var    = re.sub(r'[^\w]', '_', ref.lower())
            lines.append(
                f"{var} = Part('{lib}', '{part}', "
                f"value='{val}', footprint='{fp}')  # {c.label}"
            )

        lines.append("")
        lines.append("# ── Connections ───────────────────────────────────────")

        for c in self.graph.components:
            if c.etype == "GND":
                continue
            ref  = refs[c.uid]
            var  = re.sub(r'[^\w]', '_', ref.lower())
            n1s  = re.sub(r'[^\w]', '_', c.n1) if c.n1 != "GND" else "gnd"
            n2s  = re.sub(r'[^\w]', '_', c.n2) if c.n2 != "GND" else "gnd"
            lines.append(f"{var}['~'][1] += {n1s}")
            lines.append(f"{var}['~'][2] += {n2s}")

        lines.append("")
        lines.append("# ── Export ────────────────────────────────────────────")
        lines.append("ERC()                        # Electrical Rules Check")
        lines.append("generate_netlist()            # Salida: circuit.net")
        lines.append("")
        lines.append("if __name__ == '__main__':")
        lines.append("    # También se puede generar SVG del esquemático:")
        lines.append("    # generate_schematic()")
        lines.append("    pass")

        return "\n".join(lines)

    # ── BOM ───────────────────────────────────────────────────────

    def to_bom_csv(self) -> str:
        """
        Genera BOM en formato CSV.

        Columnas: Reference, Value, Footprint, Label, Type, Node1, Node2
        """
        refs = self._assign_refs()
        buf  = io.StringIO()
        w    = csv.writer(buf)
        w.writerow(["Reference", "Value", "Footprint", "Label", "Type",
                    "Node1", "Node2", "UID"])
        for c in self.graph.components:
            if c.etype == "GND":
                continue
            ref = refs.get(c.uid, c.uid)
            w.writerow([
                ref,
                _fmt_value(c.etype, c.value),
                _DEFAULT_FOOTPRINTS.get(c.etype, ""),
                c.label,
                c.etype,
                c.n1,
                c.n2,
                c.uid,
            ])
        return buf.getvalue()

    def to_bom_dict(self) -> list[dict]:
        """BOM como lista de dicts (para JSON / MCP)."""
        refs = self._assign_refs()
        rows = []
        for c in self.graph.components:
            if c.etype == "GND":
                continue
            rows.append({
                "ref": refs.get(c.uid, c.uid),
                "value": _fmt_value(c.etype, c.value),
                "footprint": _DEFAULT_FOOTPRINTS.get(c.etype, ""),
                "label": c.label,
                "type": c.etype,
                "n1": c.n1,
                "n2": c.n2,
                "uid": c.uid,
            })
        return rows

    def save_kicad_netlist(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_kicad_netlist(), encoding="utf-8")
        return path

    def save_skidl_script(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_skidl_script(), encoding="utf-8")
        return path

    def save_bom_csv(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_bom_csv(), encoding="utf-8")
        return path
