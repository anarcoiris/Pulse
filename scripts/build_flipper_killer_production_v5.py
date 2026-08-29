"""
build_flipper_killer_production_v5.py
=====================================
Generates the V5 production / scratchpad package without modifying V4.
Fixes:
  - Explicit (net "...") on all J2 pads (pads 4, 11, 17, 18).
  - True KiCad 10 dynamic copper pour zones (F.Cu & B.Cu) for PWR_GND.
  - Generates updated Gerbers, Drills, BOM, CPL, DRC report for V5.
"""

import os
import re
import json
import uuid
import shutil
import subprocess
from pathlib import Path

root_dir = Path(r"c:\Users\soyko\Documents\Pulse-main")
out_dir_v4 = root_dir / 'output' / 'flipper_killer_production_v4'
out_dir_v5 = root_dir / 'output' / 'flipper_killer_production_v5'
out_dir_v5.mkdir(parents=True, exist_ok=True)

# 1. Copy base files from V4 to V5
for fn in ['board.kicad_sch', 'bom.csv', 'jlcpcb_bom.csv', 'pcbway_bom.csv', 'cpl.csv', 'jlcpcb_cpl.csv', 'pcbway_cpl.csv', 'MANUFACTURING_NOTES.md']:
    src_f = out_dir_v4 / fn
    if src_f.exists():
        shutil.copyfile(src_f, out_dir_v5 / fn)

# 2. Read V4 PCB
v4_pcb = out_dir_v4 / 'board.kicad_pcb'
with open(v4_pcb, 'r', encoding='utf-8') as f:
    pcb_text = f.read()

# 3. Ensure all pads in J2 have explicit net directives
J2_EXPLICIT_NETS = {
    "1": "PWR_5V_FLIPPER_IN",
    "2": "SPI_FLIPPER_MOSI",
    "3": "SPI_FLIPPER_MISO",
    "4": "CS_RF_CC1101",
    "5": "SPI_FLIPPER_SCK",
    "6": "GDO0_RF_CC1101",
    "7": "CS_RF_NRF24",
    "8": "PWR_GND",
    "9": "PWR_3V3_FLIPPER",
    "10": "NC_SWC_10",
    "11": "PWR_GND",
    "12": "NC_SIO_12",
    "13": "UART_ESP_RX",
    "14": "UART_ESP_TX",
    "15": "NC_GPIO15_15",
    "16": "CE_RF_NRF24",
    "17": "PWR_GND",
    "18": "PWR_GND"
}

def fix_j2_pads(match):
    fp_block = match.group(0)
    if 'reference "J2"' not in fp_block:
        return fp_block
    
    def pad_fixer(pm):
        pad_num = pm.group(1)
        pad_body = pm.group(0)
        net_name = J2_EXPLICIT_NETS.get(pad_num, "PWR_GND")
        if '(net ' in pad_body:
            pad_body = re.sub(r'\(net\s+(?:\d+\s+)?"[^"]*"\)', f'(net "{net_name}")', pad_body)
        else:
            # insert (net "...") before closing paren
            last_p = pad_body.rfind(')')
            pad_body = pad_body[:last_p] + f'\n\t\t\t(net "{net_name}")\n\t\t)'
        return pad_body

    fp_block = re.sub(r'\(pad\s+"?(\w+)"?.*?\n\t\t\)', pad_fixer, fp_block, flags=re.DOTALL)
    return fp_block

pcb_text = re.sub(r'\(footprint\s+.*?\n\t\)', fix_j2_pads, pcb_text, flags=re.DOTALL)

# 4. Add KiCad 10 compliant Copper Pour Zones for PWR_GND on F.Cu and B.Cu
zone_fcu = f"""\t(zone
\t\t(net "PWR_GND")
\t\t(net_name "PWR_GND")
\t\t(layer "F.Cu")
\t\t(uuid "{str(uuid.uuid4())}")
\t\t(hatch edge 0.5)
\t\t(priority 0)
\t\t(connect_pads
\t\t\t(clearance 0.2)
\t\t)
\t\t(min_thickness 0.15)
\t\t(filled_areas_thickness no)
\t\t(fill
\t\t\t(thermal_gap 0.25)
\t\t\t(thermal_bridge_width 0.3)
\t\t)
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 114.0 81.0)
\t\t\t\t(xy 181.5 81.0)
\t\t\t\t(xy 181.5 129.0)
\t\t\t\t(xy 114.0 129.0)
\t\t\t)
\t\t)
\t)"""

zone_bcu = f"""\t(zone
\t\t(net "PWR_GND")
\t\t(net_name "PWR_GND")
\t\t(layer "B.Cu")
\t\t(uuid "{str(uuid.uuid4())}")
\t\t(hatch edge 0.5)
\t\t(priority 0)
\t\t(connect_pads
\t\t\t(clearance 0.2)
\t\t)
\t\t(min_thickness 0.15)
\t\t(filled_areas_thickness no)
\t\t(fill
\t\t\t(thermal_gap 0.25)
\t\t\t(thermal_bridge_width 0.3)
\t\t)
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 114.0 81.0)
\t\t\t\t(xy 181.5 81.0)
\t\t\t\t(xy 181.5 129.0)
\t\t\t\t(xy 114.0 129.0)
\t\t\t)
\t\t)
\t)"""

last_p = pcb_text.rfind(')')
if last_p != -1:
    pcb_text = pcb_text[:last_p] + f"\n{zone_fcu}\n{zone_bcu}\n)"

v5_pcb = out_dir_v5 / 'board.kicad_pcb'
with open(v5_pcb, 'w', encoding='utf-8') as f:
    f.write(pcb_text)

# 5. Export Gerbers & Drills for V5
gerber_dir_v5 = out_dir_v5 / 'gerbers'
gerber_dir_v5.mkdir(parents=True, exist_ok=True)

subprocess.run([
    'kicad-cli', 'pcb', 'export', 'gerbers',
    '--output', str(gerber_dir_v5) + '/',
    '--layers', 'F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,B.Paste,Edge.Cuts',
    str(v5_pcb)
], capture_output=True, text=True)

subprocess.run([
    'kicad-cli', 'pcb', 'export', 'drill',
    '--output', str(gerber_dir_v5) + '/',
    '--format', 'excellon',
    '--drill-origin', 'absolute',
    str(v5_pcb)
], capture_output=True, text=True)

# 6. Run DRC on V5
drc_json_v5 = out_dir_v5 / 'drc_report.json'
subprocess.run(['kicad-cli', 'pcb', 'drc', '--output', str(drc_json_v5), '--format', 'json', str(v5_pcb)], capture_output=True, text=True)

with open(drc_json_v5, 'r', encoding='utf-8') as f:
    drc_v5 = json.load(f)

print(f"V5 DRC Violations: {len(drc_v5.get('violations', []))}, Unconnected: {len(drc_v5.get('unconnected_items', []))}")
