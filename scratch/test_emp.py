import sys
import os
import json
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.abspath('.'))
from pulse_lab import _load_preset, _generate_pcb
from bridge.kicad_bridge import KiCadBridge

print("1. Cargando EMP PFN 5kV...")
graph = _load_preset('emp_pfn')
print(f"Nodos: {len(graph.all_nodes)}, Componentes: {len(graph.components)}")

print("\n2. Generando PCB y Auto-enrutando (ahora con clearance de 0.35mm)...")
res = _generate_pcb(graph, out_dir="output/test_emp")
pcb_path = Path(res['path'])
pcb = res['pcb']

print(f"Ruta: {pcb_path}")
print(f"Stats: {res['stats']}")

print("\n3. Revisando el Diseño (IA DRC)...")
from knowledge.layout_reviewer import LayoutReviewer
rev = LayoutReviewer(pcb)
report_data = rev.audit()
print(f"DRC Pasado (Sin errores criticos): {report_data['passed']}")
print("Imprimiendo reporte:")
print(rev.generate_report())

print("\n4. Exportando render SVG con kicad-cli...")
bridge = KiCadBridge()
if bridge.available:
    cli = str(bridge._cli)
    svg_out = pcb_path.parent / "board_render.svg"
    cmd = [
        cli, "pcb", "export", "svg",
        "--layers", "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts",
        "--output", str(svg_out),
        str(pcb_path)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"SVG Generado exitosamente en: {svg_out}")
    except subprocess.CalledProcessError as e:
        print(f"Error generando SVG: {e.stderr}")
else:
    print("kicad-cli no disponible")
