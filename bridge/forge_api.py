
import os
import json
import datetime
import re
from pathlib import Path
from typing import Optional

from ui.editor import CircuitGraph

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
    from bridge.pcb_layout import PCBLayout

    comps = graph.components
    n = len(comps)
    # Auto-size board based on component count
    cols = max(2, int(n ** 0.5) + 1)
    w = max(30, cols * 15)
    h = max(20, (n // cols + 2) * 12)

    pcb = PCBLayout(board_width=w, board_height=h,
                    corner_radius=1.5, project_name='PulseLab Design')

    # Place components in a grid
    row, col = 0, 0
    margin_x, margin_y = 8.0, 8.0
    spacing_x, spacing_y = 12.0, 10.0

    for c in comps:
        x = margin_x + col * spacing_x
        y = margin_y + row * spacing_y
        etype = c.etype
        ref   = c.uid
        val   = f"{c.value:.6g}" if isinstance(c.value, float) else str(c.value)

        if etype in ('R',):
            pcb.add_resistor(ref, val, x, y, net1=c.n1, net2=c.n2)
        elif etype in ('C',):
            pcb.add_capacitor(ref, val, x, y, net1=c.n1, net2=c.n2)
        elif etype in ('L',):
            pcb.add_inductor(ref, val, x, y, net1=c.n1, net2=c.n2)
        elif etype in ('V',):
            pcb.add_pin_header(ref, 2, x, y, value=f"{val}V")
        elif etype in ('IC', 'MCU'):
            pkg = "SOP16"
            is_esp = ("ESP" in val.upper() or "NODE" in val.upper())
            if is_esp: pkg = "ESP32"
            if "CH340" in val.upper() or "SOP8" in val.upper(): pkg = "SOP8"
            
            fp = pcb.add_ic(ref, val, x, y, pins=getattr(c, 'pins', {}), pkg_type=pkg)
            
            # --- Mejoras Profesionales (v2.1) ---
            # 1. Decoupling Capacitors (10uF + 100nF)
            # Buscamos pines de poder (3V3, VCC, VBUS)
            power_nets = [n for n in getattr(c, 'pins', {}).values() if n in ('3V3', 'VCC', 'VBUS', '5V')]
            if power_nets:
                p_net = power_nets[0]
                pcb.add_capacitor(f"C_{ref}_H", "10uF", x+5, y-5, net1=p_net, net2="GND")
                pcb.add_capacitor(f"C_{ref}_L", "100nF", x+8, y-5, net1=p_net, net2="GND")
            
            # 2. Antenna Keep-out (solo para ESP32)
            if is_esp:
                # El footprint ESP32-WROOM mide 18x25.5mm. Antena en la parte superior.
                # Definimos zona de exclusión de 18x6mm en el tope.
                pcb.add_keepout([
                    (x - 9, y - 13), (x + 9, y - 13),
                    (x + 9, y - 7),  (x - 9, y - 7)
                ])
        else:
            pcb.add_pin_header(ref, 2, x, y, value=etype)

        col += 1
        if col >= cols:
            col = 0
            row += 1

    if n >= 4:
        pcb.add_mounting_holes_corners(margin=3.0)

    pcb.add_text('PulseLab Forge', pcb.board.center_x,
                 pcb.board.origin_y + pcb.board.height_mm + 2, size=0.8)

    # Añadir plano de masa si existe el nodo GND
    if "GND" in graph.all_nodes:
        pcb.add_copper_pour("GND", margin=1.0)
        
    # Ejecutar nuestro A* auto-router 2D/2L
    pcb.autoroute(width=0.25, grid_size=0.25)

    # Exportar Schematic (.kicad_sch)
    from bridge.schematic_generator import SchematicGenerator
    sch_path = Path(out_dir) / 'pulselab_pcb' / 'board.kicad_sch'
    sch_gen = SchematicGenerator(graph)
    sch_gen.save(str(sch_path))

    # Exportar PCB y KiCad Pro
    out_path = Path(out_dir) / 'pulselab_pcb' / 'board.kicad_pcb'
    pcb.save(out_path)
    
    return {'path': str(out_path), 'stats': pcb.stats(), 'pcb': pcb, 'sch_path': str(sch_path)}

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
