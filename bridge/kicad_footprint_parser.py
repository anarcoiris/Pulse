"""
bridge/kicad_footprint_parser.py
=================================
Parser for official KiCad (.kicad_mod) footprint files.
Extracts real pad geometries, drill sizes, shapes, and silkscreen lines/polygons
directly from KiCad 7/8/9/10 footprint libraries.
"""
from __future__ import annotations
import re
import math
from typing import Optional, List, Dict, Any, Tuple
from bridge.pcb_layout import Footprint, RawFootprint, Pad
from bridge.kicad_bridge import get_kicad_footprint


class KiCadFootprintParser:
    """Parses .kicad_mod S-expressions into PulseLab Footprint objects."""

    @staticmethod
    def parse_sexpr(sexpr: str, ref: str = "REF", value: str = "", lib_id: str = "") -> RawFootprint:
        """Parses a full .kicad_mod S-expression into a RawFootprint."""
        fp = RawFootprint(ref=ref, lib_id=lib_id, value=value, raw_sexpr=sexpr)
        fp.pads = []
        fp.lines = []    # Silkscreen lines: [[x1, y1], [x2, y2], layer]
        fp.circles = []  # Silkscreen circles: [[cx, cy], radius, layer]
        fp.rects = []    # Silkscreen rects: [x1, y1, x2, y2, layer]
        fp.arcs = []     # Silkscreen arcs: [[start_x, start_y], [mid_x, mid_y], [end_x, end_y], layer]

        # 1. Parse Pads by line grouping
        lines = sexpr.splitlines()
        in_pad = False
        pad_text = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("(pad "):
                in_pad = True
                pad_text = [stripped]
            elif in_pad:
                pad_text.append(stripped)
                if stripped == ")" or stripped.endswith(")"):
                    # Check if balanced or root pad tag closes
                    full_pad_block = " ".join(pad_text)
                    if full_pad_block.count("(") == full_pad_block.count(")"):
                        in_pad = False
                        KiCadFootprintParser._parse_single_pad(full_pad_block, fp)

        # 2. Parse Silkscreen Lines (fp_line)
        line_matches = re.finditer(r'\(fp_line\s+\(start\s+([\d\.-]+)\s+([\d\.-]+)\)\s+\(end\s+([\d\.-]+)\s+([\d\.-]+)\).*?\(layer\s+"?([^"\s\)]+)"?\)', sexpr, re.DOTALL)
        for m in line_matches:
            x1, y1, x2, y2, layer = m.groups()
            if "Silk" in layer or "Fab" in layer:
                fp.lines.append([[float(x1), float(y1)], [float(x2), float(y2)], layer])

        # 3. Parse Silkscreen Circles (fp_circle)
        circle_matches = re.finditer(r'\(fp_circle\s+\(center\s+([\d\.-]+)\s+([\d\.-]+)\)\s+\(end\s+([\d\.-]+)\s+([\d\.-]+)\).*?\(layer\s+"?([^"\s\)]+)"?\)', sexpr, re.DOTALL)
        for m in circle_matches:
            cx, cy, ex, ey, layer = m.groups()
            if "Silk" in layer or "Fab" in layer:
                rad = math.sqrt((float(ex) - float(cx))**2 + (float(ey) - float(cy))**2)
                fp.circles.append([[float(cx), float(cy)], rad, layer])

        # 4. Parse Silkscreen Rects (fp_rect)
        rect_matches = re.finditer(r'\(fp_rect\s+\(start\s+([\d\.-]+)\s+([\d\.-]+)\)\s+\(end\s+([\d\.-]+)\s+([\d\.-]+)\).*?\(layer\s+"?([^"\s\)]+)"?\)', sexpr, re.DOTALL)
        for m in rect_matches:
            x1, y1, x2, y2, layer = m.groups()
            if "Silk" in layer or "Fab" in layer:
                fp.rects.append([float(x1), float(y1), float(x2), float(y2), layer])

        return fp

    @staticmethod
    def _parse_single_pad(pad_str: str, fp: RawFootprint):
        """Parses a single balanced (pad ...) S-expression."""
        head_match = re.search(r'\(pad\s+"([^"]*)"\s+(\w+)\s+(\w+)', pad_str)
        if not head_match:
            return

        p_num = head_match.group(1) or "MP"
        p_type = head_match.group(2)
        p_shape = head_match.group(3)

        at_match = re.search(r'\(at\s+([\d\.-]+)\s+([\d\.-]+)(?:\s+([\d\.-]+))?\)', pad_str)
        size_match = re.search(r'\(size\s+([\d\.-]+)\s+([\d\.-]+)\)', pad_str)
        drill_match = re.search(r'\(drill\s+(?:oval\s+)?([\d\.-]+)(?:\s+([\d\.-]+))?\)', pad_str)
        layers_match = re.search(r'\(layers\s+([^\)]+)\)', pad_str)

        if not at_match or not size_match:
            return

        px = float(at_match.group(1))
        py = float(at_match.group(2))
        pw = float(size_match.group(1))
        ph = float(size_match.group(2))
        drill = float(drill_match.group(1)) if drill_match else 0.0

        layers = []
        if layers_match:
            layers = [l.strip('"') for l in layers_match.group(1).split()]

        pad = Pad(
            number=p_num,
            pad_type=p_type,
            shape=p_shape,
            x=px,
            y=py,
            w=pw,
            h=ph,
            drill=drill,
            layers=layers or (["F.Cu", "F.Mask", "F.Paste"] if p_type == "smd" else ["*.Cu", "*.Mask"])
        )
        fp.pads.append(pad)

    @classmethod
    def load_footprint(cls, lib_id: str, ref: str = "REF", value: str = "") -> Optional[Footprint]:
        """Loads and parses a footprint from the official KiCad footprint directory."""
        if not lib_id or ":" not in lib_id:
            return None

        lib, name = lib_id.split(":", 1)
        name = name.strip()
        sexpr = get_kicad_footprint(lib, name)
        if not sexpr:
            return None

        try:
            return cls.parse_sexpr(sexpr, ref=ref, value=value, lib_id=lib_id)
        except Exception:
            return None
