"""
test_graphics_engine.py
=======================
Unit tests for bridge/graphics_engine.py
"""
import pytest
from bridge.graphics_engine import (
    LogoGraphic,
    PolyGraphic,
    format_logo_footprint_sexpr,
    format_poly_graphic_sexpr,
)

def test_format_logo_footprint_sexpr():
    logo = LogoGraphic(
        footprint_name="Logos:fabitive_logo",
        reference="LOGO1",
        value="LOGO",
        at_x=120.0,
        at_y=80.0,
        rotation=90.0,
        layer="F.Cu"
    )
    sexpr = format_logo_footprint_sexpr(logo)
    assert '(footprint "Logos:fabitive_logo"' in sexpr
    assert '(layer "F.Cu")' in sexpr
    assert '(at 120.0000 80.0000 90.0)' in sexpr
    assert '(property "Reference" "LOGO1"' in sexpr

def test_format_poly_graphic_sexpr():
    poly = PolyGraphic(
        points=[(10.0, 10.0), (20.0, 10.0), (15.0, 20.0)],
        layer="B.SilkS",
        stroke_width=0.15,
        fill=True
    )
    sexpr = format_poly_graphic_sexpr(poly)
    assert '(gr_poly' in sexpr
    assert '(pts (xy 10.0000 10.0000) (xy 20.0000 10.0000) (xy 15.0000 20.0000))' in sexpr
    assert '(stroke (width 0.15) (type solid))' in sexpr
    assert '(fill yes)' in sexpr
    assert '(layer "B.SilkS")' in sexpr
