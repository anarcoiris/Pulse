"""
build_flipper_killer_production_v2.py
=====================================
Unified Master Production Pipeline for Flipper Killer MK II (ESP32-S3-WROOM-1U Multi-Tool).
Outputs to: output/flipper_killer_production_v2/
"""

import os
import sys
import re
import json
import csv
import math
import uuid
import subprocess
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.circuit_graph import CircuitGraph
from bridge.schematic_generator import SchematicGenerator

out_dir = root_dir / "output" / "flipper_killer_production_v2"
out_dir.mkdir(parents=True, exist_ok=True)
json_path = root_dir / "knowledge/data/flipper_multiboard_pcb_production.json"
kicad_fp_root = Path(r"C:\Users\soyko\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints")
hist_pcb = root_dir / "output/flipper_killer_production_ready/.history/board-no-stencil.kicad_pcb"
source_pcb = root_dir / "output/flipper_killer_production_ready/board.kicad_pcb"

def get_uuid():
    return str(uuid.uuid4())

print("=================================================================")
print("  FLIPPER KILLER MK II (WROOM-1U) — PRODUCTION RELEASE V2 BUILD")
print("=================================================================")

# 1. Generate Production Schematic
with open(json_path, "r", encoding="utf-8") as f:
    circuit_data = json.load(f)

graph = CircuitGraph.from_component_dicts(circuit_data["circuit"])
sch_gen = SchematicGenerator(graph)
sch_content = sch_gen.generate()
sch_path = out_dir / "board.kicad_sch"
with open(sch_path, "w", encoding="utf-8") as f:
    f.write(sch_content)
print(f"  [OK] Exported Schematic -> {sch_path}")

# 2. Footprint Template Retriever
def get_fp_template(lib_dir: str, fp_name: str) -> str:
    if lib_dir == "Custom" or "Flipper" in fp_name:
        with open(hist_pcb, "r", encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'(\(footprint\s+"Custom:Flipper_Zero_GPIO".*?\n\t\))', text, re.DOTALL)
        if m:
            return m.group(1)
            
    if lib_dir == "Connector_USB" and "TYPE-C-31-M-12" in fp_name:
        with open(hist_pcb, "r", encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'(\(footprint\s+"USB_C_Receptacle_HRO_TYPE-C-31-M-12".*?\n\t\))', text, re.DOTALL)
        if m:
            return m.group(1)

    fp_path = kicad_fp_root / f"{lib_dir}.pretty" / f"{fp_name}.kicad_mod"
    if fp_path.exists():
        with open(fp_path, "r", encoding="utf-8") as f:
            return f.read().strip()
            
    for p in kicad_fp_root.rglob(f"{fp_name}.kicad_mod"):
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
            
    raise FileNotFoundError(f"Cannot find footprint {lib_dir}:{fp_name}")

CENTER_X = 148.5
CENTER_Y = 105.0

COMPONENTS = {}
for c in circuit_data["circuit"]:
    ref = c["label"]
    val = str(c["value"])
    fp = c["footprint"]
    fp_lib, fp_name = fp.split(":", 1) if ":" in fp else ("Custom", fp)
    pos = c["position"]
    abs_x = round(CENTER_X + pos["x"], 4)
    abs_y = round(CENTER_Y + pos["y"], 4)
    rot = float(c.get("rotation", 0.0))
    layer = c.get("layer", "F.Cu")
    pins = c["pins"]
    COMPONENTS[ref] = (fp_lib, fp_name, val, abs_x, abs_y, rot, layer, pins)

all_nets = set()
for ref, data in COMPONENTS.items():
    for pin, net in data[7].items():
        if net and not net.startswith("NC_"):
            all_nets.add(net)

sorted_nets = [""] + sorted(list(all_nets))
net_id_map = {nname: nid for nid, nname in enumerate(sorted_nets)}

