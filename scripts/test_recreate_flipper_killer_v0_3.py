import json
import sys
import subprocess
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.circuit_graph import CircuitGraph
from bridge.pcb_builder import PCBBuilder
from bridge.kicad_bridge import KiCadBridge
from bridge.render_engine import RenderEngine3D

def run_phase1():
    json_path = root_dir / "knowledge/data/flipper_multiboard_pcb.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    circuit = data.get("circuit", [])
    net_classes = data.get("net_classes", {})

    print("==================================================")
    print(" FASE 1: RECREACION E INTERACCION DE FLIPPER_KILLER_MK_II_0.3")
    print("==================================================")

    # 1. SEMANTIC VALIDATION
    print("\n1. GRAFO DE CIRCUITO Y ASIGNACION DE FOOTPRINTS:")
    graph = CircuitGraph.from_component_dicts(circuit)
    print(f"  [OK] CircuitGraph reconstruido:")
    print(f"     - Componentes: {len(graph.components)}")
    for c in graph.components:
        print(f"       * [{c.uid}] {c.etype} value={c.value} footprint={c.footprint_id}")
    print(f"     - Redes logicas: {len(graph.all_nodes)}")

    out_dir = root_dir / "output"
    project_name = "Flipper killer mk II 0.3"
    sub_dir = "flipper_killer_mk_ii_0.3"

    builder = PCBBuilder.from_circuit_graph(
        graph,
        out_dir=str(out_dir),
        project_name=project_name,
        net_classes=net_classes,
    )
    result = builder.save(sub_dir=sub_dir)

    pcb_path = Path(result["path"])
    sch_path = Path(result.get("sch_path"))
    stats = result.get("stats", {})

    print(f"\n  [OK] PCB & Esquetmatico v0.3 Generados:")
    print(f"     - PCB Path: {pcb_path}")
    print(f"     - SCH Path: {sch_path}")
    print(f"     - Placa: {stats.get('board_mm')} mm")
    print(f"     - Footprints colocados: {stats.get('footprints')}")
    print(f"     - Pistas (Traces): {stats.get('traces')}")
    print(f"     - Vias: {stats.get('vias')}")
    print(f"     - Redes asignadas: {stats.get('nets')}")
    print(f"     - Agujeros M3: {stats.get('mounting_holes')}")

    bridge = KiCadBridge()
    cli = bridge._cli

    if cli and cli.exists():
        print("\n  [...] Rellenando plano GND (fill-zones)...")
        fill_res = subprocess.run(
            [str(cli), "pcb", "fill-zones", str(pcb_path)],
            capture_output=True, text=True, timeout=30
        )
        if fill_res.returncode == 0:
            print("  [OK] Plano GND rellenado con exito.")
        else:
            print(f"  [WARN] Warn en fill-zones: {fill_res.stderr.strip()}")

    # 2. DRC & STRUCTURAL AUDIT
    print("\n2. AUDITORIA DRC Y STRUCTURAL SANITY CHECK:")
    # Run kicad_audit.py
    audit_script = root_dir / "core/kicad_audit.py"
    if audit_script.exists():
        audit_res = subprocess.run(
            [sys.executable, str(audit_script), str(pcb_path)],
            capture_output=True, text=True
        )
        print("  - Reporte de kicad_audit.py:")
        print("    " + "\n    ".join(audit_res.stdout.strip().split("\n")[:15]))

    if bridge.available:
        drc_res = bridge.run_drc(pcb_path, output_dir=pcb_path.parent)
        violations = drc_res.get("violations", [])
        warnings = drc_res.get("warnings", [])
        
        type_counts = {}
        for v in violations:
            vtype = v.get("type", "other")
            type_counts[vtype] = type_counts.get(vtype, 0) + 1

        print(f"\n  - KiCad CLI DRC (v10.0.3): Total Violaciones = {len(violations)}, Advertencias = {len(warnings)}")
        for vtype, count in type_counts.items():
            print(f"    * [{vtype}]: {count} elementos")

    # 3. VISUAL RENDER (SVG & GLTF)
    print("\n3. GENERANDO PREVISUALIZACION VISUAL VECTORIAL (SVG):")
    if cli and cli.exists():
        svg_file = pcb_path.parent / "board_preview.svg"
        res_svg = subprocess.run(
            [str(cli), "pcb", "export", "svg",
             "--output", str(svg_file),
             "--layers", "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts",
             "--page-size-mode", "2",
             str(pcb_path)],
            capture_output=True, text=True, timeout=30
        )
        if res_svg.returncode == 0 and svg_file.exists():
            print(f"  [OK] SVG Render listo:")
            print(f"     - Ruta SVG: {svg_file}")
            print(f"     - Tamano: {svg_file.stat().st_size / 1024:.1f} KB")

    print("\n==================================================")
    print(" FASE 1 COMPLETADA CON EXITO")
    print("==================================================")

if __name__ == "__main__":
    run_phase1()
