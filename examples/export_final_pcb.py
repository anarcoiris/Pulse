"""
export_final_pcb.py
===================
Script to take the generated JSON for PulseLab Zero and export it via Forge API
to KiCad schematic and PCB, so the user can visually inspect the results.
"""

import json
from pathlib import Path
from core.circuit_graph import CircuitGraph
from bridge.forge_api import generate_pcb

def export_json_to_pcb(json_path: str):
    p = Path(json_path)
    if not p.exists():
        print(f"Error: No se encuentra {json_path}")
        return

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    components = data.get("circuit", [])
    if not components:
        print("El archivo JSON no contiene componentes válidos.")
        return

    print(f"Cargando {len(components)} componentes desde {p.name}...")
    graph = CircuitGraph.from_component_dicts(components)

    print("Generando PCB y Esquemático...")
    res = generate_pcb(graph)

    import subprocess
    
    if "error" in res:
        print(f"❌ Error al generar PCB: {res['error']}")
    else:
        print(f"✅ Generación Exitosa.")
        sch_path = res.get('sch_path', '')
        pcb_path = res.get('path', '')
        print(f"📄 Esquemático guardado en: {sch_path}")
        print(f"🖨️ PCB guardado en: {pcb_path}")
        
        if sch_path:
            out_pdf = sch_path.replace(".kicad_sch", ".pdf")
            print(f"📸 Exportando PDF del esquemático...")
            subprocess.run(["kicad-cli", "sch", "export", "pdf", sch_path, "-o", out_pdf], check=False)
            
        if pcb_path:
            out_svg = pcb_path.replace(".kicad_pcb", ".svg")
            print(f"📸 Exportando SVG del PCB a {out_svg}...")
            layers = "F.Cu,B.Cu,F.SilkS,F.Mask,Edge.Cuts"
            subprocess.run(["kicad-cli", "pcb", "export", "svg", pcb_path, "-l", layers, "-o", out_svg], check=False)
            print(f"✅ SVG PCB generado.")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    json_target = "knowledge/data/validation_complex/esp32_rf_nfc.json"
    export_json_to_pcb(json_target)