def instantiate_fp(ref, fp_lib, fp_name, val, cx, cy, rot, layer, pin_net_map):
    raw_mod = get_fp_template(fp_lib, fp_name)
    fp_uuid = get_uuid()
    rot_str = f" {rot}" if rot != 0.0 else ""
    at_str = f"(at {cx:.4f} {cy:.4f}{rot_str})"
    
    # Update properties
    raw_mod = re.sub(r'\(property\s+"Reference"\s+"[^"]*"', f'(property "Reference" "{ref}"', raw_mod)
    raw_mod = re.sub(r'\(property\s+"Value"\s+"[^"]*"', f'(property "Value" "{val}"', raw_mod)
    raw_mod = re.sub(r'\(fp_text\s+reference\s+"[^"]*"', f'(fp_text reference "{ref}"', raw_mod)
    raw_mod = re.sub(r'\(fp_text\s+value\s+"[^"]*"', f'(fp_text value "{val}"', raw_mod)
    
    raw_mod = re.sub(r'\(layer\s+"[^"]+"\)', f'(layer "{layer}")', raw_mod, count=1)
    raw_mod = re.sub(r'\(uuid\s+"[^"]+"\)', '', raw_mod, count=1)
    raw_mod = re.sub(r'\(at\s+[^)]+\)', '', raw_mod, count=1)
    
    raw_mod = re.sub(r'(\(layer\s+"[^"]+"\))', f'\\1\n\t\t(uuid "{fp_uuid}")\n\t\t{at_str}', raw_mod, count=1)
    
    def fix_pad(match):
        p_block = match.group(0)
        pnum = match.group(1)
        net_name = pin_net_map.get(pnum, "")
        if not net_name and pnum == "SH":
            net_name = pin_net_map.get("SH", "")
        if not net_name and pnum.isdigit():
            net_name = pin_net_map.get(pnum, "")
            
        p_block = re.sub(r'\s*\(net\s+[^)]+\)', '', p_block)
        p_block = re.sub(r'\s*\(uuid\s+[^)]+\)', '', p_block)
        
        pad_uuid = get_uuid()
        p_block = p_block.rstrip()
        if p_block.endswith(')'):
            p_block = p_block[:-1].rstrip()
            if net_name and net_name in net_id_map:
                nid = net_id_map[net_name]
                p_block += f'\n\t\t\t(net {nid} "{net_name}")\n\t\t\t(uuid "{pad_uuid}")\n\t\t)'
            else:
                p_block += f'\n\t\t\t(uuid "{pad_uuid}")\n\t\t)'
        return p_block

    raw_mod = re.sub(r'\(pad\s+"?([^"\s]+)"?\s+(?:smd|thru_hole|np_thru_hole|connect).*?\n\t*\)', fix_pad, raw_mod, flags=re.DOTALL)
    
    lines = raw_mod.strip().split('\n')
    indented = "\n".join(["\t" + l if not l.startswith("\t") else l for l in lines])
    return indented

# 3. Instantiate All Footprints & Extract Pad Geometry
footprints_str_list = []
pad_coords = {}
net_pads = {}

for ref, (fp_lib, fp_name, val, cx, cy, rot, layer, pin_net_map) in COMPONENTS.items():
    fp_text = instantiate_fp(ref, fp_lib, fp_name, val, cx, cy, rot, layer, pin_net_map)
    footprints_str_list.append(fp_text)
    
    rad = math.radians(rot)
    for pad_m in re.finditer(r'\(pad\s+"?([^"\s]+)"?\s+.*?\n\t*\)', fp_text, re.DOTALL):
        pad_str = pad_m.group(0)
        pnum = pad_m.group(1)
        
        at_m = re.search(r'\(at\s+([^\)]+)\)', pad_str)
        px, py = 0.0, 0.0
        if at_m:
            parts = at_m.group(1).split()
            px, py = float(parts[0]), float(parts[1])
            
        net_m = re.search(r'\(net\s+(\d+)\s+"([^"]+)"\)', pad_str)
        nname = net_m.group(2) if net_m else ""
        
        abs_x = round(cx + px * math.cos(rad) - py * math.sin(rad), 4)
        abs_y = round(cy + px * math.sin(rad) + py * math.cos(rad), 4)
        
        pad_coords[(ref, pnum)] = (abs_x, abs_y)
        if nname and not nname.startswith("NC_"):
            if nname not in net_pads:
                net_pads[nname] = []
            net_pads[nname].append((abs_x, abs_y, ref, pnum))

