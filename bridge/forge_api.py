
import os
import json
import datetime
import re
from pathlib import Path
from typing import Optional

from core.circuit_graph import CircuitGraph

def load_preset(name: str) -> CircuitGraph:
    """Carga un preset por nombre ('emp_pfn' | 'basic_rc' | 'rlc' | 'mcu')."""
    if name == 'basic_rc':
        from presets.basic_rc import load
    elif name == 'rlc':
        from presets.rlc import load
    elif name == 'mcu':
        from presets.mcu_uart import load
    else:
        from presets.emp_pfn import load
    return load()

def export_pdf(graph: CircuitGraph, out_dir: str = 'docs/latex_fix') -> str:
    """
    Genera PDF y PNG usando circuit_generator.py.
    Devuelve el path del PDF generado.
    """
    import matplotlib
    matplotlib.use('Agg')
    from circuit_generator import generate_from_simulator
    sim = graph.to_simulator()
    pdf_path, _ = generate_from_simulator(sim, output_dir=out_dir,
                                          basename='circuit_custom')
    return pdf_path

def export_kicad_netlist(graph: CircuitGraph, out_dir: str = 'output') -> dict:
    """Genera netlist KiCad + script SKiDL + BOM desde el circuito actual."""
    from bridge.kicad_bridge import KiCadBridge
    bridge = KiCadBridge()
    return bridge.generate_netlist(graph, output_dir=out_dir, project_name='pulselab_design')

def generate_pcb(graph: CircuitGraph, out_dir: str = 'output') -> dict:
    """Genera un .kicad_pcb con los componentes del circuito actual."""
    from bridge.pcb_builder import PCBBuilder
    builder = PCBBuilder.from_circuit_graph(graph, out_dir=out_dir)
    return builder.save()

def export_gerbers(pcb_path: str = None) -> dict:
    """Exporta Gerbers + Drill desde un .kicad_pcb."""
    from bridge.kicad_bridge import KiCadBridge
    from bridge.gerber_export import generate_all_manufacturing_files

    bridge = KiCadBridge()
    if not bridge.available:
        return {'error': 'KiCad no encontrado'}

    if pcb_path is None:
        pcb_path = 'output/pulselab_pcb/board.kicad_pcb'
    pcb = Path(pcb_path)
    if not pcb.exists():
        return {'error': f'PCB no encontrado: {pcb_path}. Genera primero con FORGE > Generar PCB.'}

    return generate_all_manufacturing_files(bridge._cli, pcb, pcb.parent / 'manufacturing')

def save_json(graph: CircuitGraph, path: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(graph.to_json(), f, indent=2)

def load_json(path: str) -> CircuitGraph:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return CircuitGraph.from_json(data)
