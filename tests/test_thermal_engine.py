"""
test_thermal_engine.py
======================
Unit tests for core/thermal_engine.py
"""
import pytest
from core.thermal_engine import (
    ThermalViaConfig,
    ThermalZoneConfig,
    generate_thermal_via_grid,
    format_thermal_via_sexpr,
    format_thermal_vias_sexpr,
)

def test_generate_thermal_via_grid_3x3():
    vias = generate_thermal_via_grid(
        center_x=100.0,
        center_y=100.0,
        rows=3,
        cols=3,
        pitch=1.0,
        via_size=0.6,
        drill=0.3,
        net_name="PWR_GND",
        net_id=2
    )
    assert len(vias) == 9
    # Center via should be exactly at (100.0, 100.0)
    center_via = vias[4]
    assert center_via["x"] == 100.0
    assert center_via["y"] == 100.0
    assert center_via["size"] == 0.6
    assert center_via["drill"] == 0.3
    assert center_via["net_id"] == 2

def test_format_thermal_via_sexpr():
    via = {
        "x": 100.0,
        "y": 100.0,
        "size": 0.6,
        "drill": 0.3,
        "net_name": "PWR_GND",
        "net_id": 1
    }
    sexpr = format_thermal_via_sexpr(via)
    assert '(via (at 100.0000 100.0000)' in sexpr
    assert '(size 0.60) (drill 0.30)' in sexpr
    assert '(layers "F.Cu" "B.Cu")' in sexpr
    assert '(net 1)' in sexpr
