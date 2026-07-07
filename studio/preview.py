"""
studio/preview.py
=================
Thin adapter for schematic/PCB preview paths (no inline viewer in v1).
"""

from __future__ import annotations

from pathlib import Path

from bridge.forge_api import generate_pcb
from bridge.gerber_export import export_svg
from bridge.kicad_bridge import KiCadBridge
from core.circuit_graph import CircuitGraph


def export_schematic_preview(graph: CircuitGraph, out_dir: str = "output/studio_preview") -> dict:
    """Generate PCB + SVG preview; returns paths or error dict."""
    bridge = KiCadBridge()
    if not bridge.available:
        return {"error": "KiCad no encontrado. Instala KiCad 8+ o usa pulse_lab FORGE > KiCad Status."}

    if not graph.components:
        return {"error": "Sin componentes en la sesion. Genera o carga un circuito primero."}

    pcb_result = generate_pcb(graph, out_dir=out_dir)
    if "error" in pcb_result:
        return pcb_result

    pcb_path = Path(pcb_result["path"])
    svg_result = export_svg(bridge._cli, pcb_path, output_dir=pcb_path.parent / "preview")
    if svg_result.get("error") or svg_result.get("stderr"):
        return {
            "pcb": str(pcb_path),
            "error": svg_result.get("error") or svg_result.get("stderr"),
        }

    files = svg_result.get("files") or []
    return {
        "pcb": str(pcb_path),
        "sch": pcb_result.get("sch_path", ""),
        "svg_dir": svg_result.get("output_dir", ""),
        "svg_files": files,
    }
