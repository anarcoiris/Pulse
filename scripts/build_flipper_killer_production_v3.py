import re
import json
import uuid
import shutil
import subprocess
from pathlib import Path

root_dir = Path.cwd()
out_dir_v3 = root_dir / 'output' / 'flipper_killer_production_v3'
out_dir_v3.mkdir(parents=True, exist_ok=True)

# Copy schematic, BOM, and CPL
shutil.copyfile(root_dir / 'output/flipper_killer_production_v2/bom.csv', out_dir_v3 / 'bom.csv')
shutil.copyfile(root_dir / 'output/flipper_killer_production_v2/jlcpcb_bom.csv', out_dir_v3 / 'jlcpcb_bom.csv')
shutil.copyfile(root_dir / 'output/flipper_killer_production_v2/cpl.csv', out_dir_v3 / 'cpl.csv')
shutil.copyfile(root_dir / 'output/flipper_killer_production_v2/jlcpcb_cpl.csv', out_dir_v3 / 'jlcpcb_cpl.csv')

src_pcb = out_dir_v3 / 'debug.kicad_pcb'
with open(src_pcb, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update J2 pad nets to canonical pinout
J2_PIN_NETS = {
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
    "17": "NC_1W_17",
    "18": "PWR_GND"
}

def update_j2_pads(match):
    fp_block = match.group(0)
    if 'J2' not in fp_block:
        return fp_block
    
    def pad_replacer(pm):
        pad_num = pm.group(1)
        net_name = J2_PIN_NETS.get(pad_num, "PWR_GND")
        pad_str = pm.group(0)
        pad_str = re.sub(r'\(net\s+(?:\d+\s+)?"[^"]*"\)', f'(net "{net_name}")', pad_str)
        return pad_str

    fp_block = re.sub(r'\(pad\s+"(\d+)".*?\n\t\t\)', pad_replacer, fp_block, flags=re.DOTALL)
    return fp_block

text = re.sub(r'\(footprint\s+.*?\n\t\)', update_j2_pads, text, flags=re.DOTALL)

# 2. Expand copper zones on F.Cu and B.Cu to [114.0, 181.5]
def expand_zone_polygon(match):
    zone_block = match.group(0)
    if 'PWR_GND' in zone_block:
        new_pts = """(pts
				(xy 114.0 81.0)
				(xy 181.5 81.0)
				(xy 181.5 129.0)
				(xy 114.0 129.0)
			)"""
        zone_block = re.sub(r'\(pts\s+.*?\n\t\t\t\)', new_pts, zone_block, flags=re.DOTALL)
    return zone_block

text = re.sub(r'\(zone\s+.*?\n\t\)', expand_zone_polygon, text, flags=re.DOTALL)

# 3. Strip all filled_polygon blocks
text = re.sub(r'\t\t\(filled_polygon\s+.*?\n\t\t\)\n', '', text, flags=re.DOTALL)

# 4. Remove all old conflicting tracks on Flipper and RF nets
lines = text.splitlines()
clean = []
in_seg = False
seg_lines = []
for line in lines:
    if line.strip().startswith('(segment'):
        in_seg = True
        seg_lines = [line]
    elif in_seg:
        seg_lines.append(line)
        if line.strip() == ')':
            in_seg = False
            seg_block = "\n".join(seg_lines)
            if any(k in seg_block for k in ['SPI_FLIPPER', 'CS_RF', 'CE_RF', 'GDO0_RF', 'PWR_5V_FLIPPER', 'PWR_3V3_FLIPPER', 'UART_ESP']):
                continue
            clean.append(seg_block)
    else:
        clean.append(line)

text = "\n".join(clean)

# 5. Insert clean non-crossing routes running below J2 at Y in [123.0, 126.0]
def seg(x1, y1, x2, y2, net_name, layer="B.Cu", width=0.25):
    return f'\t(segment (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) (width {width}) (layer "{layer}") (net "{net_name}") (uuid "{str(uuid.uuid4())}"))'

routes = [
    # 1. PWR_5V_FLIPPER_IN: J2 Pin 1 (175.17, 121.0) -> D1 Pin 2 (135.375, 90.55)
    seg(175.17, 121.0, 175.17, 123.0, "PWR_5V_FLIPPER_IN", "F.Cu", 0.5),
    seg(175.17, 123.0, 135.375, 123.0, "PWR_5V_FLIPPER_IN", "F.Cu", 0.5),
    seg(135.375, 123.0, 135.375, 90.55, "PWR_5V_FLIPPER_IN", "F.Cu", 0.5),

    # 2. SPI_FLIPPER_MOSI: J2 Pin 2 (172.63, 121.0) -> R_ISO_MOSI Pad 2 (164.7, 116.9) -> U4 Pad 6 (175.04, 114.08) & U3 Pad 6 (175.04, 96.08)
    seg(172.63, 121.0, 172.63, 123.5, "SPI_FLIPPER_MOSI", "B.Cu", 0.25),
    seg(172.63, 123.5, 164.7, 123.5, "SPI_FLIPPER_MOSI", "B.Cu", 0.25),
    seg(164.7, 123.5, 164.7, 116.9, "SPI_FLIPPER_MOSI", "B.Cu", 0.25),
    seg(172.63, 123.5, 175.04, 123.5, "SPI_FLIPPER_MOSI", "B.Cu", 0.25),
    seg(175.04, 123.5, 175.04, 114.08, "SPI_FLIPPER_MOSI", "B.Cu", 0.25),
    seg(175.04, 114.08, 175.04, 96.08, "SPI_FLIPPER_MOSI", "B.Cu", 0.25),

    # 3. SPI_FLIPPER_MISO: J2 Pin 3 (170.09, 121.0) -> R_ISO_MISO Pad 2 (162.2, 116.9) -> U4 Pad 7 (172.5, 116.62) & U3 Pad 7 (172.5, 98.62)
    seg(170.09, 121.0, 170.09, 124.0, "SPI_FLIPPER_MISO", "B.Cu", 0.25),
    seg(170.09, 124.0, 162.2, 124.0, "SPI_FLIPPER_MISO", "B.Cu", 0.25),
    seg(162.2, 124.0, 162.2, 116.9, "SPI_FLIPPER_MISO", "B.Cu", 0.25),
    seg(170.09, 124.0, 172.5, 124.0, "SPI_FLIPPER_MISO", "B.Cu", 0.25),
    seg(172.5, 124.0, 172.5, 116.62, "SPI_FLIPPER_MISO", "B.Cu", 0.25),
    seg(172.5, 116.62, 172.5, 98.62, "SPI_FLIPPER_MISO", "B.Cu", 0.25),

    # 4. CS_RF_CC1101: J2 Pin 4 (167.55, 121.0) -> U3 Pad 4 (175.04, 93.54)
    seg(167.55, 121.0, 167.55, 124.5, "CS_RF_CC1101", "B.Cu", 0.25),
    seg(167.55, 124.5, 176.5, 124.5, "CS_RF_CC1101", "B.Cu", 0.25),
    seg(176.5, 124.5, 176.5, 93.54, "CS_RF_CC1101", "B.Cu", 0.25),
    seg(176.5, 93.54, 175.04, 93.54, "CS_RF_CC1101", "B.Cu", 0.25),

    # 5. SPI_FLIPPER_SCK: J2 Pin 5 (165.01, 121.0) -> R_ISO_SCK Pad 2 (167.2, 116.9) -> U4 Pad 5 (172.5, 114.08) & U3 Pad 5 (172.5, 96.08)
    seg(165.01, 121.0, 165.01, 125.0, "SPI_FLIPPER_SCK", "B.Cu", 0.25),
    seg(165.01, 125.0, 167.2, 125.0, "SPI_FLIPPER_SCK", "B.Cu", 0.25),
    seg(167.2, 125.0, 167.2, 116.9, "SPI_FLIPPER_SCK", "B.Cu", 0.25),
    seg(167.2, 116.9, 173.8, 116.9, "SPI_FLIPPER_SCK", "F.Cu", 0.25),
    seg(173.8, 116.9, 173.8, 114.08, "SPI_FLIPPER_SCK", "F.Cu", 0.25),
    seg(173.8, 114.08, 172.5, 114.08, "SPI_FLIPPER_SCK", "F.Cu", 0.25),
    seg(173.8, 114.08, 173.8, 96.08, "SPI_FLIPPER_SCK", "F.Cu", 0.25),
    seg(173.8, 96.08, 172.5, 96.08, "SPI_FLIPPER_SCK", "F.Cu", 0.25),

    # 6. GDO0_RF_CC1101: J2 Pin 6 (162.47, 121.0) -> U3 Pad 3 (172.5, 93.54)
    seg(162.47, 121.0, 162.47, 125.5, "GDO0_RF_CC1101", "B.Cu", 0.25),
    seg(162.47, 125.5, 177.5, 125.5, "GDO0_RF_CC1101", "B.Cu", 0.25),
    seg(177.5, 125.5, 177.5, 93.54, "GDO0_RF_CC1101", "B.Cu", 0.25),
    seg(177.5, 93.54, 172.5, 93.54, "GDO0_RF_CC1101", "B.Cu", 0.25),

    # 7. CS_RF_NRF24: J2 Pin 7 (159.93, 121.0) -> U4 Pad 4 (175.04, 111.54)
    seg(159.93, 121.0, 159.93, 126.0, "CS_RF_NRF24", "B.Cu", 0.25),
    seg(159.93, 126.0, 178.5, 126.0, "CS_RF_NRF24", "B.Cu", 0.25),
    seg(178.5, 126.0, 178.5, 111.54, "CS_RF_NRF24", "B.Cu", 0.25),
    seg(178.5, 111.54, 175.04, 111.54, "CS_RF_NRF24", "B.Cu", 0.25),

    # 8. PWR_3V3_FLIPPER: J2 Pin 9 (144.69, 121.0) -> U4 Pad 2 (175.04, 109.0) & U3 Pad 2 (175.04, 91.0) & C_RF1/C_RF2
    seg(144.69, 121.0, 144.69, 123.5, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(144.69, 123.5, 174.5, 123.5, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(174.5, 123.5, 174.5, 109.0, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(174.5, 109.0, 175.04, 109.0, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(174.5, 109.0, 174.5, 91.0, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(174.5, 91.0, 175.04, 91.0, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(174.5, 100.9, 169.425, 100.9, "PWR_3V3_FLIPPER", "F.Cu", 0.4),
    seg(174.5, 102.5, 171.725, 102.5, "PWR_3V3_FLIPPER", "F.Cu", 0.4),

    # 9. UART_ESP_RX: J2 Pin 13 (134.53, 121.0) -> U2 Pin 36 (159.325, 101.155)
    seg(134.53, 121.0, 134.53, 118.0, "UART_ESP_RX", "F.Cu", 0.25),
    seg(134.53, 118.0, 159.325, 118.0, "UART_ESP_RX", "F.Cu", 0.25),
    seg(159.325, 118.0, 159.325, 101.155, "UART_ESP_RX", "F.Cu", 0.25),

    # 10. UART_ESP_TX: J2 Pin 14 (131.99, 121.0) -> U2 Pin 37 (159.325, 99.885)
    seg(131.99, 121.0, 131.99, 117.0, "UART_ESP_TX", "F.Cu", 0.25),
    seg(131.99, 117.0, 158.0, 117.0, "UART_ESP_TX", "F.Cu", 0.25),
    seg(158.0, 117.0, 158.0, 99.885, "UART_ESP_TX", "F.Cu", 0.25),
    seg(158.0, 99.885, 159.325, 99.885, "UART_ESP_TX", "F.Cu", 0.25),

    # 11. CE_RF_NRF24: J2 Pin 16 (126.91, 121.0) -> U4 Pad 3 (172.5, 111.54)
    seg(126.91, 121.0, 126.91, 126.5, "CE_RF_NRF24", "B.Cu", 0.25),
    seg(126.91, 126.5, 172.5, 126.5, "CE_RF_NRF24", "B.Cu", 0.25),
    seg(172.5, 126.5, 172.5, 111.54, "CE_RF_NRF24", "B.Cu", 0.25),
]

routes_str = "\n".join(routes)

last_paren_idx = text.rfind(')')
if last_paren_idx != -1:
    text = text[:last_paren_idx] + f"\n{routes_str}\n)"

with open(out_dir_v3 / 'board.kicad_pcb', 'w', encoding='utf-8') as f:
    f.write(text)

with open(out_dir_v3 / 'board-no-stencil.kicad_pcb', 'w', encoding='utf-8') as f:
    f.write(text)

# Export Gerbers & Drills
gerber_dir = out_dir_v3 / 'gerbers'
gerber_dir.mkdir(parents=True, exist_ok=True)

subprocess.run([
    'kicad-cli', 'pcb', 'export', 'gerbers',
    '--output', str(gerber_dir) + '/',
    '--layers', 'F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,B.Paste,Edge.Cuts',
    str(out_dir_v3 / 'board.kicad_pcb')
], capture_output=True, text=True)

subprocess.run([
    'kicad-cli', 'pcb', 'export', 'drill',
    '--output', str(gerber_dir) + '/',
    '--format', 'excellon',
    '--drill-origin', 'absolute',
    str(out_dir_v3 / 'board.kicad_pcb')
], capture_output=True, text=True)

# Run DRC
drc_json_v3 = out_dir_v3 / 'drc_report.json'
if drc_json_v3.exists():
    drc_json_v3.unlink()

res = subprocess.run(['kicad-cli', 'pcb', 'drc', '--output', str(drc_json_v3), '--format', 'json', str(out_dir_v3 / 'board.kicad_pcb')], capture_output=True, text=True)

with open(drc_json_v3, 'r', encoding='utf-8') as f:
    drc_v3 = json.load(f)

print("==================================================")
print(f"  V3 FINAL REVISED CANONICAL DRC REPORT:")
print(f"  Unconnected: {len(drc_v3.get('unconnected_items', []))}")
print(f"  Violations:  {len(drc_v3.get('violations', []))}")
print("==================================================")
by_type = {}
for v in drc_v3.get('violations', []):
    t = v.get('type')
    by_type[t] = by_type.get(t, 0) + 1
for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

if drc_v3.get('violations'):
    print("\nViolations list:")
    for v in drc_v3.get('violations')[:15]:
        print(f"  [{v.get('type')}] {v.get('description')}")