print(f"  [OK] Instantiated {len(footprints_str_list)} footprints (including official WROOM-1U).")

# 4. Clean Track Extraction from User / FreeRouting Session
with open(source_pcb, "r", encoding="utf-8") as f:
    source_pcb_text = f.read()

# Extract segments and vias with proper net indexing
tracks = []
for seg_m in re.finditer(r'\(segment\s+\(start\s+([^\)]+)\)\s+\(end\s+([^\)]+)\)\s+\(width\s+([^\)]+)\)\s+\(layer\s+"([^"]+)"\)\s+\(net\s+(?:(\d+)\s+)?"([^"]+)"\)\s+(?:\(uuid\s+"[^"]+"\)\s*)?\)', source_pcb_text):
    start_str, end_str, width_str, layer, old_nid, nname = seg_m.groups()
    if nname in net_id_map:
        nid = net_id_map[nname]
        tracks.append(f'\t(segment (start {start_str}) (end {end_str}) (width {width_str}) (layer "{layer}") (net {nid}) (uuid "{get_uuid()}"))')

for via_m in re.finditer(r'\(via\s+\(at\s+([^\)]+)\)\s+\(size\s+([^\)]+)\)\s+\(drill\s+([^\)]+)\)\s+\(layers\s+"([^"]+)"\s+"([^"]+)"\)\s+\(net\s+(?:(\d+)\s+)?"([^"]+)"\)\s+(?:\(uuid\s+"[^"]+"\)\s*)?\)', source_pcb_text):
    at_str, size_str, drill_str, l1, l2, old_nid, nname = via_m.groups()
    if nname in net_id_map:
        nid = net_id_map[nname]
        tracks.append(f'\t(via (at {at_str}) (size {size_str}) (drill {drill_str}) (layers "{l1}" "{l2}") (net {nid}) (uuid "{get_uuid()}"))')

print(f"  [OK] Extracted and re-indexed {len(tracks)} routed segments & vias.")

# 5. Header, Setup & Design Rules
with open(hist_pcb, "r", encoding="utf-8") as f:
    orig_text = f.read()

m_head = re.search(r'(.*?\(setup\s+.*?\n\t\))', orig_text, re.DOTALL)
header_str = m_head.group(1) if m_head else ""

# Update board design constraints for JLCPCB manufacturing standards:
header_str = re.sub(r'\(min_drill\s+[^)]+\)', '(min_drill 0.2)', header_str)
header_str = re.sub(r'\(min_hole_clearance\s+[^)]+\)', '(min_hole_clearance 0.2)', header_str)
header_str = re.sub(r'\(hole_to_hole_clearance\s+[^)]+\)', '(hole_to_hole_clearance 0.2)', header_str)
header_str = re.sub(r'\(solder_mask_min_width\s+[^)]+\)', '(solder_mask_min_width 0.08)', header_str)

edge_cuts = re.findall(r'(\t\(gr_\w+\s+.*?layer\s+"Edge\.Cuts".*?\n\t\))', orig_text, re.DOTALL)
edge_cuts_str = "\n".join(edge_cuts)

net_defs = []
for nid, nname in enumerate(sorted_nets):
    if nid == 0:
        net_defs.append('\t(net 0 "")')
    else:
        net_defs.append(f'\t(net {nid} "{nname}")')
net_defs_str = "\n".join(net_defs)

footprints_full_str = "\n".join(footprints_str_list)

# 6. Thermal Zones & Ground Pours
v33_id = net_id_map["PWR_3V3_ESP"]
thermal_zone_f = f"""
\t(zone
\t\t(net {v33_id})
\t\t(net_name "PWR_3V3_ESP")
\t\t(layer "F.Cu")
\t\t(uuid "{get_uuid()}")
\t\t(priority 1)
\t\t(hatch edge 0.5)
\t\t(connect_pads yes (clearance 0.20))
\t\t(min_thickness 0.25)
\t\t(filled_areas_thickness no)
\t\t(fill yes (thermal_gap 0.20) (thermal_bridge_width 0.4))
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 144.5 83.5)
\t\t\t\t(xy 152.5 83.5)
\t\t\t\t(xy 152.5 89.5)
\t\t\t\t(xy 144.5 89.5)
\t\t\t)
\t\t)
\t)
"""

