"""
graphics_engine.py
==================
Stencil Logos & Graphical Artwork Engine for PulseLab EDA Platform.

Provides:
- Silkscreen and Copper logo footprint placement (`F.SilkS`, `B.SilkS`, `F.Cu`, `B.Cu`).
- Graphical polygon (`gr_poly`) and line (`gr_line`) S-expression generator.
- Vector graphics/stencil placement support.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import uuid

@dataclass
class LogoGraphic:
    footprint_name: str # e.g. "Logos:fabitive_logo"
    reference: str = "LOGO1"
    value: str = "LOGO"
    at_x: float = 0.0
    at_y: float = 0.0
    rotation: float = 0.0
    layer: str = "F.SilkS" # "F.SilkS", "B.SilkS", "F.Cu", "B.Cu"

@dataclass
class PolyGraphic:
    points: List[Tuple[float, float]]
    layer: str = "F.SilkS"
    stroke_width: float = 0.12
    fill: bool = True

def format_logo_footprint_sexpr(logo: LogoGraphic) -> str:
    """
    Formats a logo footprint placement into KiCad S-expression.
    """
    fp_uuid = str(uuid.uuid4())
    ref_uuid = str(uuid.uuid4())
    val_uuid = str(uuid.uuid4())

    rot_str = f" {logo.rotation:.1f}" if logo.rotation != 0.0 else ""
    return (
        f'  (footprint "{logo.footprint_name}"\n'
        f'    (layer "{logo.layer}")\n'
        f'    (uuid "{fp_uuid}")\n'
        f'    (at {logo.at_x:.4f} {logo.at_y:.4f}{rot_str})\n'
        f'    (property "Reference" "{logo.reference}"\n'
        f'      (at 0 0{rot_str})\n'
        f'      (layer "{logo.layer}")\n'
        f'      (uuid "{ref_uuid}")\n'
        f'      (effects (font (size 1 1) (thickness 0.15)))\n'
        f'    )\n'
        f'    (property "Value" "{logo.value}"\n'
        f'      (at 0 0{rot_str})\n'
        f'      (layer "{logo.layer}")\n'
        f'      (uuid "{val_uuid}")\n'
        f'      (effects (font (size 1 1) (thickness 0.15)))\n'
        f'    )\n'
        f'  )'
    )

def format_poly_graphic_sexpr(poly: PolyGraphic) -> str:
    """
    Formats a graphical polygon (gr_poly) into KiCad S-expression.
    """
    pts_str = " ".join([f"(xy {x:.4f} {y:.4f})" for x, y in poly.points])
    fill_str = "(fill yes)" if poly.fill else "(fill no)"
    poly_uuid = str(uuid.uuid4())

    return (
        f'  (gr_poly\n'
        f'    (pts {pts_str})\n'
        f'    (stroke (width {poly.stroke_width:.2f}) (type solid))\n'
        f'    {fill_str}\n'
        f'    (layer "{poly.layer}")\n'
        f'    (uuid "{poly_uuid}")\n'
        f'  )'
    )
