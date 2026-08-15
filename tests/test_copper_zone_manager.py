"""
test_copper_zone_manager.py
===========================
Unit tests for core/copper_zone_manager.py
"""
import pytest
from core.copper_zone_manager import (
    CopperZone,
    generate_ground_pour_zones,
    generate_stitching_vias,
    format_zone_sexpr,
)

def test_generate_ground_pour_zones():
    bounds = (10.0, 10.0, 60.0, 40.0)
    zones = generate_ground_pour_zones(bounds, layers=["F.Cu", "B.Cu"], net_name="PWR_GND", net_id=1)
    assert len(zones) == 2
    assert zones[0].layer == "F.Cu"
    assert zones[1].layer == "B.Cu"
    assert len(zones[0].points) == 4

def test_generate_stitching_vias_with_keepout():
    bounds = (0.0, 0.0, 10.0, 10.0)
    # Keepout box covering center area (2.0, 2.0) to (8.0, 8.0)
    keepouts = [(2.0, 2.0, 8.0, 8.0)]
    vias = generate_stitching_vias(
        bounds,
        grid_step=2.5,
        margin=1.0,
        keepout_boxes=keepouts
    )
    # Check that no via lies inside (2.0, 2.0) to (8.0, 8.0)
    for v in vias:
        in_kp = (2.0 <= v["x"] <= 8.0) and (2.0 <= v["y"] <= 8.0)
        assert not in_kp, f"Via at ({v['x']}, {v['y']}) landed inside keepout box"

def test_format_zone_sexpr():
    zone = CopperZone(
        net_name="PWR_GND",
        net_id=1,
        layer="F.Cu",
        points=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        clearance=0.15
    )
    sexpr = format_zone_sexpr(zone)
    assert '(zone (net 1) (net_name "PWR_GND") (layer "F.Cu")' in sexpr
    assert '(connect_pads (clearance 0.15))' in sexpr
    assert '(xy 0.0000 0.0000)' in sexpr