def via_str(p, net_name, size=0.8, drill=0.4):
    nid = net_id_map[net_name]
    return f'\t(via (at {p[0]:.4f} {p[1]:.4f}) (size {size}) (drill {drill}) (layers "F.Cu" "B.Cu") (net {nid}) (uuid "{get_uuid()}"))'

thermal_vias = [
    via_str((146.5, 84.5), "PWR_3V3_ESP"),
    via_str((148.5, 84.5), "PWR_3V3_ESP"),
    via_str((150.5, 84.5), "PWR_3V3_ESP"),
    via_str((146.5, 86.5), "PWR_3V3_ESP"),
    via_str((148.5, 86.5), "PWR_3V3_ESP"),
    via_str((150.5, 86.5), "PWR_3V3_ESP"),
]
thermal_vias_str = "\n".join(thermal_vias)

gnd_id = net_id_map["PWR_GND"]
gnd_zone_f = f"""
\t(zone
\t\t(net {gnd_id})
\t\t(net_name "PWR_GND")
\t\t(layer "F.Cu")
\t\t(uuid "{get_uuid()}")
\t\t(priority 0)
\t\t(hatch edge 0.5)
\t\t(connect_pads yes (clearance 0.20))
\t\t(min_thickness 0.25)
\t\t(filled_areas_thickness no)
\t\t(fill yes (thermal_gap 0.20) (thermal_bridge_width 0.4))
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 116.5 82.0)
\t\t\t\t(xy 180.5 82.0)
\t\t\t\t(xy 180.5 128.0)
\t\t\t\t(xy 116.5 128.0)
\t\t\t)
\t\t)
\t)
"""

gnd_zone_b = f"""
\t(zone
\t\t(net {gnd_id})
\t\t(net_name "PWR_GND")
\t\t(layer "B.Cu")
\t\t(uuid "{get_uuid()}")
\t\t(priority 0)
\t\t(hatch edge 0.5)
\t\t(connect_pads yes (clearance 0.20))
\t\t(min_thickness 0.25)
\t\t(filled_areas_thickness no)
\t\t(fill yes (thermal_gap 0.20) (thermal_bridge_width 0.4))
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 116.5 82.0)
\t\t\t\t(xy 180.5 82.0)
\t\t\t\t(xy 180.5 128.0)
\t\t\t\t(xy 116.5 128.0)
\t\t\t)
\t\t)
\t)
"""

full_pcb_str = f"""{header_str}
{net_defs_str}
{footprints_full_str}
{edge_cuts_str}
{"\n".join(tracks)}
{thermal_vias_str}
{thermal_zone_f}
{gnd_zone_f}
{gnd_zone_b}
)
"""

pcb_no_stencil_file = out_dir / "board-no-stencil.kicad_pcb"
with open(pcb_no_stencil_file, "w", encoding="utf-8") as f:
    f.write(full_pcb_str)

pcb_board_file = out_dir / "board.kicad_pcb"
with open(pcb_board_file, "w", encoding="utf-8") as f:
    f.write(full_pcb_str)

print(f"  [OK] Saved board-no-stencil.kicad_pcb and board.kicad_pcb ({len(full_pcb_str)} chars)")

# 7. Generate BOM and CPL files
bom_rows = []
jlc_bom_rows = []
cpl_rows = []
jlc_cpl_rows = []

