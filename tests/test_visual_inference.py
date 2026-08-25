"""
tests/test_visual_inference.py - Unit tests for visual inference and courtyard hitbox normalization engine
"""
import pytest
from core.visual_inference import (
    get_package_spec,
    CourtyardBox,
    VisualInferenceEngine,
    run_visual_inspection,
)
from core.circuit_graph import CircuitGraph
from bridge.pcb_builder import PCBBuilder


def test_get_package_spec_mcu():
    spec = get_package_spec("RF_Module:ESP32-S3-WROOM-1", "U1", "ESP32-S3")
    assert spec["package_type"] == "MCU"
    assert spec["width"] == 18.0
    assert spec["height"] == 25.5
    assert spec["courtyard_margin"] >= 0.40


def test_get_package_spec_passives():
    spec_c = get_package_spec("Capacitor_SMD:C_0805_2012Metric", "C1", "10uF")
    assert spec_c["package_type"] == "CAPACITOR"
    assert spec_c["width"] == 2.0
    assert spec_c["height"] == 1.25

    spec_r = get_package_spec("Resistor_SMD:R_0603_1608Metric", "R1", "10k")
    assert spec_r["package_type"] == "RESISTOR"
    assert spec_r["width"] == 1.6


def test_courtyard_box_intersection():
    # Overlapping boxes
    b1 = CourtyardBox(ref="U1", x=0.0, y=0.0, width=10.0, height=10.0, rotation=0.0, margin=0.5, package_type="IC")
    b2 = CourtyardBox(ref="U2", x=5.0, y=5.0, width=10.0, height=10.0, rotation=0.0, margin=0.5, package_type="IC")
    assert b1.intersects(b2) is True

    # Non-overlapping boxes
    b3 = CourtyardBox(ref="U3", x=30.0, y=30.0, width=10.0, height=10.0, rotation=0.0, margin=0.5, package_type="IC")
    assert b1.intersects(b3) is False


def test_visual_inspection_clean_layout(tmp_path):
    circuit = {
        "name": "Clean Test",
        "version": "1.0",
        "board_width": 60.0,
        "board_height": 40.0,
        "circuit": [
            {
                "etype": "MCU",
                "label": "U1",
                "footprint": "ESP32-S3-WROOM-1",
                "position": [0.0, 0.0],
                "rotation": 0.0,
                "pins": {"1": "PWR_3V3", "2": "GND", "3": "IO1"}
            },
            {
                "etype": "CAPACITOR",
                "label": "C1",
                "value": "10uF",
                "footprint": "C_0805",
                "position": [-12.0, 5.0],
                "rotation": 0.0,
                "pins": {"1": "PWR_3V3", "2": "GND"}
            }
        ]
    }
    g = CircuitGraph.from_json(circuit)
    builder = PCBBuilder.from_circuit_graph(g, out_dir=str(tmp_path))
    builder.save()

    report = run_visual_inspection(builder.pcb, circuit)
    assert report.passed is True
    assert report.visual_score >= 80.0
    assert len(report.courtyards) == 2


def test_visual_inspection_overlap_detection():
    from bridge.pcb_layout import PCBLayout, Footprint
    pcb = PCBLayout(board_width=50.0, board_height=50.0)
    # Two overlapping footprints placed at center
    fp1 = Footprint(lib_id="Package_SO:SOIC-8", ref="U1", value="IC1", x=25.0, y=25.0)
    fp2 = Footprint(lib_id="Package_SO:SOIC-8", ref="U2", value="IC2", x=25.5, y=25.5)
    pcb._footprints = [fp1, fp2]

    engine = VisualInferenceEngine(board_width=50.0, board_height=50.0)
    report = engine.inspect(pcb)

    assert report.passed is False
    assert any(v.rule_id == "VIS-001" for v in report.violations)


def test_gnd_via_filtering_bug_regression():
    """Verify that non-GND vias (e.g. VCC) are not counted as GND vias."""
    from bridge.pcb_layout import PCBLayout, Footprint, Via
    pcb = PCBLayout(board_width=50.0, board_height=50.0)
    pcb._get_net_id = lambda name: 1 if "GND" in name else 2
    pcb._nets = {"GND": 1, "VCC": 2}

    # Add a regulator and only a VCC via (no GND via)
    fp = Footprint(lib_id="Package_TO_SOT_SMD:SOT-223", ref="U1", value="AMS1117", x=25.0, y=25.0)
    pcb._footprints = [fp]
    # Place a VCC via nearby
    vcc_via = Via(x=26.0, y=26.0, net_id=2)
    pcb._vias = [vcc_via]

    engine = VisualInferenceEngine(board_width=50.0, board_height=50.0)
    report = engine.inspect(pcb)

    # VIS-005 should fire because the regulator does NOT have a GND via nearby
    assert any(v.rule_id == "VIS-005" for v in report.violations)


def test_courtyard_aabb_rotation_accounting():
    """Verify that PCBBuilder._get_courtyard_aabb accounts for rotation."""
    from bridge.pcb_builder import PCBBuilder
    from bridge.pcb_layout import Footprint

    fp_0 = Footprint(lib_id="Package_SO:SOIC-8", ref="U1", value="IC", x=50.0, y=50.0, rotation=0.0)
    fp_90 = Footprint(lib_id="Package_SO:SOIC-8", ref="U1", value="IC", x=50.0, y=50.0, rotation=90.0)

    aabb_0 = PCBBuilder._get_courtyard_aabb(fp_0, get_package_spec)
    aabb_90 = PCBBuilder._get_courtyard_aabb(fp_90, get_package_spec)

    w_0 = aabb_0[1] - aabb_0[0]
    h_0 = aabb_0[3] - aabb_0[2]

    w_90 = aabb_90[1] - aabb_90[0]
    h_90 = aabb_90[3] - aabb_90[2]

    # At 90 degrees, width and height of AABB swap
    assert abs(w_0 - h_90) < 0.1
    assert abs(h_0 - w_90) < 0.1


def test_find_non_overlapping_position_flexible_signatures():
    """Verify that _find_non_overlapping_position accepts both 3-arg and 4-arg signatures."""
    from bridge.pcb_builder import PCBBuilder
    from bridge.pcb_layout import PCBLayout, Footprint

    pcb = PCBLayout(board_width=50.0, board_height=50.0)
    builder = PCBBuilder(board_width=50.0, board_height=50.0)

    # 3-arg signature (pcb, x, y)
    x1, y1 = builder._find_non_overlapping_position(pcb, 25.0, 25.0)
    assert isinstance(x1, float)
    assert isinstance(y1, float)

    # 4-arg signature (pcb, fp, x, y)
    fp = Footprint(lib_id="Resistor_SMD:R_0805_2012Metric", ref="R1", value="10k", x=25.0, y=25.0)
    x2, y2 = builder._find_non_overlapping_position(pcb, fp, 25.0, 25.0)
    assert isinstance(x2, float)
    assert isinstance(y2, float)


def test_sexp_parser_bounds_and_empty_string():
    """Verify that sexp.parse safely handles empty strings and unclosed expressions."""
    from core.sexp import parse

    assert parse("") == []
    assert parse("   ") == []

    with pytest.raises(SyntaxError):
        parse("(kicad_pcb (unclosed")
