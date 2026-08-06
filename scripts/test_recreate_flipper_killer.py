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

def run_essay():
    json_path = root_dir / "knowledge/data/flipper_multiboard_pcb.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    circuit = data.get("circuit", [])
    net_classes = data.get("net_classes", {})

    print("==================================================")
    print(" ENSAYO: RECREACION DE FLIPPER_KILLER_MK_II_0.2")
    print("==================================================")

    # 1. SEMANTIC VALIDATION
    print("\n1. VALIDACION SEMANTICA Y GRAFO DE CIRCUITO:")
    graph = CircuitGraph.from_component_dicts(circuit)
    print(f"  [OK] CircuitGraph construido con exito:")
    print(f"     - Componentes principales: {len(graph.components)}")
    for c in graph.components:
        print(f"       * [{c.uid}] {c.etype} value={c.value} footprint={c.footprint_id}")
    print(f"     - Redes logicas principales: {len(graph.all_nodes)}")

    out_dir = root_dir / "output"
    project_name = "Flipper killer mk II 0.2"
    sub_dir = "flipper_killer_mk_ii_0.2"

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

    print(f"\n  [OK] PCB & Esquetmatico (.kicad_sch) Generados:")
    print(f"     - PCB Path: {pcb_path}")
    print(f"     - SCH Path: {sch_path}")
    print(f"     - Dimensiones de la placa: {stats.get('board_mm')} mm")
    print(f"     - Footprints colocados: {stats.get('footprints')}")
    print(f"     - Pistas (Traces): {stats.get('traces')}")
    print(f"     - Vias: {stats.get('vias')}")
    print(f"     - Redes asignadas: {stats.get('nets')}")
    print(f"     - Agujeros de montaje M3: {stats.get('mounting_holes')}")

    bridge = KiCadBridge()
    cli = bridge._cli

    # Fill zones with kicad-cli prior to DRC & exports
    if cli and cli.exists():
        print("\n  [...] Rellenando zonas de plano de masa (GND copper pour)...")
        fill_res = subprocess.run(
            [str(cli), "pcb", "fill-zones", str(pcb_path)],
            capture_output=True, text=True, timeout=30
        )
        if fill_res.returncode == 0:
            print("  [OK] Relleno de plano de masa GND completado con exito en KiCad CLI.")
        else:
            print(f"  [WARN] Warning en fill-zones: {fill_res.stderr.strip()}")

    # 2. DRC VALIDATION
    print("\n2. VALIDACION DRC (KiCad 10.0 CLI Design Rules Check):")
    if bridge.available:
        drc_res = bridge.run_drc(pcb_path, output_dir=pcb_path.parent)
        violations = drc_res.get("violations", [])
        warnings = drc_res.get("warnings", [])
        
        # Categorize violations
        type_counts = {}
        for v in violations:
            vtype = v.get("type", "other")
            type_counts[vtype] = type_counts.get(vtype, 0) + 1

        print(f"  - Ejecutable CLI: {bridge._cli}")
        print(f"  - Version KiCad: {bridge.version}")
        print(f"  - Total Violaciones DRC: {len(violations)}")
        print(f"  - Total Advertencias DRC: {len(warnings)}")
        
        if type_counts:
            print("  - Desglose de Violaciones DRC por Categoria:")
            for vtype, count in type_counts.items():
                print(f"    * [{vtype}]: {count} elementos")

        if violations:
            print("  - Muestra de Violaciones:")
            for v in violations[:8]:
                items_str = ", ".join([i.get("description", "") for i in v.get("items", [])])
                print(f"    * [{v.get('type')}] {v.get('description')} -> {items_str}")
        else:
            print("  - NO DRC VIOLATIONS FOUND!")
    else:
        print("  [ERROR] KiCad CLI no disponible para DRC.")

    # 3. VISUAL VALIDATION & EXPORTS
    print("\n3. VALIDACION VISUAL Y EXPORTACION DE RENDERIZADOS:")
    if cli and cli.exists():
        # Export SVG Preview
        svg_file = pcb_path.parent / "board_preview.svg"
        try:
            res_svg = subprocess.run(
                [str(cli), "pcb", "export", "svg",
                 "--output", str(svg_file),
                 "--layers", "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts",
                 "--page-size-mode", "2",
                 str(pcb_path)],
                capture_output=True, text=True, timeout=30
            )
            if res_svg.returncode == 0 and svg_file.exists():
                print(f"  [OK] Render 2D Vectorial (SVG) generado:")
                print(f"     - Ruta SVG: {svg_file}")
                print(f"     - Tamano: {svg_file.stat().st_size / 1024:.1f} KB")
            else:
                print(f"  [WARN] SVG Note: {res_svg.stderr.strip()}")
        except Exception as e:
            print(f"  [WARN] Error renderizando SVG: {e}")

        # Export 3D GLTF Render
        r3d = RenderEngine3D()
        if r3d.available:
            gltf_file = pcb_path.parent / "board_3d.gltf"
            gltf_res = r3d.export_gltf(str(pcb_path), str(gltf_file))
            if gltf_res.get("status") == "ok":
                print(f"  [OK] Render 3D Volumetrico (GLTF) generado:")
                print(f"     - Ruta GLTF: {gltf_res.get('path')}")
                print(f"     - Tamano: {gltf_res.get('size_bytes') / 1024:.1f} KB")
            else:
                print(f"  [WARN] Render 3D info: {gltf_res.get('error')}")

        # Export Gerbers & Drill
        gerber_dir = pcb_path.parent / "gerbers"
        gb_res = bridge.export_gerbers(pcb_path, output_dir=gerber_dir)
        drill_res = bridge.export_drill(pcb_path, output_dir=gerber_dir)
        pos_res = bridge.export_position(pcb_path, output_dir=gerber_dir)

        print(f"  [OK] Paquete de Fabricacion Gerber Exportado:")
        print(f"     - Directorio Gerbers: {gerber_dir}")
        print(f"     - Capas de cobre/silkscreen/mask: {len(gb_res.get('files', []))} archivos .gbr")
        print(f"     - Archivos de Taladros Excellon (.drl): {drill_res.get('status')}")
        print(f"     - Coordenadas Pick & Place (.pos): {pos_res.get('status')}")

    print("\n==================================================")
    print(" ENSAYO FLIPPER_KILLER_MK_II_0.2 COMPLETADO")
    print("==================================================")

if __name__ == "__main__":
    run_essay()