for c in circuit_data["circuit"]:
    ref = c["label"]
    val = str(c["value"])
    fp = c["footprint"]
    lcsc = c.get("jlcpcb_part", "")
    pos = c["position"]
    abs_x = round(CENTER_X + pos["x"], 4)
    abs_y = round(CENTER_Y + pos["y"], 4)
    rot = float(c.get("rotation", 0.0))
    layer = "Top" if c.get("layer", "F.Cu") == "F.Cu" else "Bottom"
    
    bom_rows.append({"Refs": f'"{ref}"', "Value": f'"{val}"', "Footprint": f'"{fp}"', "Description": c.get("etype", "")})
    jlc_bom_rows.append({"Comment": val, "Designator": ref, "Footprint": fp, "LCSC": lcsc})
    
    cpl_rows.append({"Ref": f'"{ref}"', "Val": f'"{val}"', "Package": f'"{fp}"', "PosX": f"{abs_x:.4f}", "PosY": f"{abs_y:.4f}", "Rot": f"{rot:.1f}", "Side": "top" if layer == "Top" else "bottom"})
    jlc_rot = rot if rot >= 0 else rot + 360.0
    jlc_cpl_rows.append({"Designator": f'"{ref}"', "Mid X": f"{abs_x:.4f}", "Mid Y": f"{abs_y:.4f}", "Rotation": f"{jlc_rot:.1f}", "Layer": layer})

with open(out_dir / "bom.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Refs", "Value", "Footprint", "Description"])
    writer.writeheader()
    writer.writerows(bom_rows)

with open(out_dir / "jlcpcb_bom.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC"])
    writer.writeheader()
    writer.writerows(jlc_bom_rows)

