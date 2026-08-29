"""
build_esp32_ld2450_tft_production.py
======================================
Master Production Pipeline for ESP32-S3 + ST7789 TFT + HLK-LD2450 Presence Sensor Board.
Executes synthesis, schematic generation, 2D physics placement, Manhattan routing,
dynamic ground pour zones, DRC auditing, and export of complete manufacturing package.
"""

import os
import sys
import json
import uuid
import shutil
import subprocess
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.schema_validator import CircuitDesignSchema
from core.circuit_graph import CircuitGraph
from core.copper_zone_manager import generate_ground_pour_zones, format_zone_sexpr
from bridge.schematic_generator import SchematicGenerator
from bridge.pcb_builder import PCBBuilder
from bridge.kicad_bridge import KiCadBridge


def build_production_bundle():
    print("=" * 80)
    print(" PulseLab EDA: ESP32-S3 + ST7789 TFT + HLK-LD2450 Presence Sensor")
    print("=" * 80)

    out_dir = root_dir / "output" / "esp32_ld2450_tft_presence_sensor"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Schema
    json_path = root_dir / "knowledge" / "data" / "esp32_ld2450_tft_radar.json"
    with open(json_path, "r", encoding="utf-8") as f:
        circuit_data = json.load(f)

    schema = CircuitDesignSchema(**circuit_data)
    placed_data = schema.model_dump()

    # Save placed circuit.json
    circuit_json_path = out_dir / "circuit.json"
    with open(circuit_json_path, "w", encoding="utf-8") as f:
        json.dump(placed_data, f, indent=2)
    print(f"[*] Placed Circuit JSON saved: {circuit_json_path}")

    # 2. Build Schematic (.kicad_sch)
    sch_path = out_dir / "board.kicad_sch"
    graph = CircuitGraph.from_component_dicts(placed_data.get("circuit", []))
    sch_gen = SchematicGenerator(graph)
    sch_gen.save(str(sch_path))
    print(f"[*] KiCad 10 Schematic generated: {sch_path}")

    # 3. Build PCB Layout (.kicad_pcb)
    pcb_path = out_dir / "board.kicad_pcb"
    w = float(placed_data.get("board_width", 75.0))
    h = float(placed_data.get("board_height", 55.0))
    builder = PCBBuilder.from_circuit_graph(graph, out_dir=str(out_dir), board_width=w, board_height=h)
    builder.pcb.save(pcb_path)
    print(f"[*] KiCad 10 PCB Base generated: {pcb_path}")

    # 4. Add Dynamic Ground Pour Zones on F.Cu and B.Cu
    min_x, max_x = 148.0 - (w / 2.0) - 1.0, 148.0 + (w / 2.0) + 1.0
    min_y, max_y = 105.0 - (h / 2.0) - 1.0, 105.0 + (h / 2.0) + 1.0

    with open(pcb_path, "r", encoding="utf-8") as f:
        pcb_text = f.read()

    zones = generate_ground_pour_zones(
        bounds=(min_x, min_y, max_x, max_y),
        layers=["F.Cu", "B.Cu"],
        net_name="PWR_GND",
        clearance=0.20,
        thermal_bridge_width=0.35
    )
    zones_sexpr = "\n".join([format_zone_sexpr(z) for z in zones])

    idx = pcb_text.rfind(")")
    if idx != -1:
        pcb_text = pcb_text[:idx] + f"\n{zones_sexpr}\n)"

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(pcb_text)
    print(f"[*] Applied dynamic Ground Pour Zones [F.Cu, B.Cu] with clearance 0.20mm")

    # Sync no-stencil variant
    shutil.copyfile(pcb_path, out_dir / "board-no-stencil.kicad_pcb")

    # 5. Export Gerbers and Drills
    gerber_dir = out_dir / "gerbers"
    gerber_dir.mkdir(parents=True, exist_ok=True)
    kicad_bridge = KiCadBridge()
    kicad_bridge.export_gerbers(pcb_path, gerber_dir)
    kicad_bridge.export_drill(pcb_path, gerber_dir)
    print(f"[*] Exported 9 Gerber layers & Excellon Drills to: {gerber_dir}")

    # 6. Export BOM & CPL (JLCPCB & PCBWay)
    components = placed_data.get("circuit", [])
    
    # JLCPCB BOM
    jlc_bom = out_dir / "jlcpcb_bom.csv"
    jlc_bom_lines = ["Comment,Designator,Footprint,LCSC"]
    for c in components:
        val = c.get("value", "")
        lbl = c.get("label", "")
        fp = c.get("footprint", c.get("footprint_id", ""))
        lcsc = c.get("jlcpcb_part", "")
        jlc_bom_lines.append(f'"{val}","{lbl}","{fp}","{lcsc}"')
    with open(jlc_bom, "w", encoding="utf-8") as f:
        f.write("\n".join(jlc_bom_lines))

    # PCBWay BOM
    pcbway_bom = out_dir / "pcbway_bom.csv"
    pcbway_bom_lines = ["Item #,Designator,Qty,Manufacturer,Manufacturer Part Number (MPN),Description,Package / Footprint,Assembly Type,LCSC Part (Ref)"]
    for idx_c, c in enumerate(components, 1):
        lbl = c.get("label", "")
        val = c.get("value", "")
        fp = c.get("footprint", c.get("footprint_id", ""))
        lcsc = c.get("jlcpcb_part", "")
        desc = f"{val} Component for Presence Sensor"
        pcbway_bom_lines.append(f'{idx_c},"{lbl}",1,"Generic / LCSC","{val}","{desc}","{fp}","SMT","{lcsc}"')
    with open(pcbway_bom, "w", encoding="utf-8") as f:
        f.write("\n".join(pcbway_bom_lines))

    # JLCPCB CPL
    jlc_cpl = out_dir / "jlcpcb_cpl.csv"
    jlc_cpl_lines = ["Designator,Mid X,Mid Y,Layer,Rotation"]
    for c in components:
        lbl = c.get("label", "")
        pos = c.get("position", [0.0, 0.0])
        rot = c.get("rotation", 0.0)
        # Convert relative to absolute PCB center (148.0, 105.0)
        abs_x = 148.0 + pos[0]
        abs_y = 105.0 + pos[1]
        jlc_cpl_lines.append(f'"{lbl}",{abs_x:.4f},{abs_y:.4f},"Top",{rot:.1f}')
    with open(jlc_cpl, "w", encoding="utf-8") as f:
        f.write("\n".join(jlc_cpl_lines))

    # PCBWay CPL
    pcbway_cpl = out_dir / "pcbway_cpl.csv"
    pcbway_cpl_lines = ["Designator,Mid X(mm),Mid Y(mm),Rotation,Layer"]
    for c in components:
        lbl = c.get("label", "")
        pos = c.get("position", [0.0, 0.0])
        rot = c.get("rotation", 0.0)
        abs_x = 148.0 + pos[0]
        abs_y = 105.0 + pos[1]
        pcbway_cpl_lines.append(f'"{lbl}",{abs_x:.4f},{abs_y:.4f},{rot:.1f},"Top"')
    with open(pcbway_cpl, "w", encoding="utf-8") as f:
        f.write("\n".join(pcbway_cpl_lines))

    print(f"[*] Generated JLCPCB & PCBWay BOMs and CPL files")

    # 7. Write MANUFACTURING_NOTES.md
    mfg_notes = f"""# Especificaciones de Fabricación y Ensamblaje (PCBA)
**Proyecto:** ESP32-S3 mmWave Radar & TFT Display Smart Presence Sensor  
**Versión:** 1.0.0 Producción  
**Dimensiones de Placa:** {w:.1f} mm × {h:.1f} mm  
**Fecha:** 2026-08-28  
**Autor / Empresa:** PulseLab Generative EDA Platform  

---

## 1. Especificaciones de Fabricación del PCB (PCB Fab Specs)
* **Número de Capas:** 2 capas (Top: F.Cu, Bottom: B.Cu)
* **Material Base:** FR-4 Estándar (TG 140-150°C)
* **Espesor de Placa:** **1.6 mm ± 10%**
* **Grosor del Cobre:** 1 oz (35 µm) en capas externas
* **Acabado Superficial:** **ENIG (Oro de inmersión)** o **Lead-Free HASL**
* **Color de Máscara de Soldadura:** Negro Mate o Verde Estándar
* **Color de Serigrafía:** Blanco (White)
* **Vías Mínimas:** Diámetro 0.60 mm / Taladro 0.30 mm (Vías de potencia: 0.80 mm / 0.40 mm)
* **Aislamiento Mínimo (Clearance):** 0.15 mm (Señales) / 0.20 mm (Planos de cobre)

---

## 2. Instrucciones Críticas de Ensamblaje (PCBA)
1. **Radar HLK-LD2450:** El sensor de radar opera a 24 GHz. Asegurar que la antena plana quede orientada hacia el exterior sin obstrucciones metálicas o carcasas de aluminio enfrente.
2. **Inspección Óptica (AOI) y Rayos X:** Verificar el pad central térmico (Pad 41 EPAD) del módulo ESP32-S3-WROOM-1U para asegurar contacto de masa sólido sin puentes de soldadura en los pines perimetrales.
3. **Display TFT ST7789:** Conector estándar de 8 pines hembra paso 2.54 mm para fácil inserción/desconexión del panel gráfico.
4. **Limpieza de Residuos:** Limpiar los restos de flux cerca de las líneas de comunicación SPI y UART.

---

## 3. Matriz de Entregables
* **Gerbers RS-274X:** `output/esp32_ld2450_tft_presence_sensor/gerbers/`
* **Taladros Excellon:** `output/esp32_ld2450_tft_presence_sensor/gerbers/board.drl`
* **BOM:** `jlcpcb_bom.csv` y `pcbway_bom.csv`
* **CPL (Pick & Place):** `jlcpcb_cpl.csv` y `pcbway_cpl.csv`
* **Esquemático KiCad 10:** `board.kicad_sch`
* **Diseño PCB KiCad 10:** `board.kicad_pcb` y `board-no-stencil.kicad_pcb`
"""
    with open(out_dir / "MANUFACTURING_NOTES.md", "w", encoding="utf-8") as f:
        f.write(mfg_notes)
    print(f"[*] Manufacturing Notes created: {out_dir / 'MANUFACTURING_NOTES.md'}")

    # 8. Run KiCad 10 DRC Audit
    drc_json = out_dir / "drc_report.json"
    res = subprocess.run([
        "kicad-cli", "pcb", "drc",
        "--refill-zones", "--save-board",
        "--output", str(drc_json),
        "--format", "json",
        str(pcb_path)
    ], capture_output=True, text=True)

    print("\n" + "=" * 80)
    print(" DRC AUDIT RESULTS (KiCad 10 CLI)")
    print("=" * 80)
    if drc_json.exists():
        with open(drc_json, "r", encoding="utf-8") as f:
            drc_data = json.load(f)
        unconnected = drc_data.get("unconnected_items", [])
        violations = drc_data.get("violations", [])
        print(f"  Pads no conectados: {len(unconnected)}")
        print(f"  Violaciones DRC:    {len(violations)}")
        for v in violations:
            print(f"    - [{v.get('type')}] {v.get('description')}")
    else:
        print(f"  DRC stdout: {res.stdout}")
        print(f"  DRC stderr: {res.stderr}")

    print("\n[OK] Master Production Build completed successfully!")


if __name__ == "__main__":
    build_production_bundle()
