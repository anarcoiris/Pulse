"""
tests/test_kicad_drc_integration.py
====================================
Relocated from scratch/test_drc_fail.py (Session 5 — repo hygiene, 07-jul-2026).

Integration smoke test: places two components deliberately overlapping (same
x/y) to force a DRC courtyard/clearance violation, then asserts the export
pipeline (KiCadBridge.export_all -> kicad-cli DRC) actually catches it instead
of silently succeeding. Requires a working `kicad-cli` on PATH; skipped
automatically otherwise (this was previously a standalone script under
`scratch/`, not part of any automated run).
"""

from pathlib import Path

import pytest

from bridge.kicad_bridge import KiCadBridge, find_kicad_cli
from bridge.pcb_layout import PCBLayout
from core.circuit_graph import CircuitGraph

pytestmark = pytest.mark.skipif(
    find_kicad_cli() is None, reason="kicad-cli not found on PATH"
)


def test_drc_catches_overlapping_components(tmp_path: Path):
    graph = CircuitGraph()
    graph.add("R", 10, 10, "H", 10000, "R1", "VCC", "GND")
    graph.add("C", 10, 10, "H", 100e-9, "C1", "VCC", "GND")

    pcb = PCBLayout(board_width=20, board_height=20)
    # Place both components at the exact same spot to force a courtyard/clearance
    # violation.
    pcb.add_resistor("R1", "10k", x=10, y=10, net1="VCC", net2="GND")
    pcb.add_capacitor("C1", "100nF", x=10, y=10, net1="VCC", net2="GND")

    out_dir = tmp_path / "drc_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    pcb_path = out_dir / "design.kicad_pcb"
    pcb.save(pcb_path)

    bridge = KiCadBridge()
    result = bridge.export_all(graph, output_dir=str(out_dir), project_name="design")

    assert "error" in result, "DRC should reject overlapping components, but export succeeded"
    if "drc_report" in result:
        violations = result["drc_report"].get("violations", [])
        assert violations, "export failed but no DRC violations were reported"