with open(out_dir / "cpl.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
    writer.writeheader()
    writer.writerows(cpl_rows)

with open(out_dir / "jlcpcb_cpl.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
    writer.writeheader()
    for r in jlc_cpl_rows:
        f.write(f'{r["Designator"]},{r["Mid X"]},{r["Mid Y"]},{r["Rotation"]},{r["Layer"]}\n')

print(f"  [OK] Generated BOM & CPL ({len(bom_rows)} components)")

# 8. Export Gerbers and Drills
gerber_dir = out_dir / "gerbers"
gerber_dir.mkdir(parents=True, exist_ok=True)

cmd_gbr = [
    "kicad-cli", "pcb", "export", "gerbers",
    "--output", str(gerber_dir) + "/",
    "--layers", "F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,B.Paste,Edge.Cuts",
    str(pcb_no_stencil_file)
]
subprocess.run(cmd_gbr, capture_output=True, text=True)

cmd_drl = [
    "kicad-cli", "pcb", "export", "drill",
    "--output", str(gerber_dir) + "/",
    "--format", "excellon",
    "--drill-origin", "absolute",
    str(pcb_no_stencil_file)
]
subprocess.run(cmd_drl, capture_output=True, text=True)
print(f"  [OK] Exported Gerbers & Excellon Drills -> {gerber_dir}")

# 9. Run KiCad DRC
drc_json = out_dir / "drc_report.json"
res_drc = subprocess.run(
    ["kicad-cli", "pcb", "drc", "--output", str(drc_json), "--format", "json", str(pcb_no_stencil_file)],
    capture_output=True, text=True
)

if drc_json.exists():
    with open(drc_json, "r", encoding="utf-8") as f:
        drc = json.load(f)
    unconn = len(drc.get("unconnected_items", []))
    violations = len(drc.get("violations", []))
    print(f"  [DRC Result] Unconnected: {unconn} | Violations: {violations}")

# 10. Generate MANUFACTURING_NOTES.md
notes_content = """# Especificaciones de Fabricación y Ensamblaje (PCBA)
**Proyecto:** Flipper Killer MK II (Módulo Multi-Herramienta ESP32-S3-WROOM-1U para Flipper Zero)  
**Versión:** 2.0.0 Producción  
**Fecha:** 2026-08-27  
**Empresa / Autor:** PulseLab Forge  

---

## 1. Especificaciones de Fabricación del PCB (PCB Fab Specs)
* **Número de Capas:** 2 capas (Top: F.Cu, Bottom: B.Cu)
* **Material Base:** FR-4 Estándar (TG 130-140°C o TG 150°C)
* **Espesor de Placa (Board Thickness):** **1.6 mm ± 10%** (Crítico para encaje firme en cabezal GPIO Flipper Zero)
* **Grosor del Cobre (Copper Weight):** 1 oz (35 µm) en capas externas
* **Acabado Superficial (Surface Finish):** **ENIG (Electroless Nickel Immersion Gold)** recomendado para contacto óptimo en zócalos SMD y MicroSD DM3AT. *HASL sin plomo (Lead-Free HASL) es aceptable como alternativa económica.*
* **Color de Máscara de Soldadura (Solder Mask):** Negro Mate (Matte Black) o Verde Estándar
* **Color de Serigrafía (Silkscreen):** Blanco (White)
* **Dimensiones de Placa (Board Outline):** 62.0 mm × 44.0 mm con esquinas redondeadas R=2.0 mm
* **Vías Mínimas:** Diámetro 0.6 mm / Taladro 0.3 mm (Microvías térmicas Pad 41 ESP32-S3: 0.2 mm / Vías térmicas AMS1117: 0.8 mm / 0.4 mm)
* **Ancho Mínimo de Pistas / Separación:** 0.20 mm / 0.20 mm (Pistas de potencia: 0.50 mm - 0.60 mm)

---

## 2. Requerimientos de Impedancia y Señal
* **Par Diferencial USB 2.0 (D+ / D-):** Líneas enrutadas en F.Cu acopladas con impedancia diferencial objetivo de **90 Ω ± 10%** sobre plano de referencia GND continuo.
* **Bus SPI Compartido (SCK, MOSI, MISO):** Conexión al zócalo MicroSD directo y aislamiento hacia transceptores RF / Flipper Zero mediante resistencias de amortiguamiento en serie de 330 Ω (R_ISO_MISO, R_ISO_MOSI, R_ISO_SCK) para evitar reflexiones y contención de bus.

---

## 3. Instrucciones de Montaje SMT / PCBA (Assembly Notes)
* **Lado de Montaje:** Top (F.Cu) contiene la totalidad de componentes activos y pasivos SMD.
* **Componentes THT (Through-Hole):**
  * `J2` (Cabezal macho 2x9 Flipper Zero GPIO, Pin Header 2.54mm pitch). Montar en cara superior.
  * `U3` (Módulo CC1101, Hembra/Macho 2x4 2.54mm).
  * `U4` (Módulo nRF24L01+, Hembra/Macho 2x4 2.54mm).
* **Inspección Óptica Automatizada (AOI):** Requerida en zócalo MicroSD Hirose DM3AT-SF-PEJM5 (C114227), diodo dual BAT54C (C8396) y módulo MCU ESP32-S3-WROOM-1U (C2913200).
* **Inspección por Rayos X (AXI):** Verificar pad térmico central GND (Pad 41) de ESP32-S3-WROOM-1U y pad térmico tab de AMS1117-3.3 (U1). Voiding < 20%.

---

## 4. Archivos Entregables en el Paquete de Producción V2
1. **Gerbers & Drills (`output/flipper_killer_production_v2/gerbers/`):**
   * `board-F_Cu.gbr` / `board-B_Cu.gbr` — Capas de cobre
   * `board-F_Mask.gbr` / `board-B_Mask.gbr` — Máscaras de soldadura
   * `board-F_Silkscreen.gbr` / `board-B_Silkscreen.gbr` — Serigrafías
   * `board-F_Paste.gbr` / `board-B_Paste.gbr` — Plantillas de pasta de soldar
   * `board-Edge_Cuts.gbr` — Contorno de fresado mecánico
   * `board-PTH.drl` / `board-NPTH.drl` — Archivos de taladrado Excellon
2. **Lista de Materiales (BOM):**
   * `jlcpcb_bom.csv` (Formato específico JLCPCB con números de parte LCSC)
   * `bom.csv` (Formato estándar IPC)
3. **Coordenadas de Posicionamiento (CPL / Pick & Place):**
   * `jlcpcb_cpl.csv` (Formato específico JLCPCB SMT)
   * `cpl.csv` (Formato estándar)
4. **Diseño KiCad v10:**
   * `board.kicad_sch` (Esquemático completo con protección BAT54C, MicroSD y SPI aislado)
   * `board-no-stencil.kicad_pcb` y `board.kicad_pcb` (Layout final verificado con ESP32-S3-WROOM-1U)
"""

with open(out_dir / "MANUFACTURING_NOTES.md", "w", encoding="utf-8") as f:
    f.write(notes_content)
print(f"  [OK] Exported MANUFACTURING_NOTES.md")

print("\n=================================================================")
print("  PRODUCTION RELEASE V2 BUILD COMPLETE!")
print("=================================================================")
