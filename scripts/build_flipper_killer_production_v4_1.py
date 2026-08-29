import os
import sys
import re
import json
import uuid
import shutil
import subprocess
from pathlib import Path

root_dir = Path(r"c:\Users\soyko\Documents\Pulse-main")
out_dir_v4 = root_dir / 'output' / 'flipper_killer_production_v4'
out_dir_v4_1 = root_dir / 'output' / 'flipper_killer_production_v4_1'
gerber_dir = out_dir_v4_1 / 'gerbers'

out_dir_v4_1.mkdir(parents=True, exist_ok=True)
gerber_dir.mkdir(parents=True, exist_ok=True)

# 1. SCHEMATIC
sch_src = out_dir_v4 / 'board.kicad_sch'
with open(sch_src, 'r', encoding='utf-8', errors='ignore') as f:
    sch_text = f.read()

VAL_REPLACEMENTS = {
    "R1": "10k", "R2": "5.1k", "R3": "5.1k", "R4": "330",
    "R_BOOT_PU": "10k", "R_SD_CS": "10k", "R_ISO_SCK": "330",
    "R_ISO_MOSI": "330", "R_ISO_MISO": "330", "C1": "10µF",
    "C2": "10µF", "C3": "100nF", "C4": "100nF", "C_SD": "100nF",
    "C_RF1": "10µF", "C_RF2": "100nF", "D1": "BAT54C", "U1": "AMS1117-3.3",
    "U2": "ESP32-S3-WROOM-1U", "U3": "CC1101", "U4": "nRF24",
    "J1": "USB-C", "J2": "Flipper_Zero_GPIO", "J_SD": "DM3AT-SF-PEJM5",
    "SW1": "RESET", "SW2": "BOOT", "LED1": "Green",
    "H1": "MountingHole_3.2mm_M3", "H2": "MountingHole_3.2mm_M3",
    "H3": "MountingHole_3.2mm_M3", "H4": "MountingHole_3.2mm_M3",
}

def update_sch_symbol(match):
    sym_block = match.group(0)
    ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', sym_block)
    if not ref_m:
        return sym_block
    ref = ref_m.group(1)
    if ref in VAL_REPLACEMENTS:
        new_val = VAL_REPLACEMENTS[ref]
        sym_block = re.sub(r'\(property\s+"Value"\s+"[^"]*"', f'(property "Value" "{new_val}"', sym_block)
    return sym_block

sch_text = re.sub(r'  \(symbol\s+\(lib_id\s+"[^"]+"\)[\s\S]*?\n  \)', update_sch_symbol, sch_text)
sch_text = sch_text.replace('"NC_U2_17"', '"ESP_IO9_CC_CS"')
sch_text = sch_text.replace('"NC_U2_23"', '"ESP_IO21_CC_GDO0"')
sch_text = sch_text.replace('"NC_U2_24"', '"ESP_IO47_NRF_CS"')
sch_text = sch_text.replace('"NC_U2_25"', '"ESP_IO48_NRF_CE"')

new_sch_resistors = f"""
  (symbol (lib_id "Device:R") (at 30.32 70.0 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)
    (uuid "{str(uuid.uuid4())}")
    (property "Reference" "R_ISO_CC_CS" (at 30.32 67.46 0) (effects (font (size 1.27 1.27))))
    (property "Value" "330" (at 30.32 72.54 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "Resistor_SMD:R_0603_1608Metric" (at 30.32 70.0 0) (effects (font (size 1.27 1.27)) hide))
  )
  (label "ESP_IO9_CC_CS" (at 26.51 70.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify right)))
  (wire (pts (xy 26.51 70.0) (xy 29.05 70.0)) (stroke (width 0) (type default)))
  (wire (pts (xy 31.59 70.0) (xy 34.13 70.0)) (stroke (width 0) (type default)))
  (label "CS_RF_CC1101" (at 34.13 70.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify left)))

  (symbol (lib_id "Device:R") (at 30.32 80.0 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)
    (uuid "{str(uuid.uuid4())}")
    (property "Reference" "R_ISO_CC_GDO0" (at 30.32 77.46 0) (effects (font (size 1.27 1.27))))
    (property "Value" "330" (at 30.32 82.54 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "Resistor_SMD:R_0603_1608Metric" (at 30.32 80.0 0) (effects (font (size 1.27 1.27)) hide))
  )
  (label "ESP_IO21_CC_GDO0" (at 26.51 80.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify right)))
  (wire (pts (xy 26.51 80.0) (xy 29.05 80.0)) (stroke (width 0) (type default)))
  (wire (pts (xy 31.59 80.0) (xy 34.13 80.0)) (stroke (width 0) (type default)))
  (label "GDO0_RF_CC1101" (at 34.13 80.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify left)))

  (symbol (lib_id "Device:R") (at 30.32 90.0 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)
    (uuid "{str(uuid.uuid4())}")
    (property "Reference" "R_ISO_NRF_CS" (at 30.32 87.46 0) (effects (font (size 1.27 1.27))))
    (property "Value" "330" (at 30.32 92.54 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "Resistor_SMD:R_0603_1608Metric" (at 30.32 90.0 0) (effects (font (size 1.27 1.27)) hide))
  )
  (label "ESP_IO47_NRF_CS" (at 26.51 90.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify right)))
  (wire (pts (xy 26.51 90.0) (xy 29.05 90.0)) (stroke (width 0) (type default)))
  (wire (pts (xy 31.59 90.0) (xy 34.13 90.0)) (stroke (width 0) (type default)))
  (label "CS_RF_NRF24" (at 34.13 90.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify left)))

  (symbol (lib_id "Device:R") (at 30.32 100.0 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)
    (uuid "{str(uuid.uuid4())}")
    (property "Reference" "R_ISO_NRF_CE" (at 30.32 97.46 0) (effects (font (size 1.27 1.27))))
    (property "Value" "330" (at 30.32 102.54 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "Resistor_SMD:R_0603_1608Metric" (at 30.32 100.0 0) (effects (font (size 1.27 1.27)) hide))
  )
  (label "ESP_IO48_NRF_CE" (at 26.51 100.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify right)))
  (wire (pts (xy 26.51 100.0) (xy 29.05 100.0)) (stroke (width 0) (type default)))
  (wire (pts (xy 31.59 100.0) (xy 34.13 100.0)) (stroke (width 0) (type default)))
  (label "CE_RF_NRF24" (at 34.13 100.0 0) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify left)))
"""

last_paren = sch_text.rfind(')')
sch_text = sch_text[:last_paren] + new_sch_resistors + "\n)\n"
sch_dst = out_dir_v4_1 / 'board.kicad_sch'
with open(sch_dst, 'w', encoding='utf-8') as f:
    f.write(sch_text)

# 2. PCB
pcb_src = out_dir_v4 / 'board.kicad_pcb'
with open(pcb_src, 'r', encoding='utf-8', errors='ignore') as f:
    pcb_text = f.read()

pcb_text = re.sub(r'\(title\s+"[^"]*"\)', '(title "Flipper Killer MK II Release 4.1.0 Production")', pcb_text)
pcb_text = re.sub(r'\(property\s+"Reference"\s+"Boot"', '(property "Reference" "R_BOOT_PU"', pcb_text)
pcb_text = re.sub(r'\(property\s+"Reference"\s+"_SCK"', '(property "Reference" "R_ISO_SCK"', pcb_text)
pcb_text = re.sub(r'\(property\s+"Reference"\s+"_MOSI"', '(property "Reference" "R_ISO_MOSI"', pcb_text)
pcb_text = re.sub(r'\(property\s+"Reference"\s+"_MISO"', '(property "Reference" "R_ISO_MISO"', pcb_text)

J2_CANONICAL_NETS = {
    "1": "PWR_5V_FLIPPER_IN", "2": "SPI_FLIPPER_MOSI", "3": "SPI_FLIPPER_MISO",
    "4": "CS_RF_CC1101", "5": "SPI_FLIPPER_SCK", "6": "GDO0_RF_CC1101",
    "7": "CS_RF_NRF24", "8": "PWR_GND", "9": "PWR_3V3_FLIPPER",
    "10": "NC_SWC_10", "11": "PWR_GND", "12": "NC_SIO_12",
    "13": "UART_ESP_RX", "14": "UART_ESP_TX", "15": "NC_GPIO15_15",
    "16": "CE_RF_NRF24", "17": "PWR_GND", "18": "PWR_GND"
}

def fix_j2_footprint(match):
    fp_block = match.group(0)
    if 'Reference" "J2"' not in fp_block:
        return fp_block
    def pad_replacer(pm):
        pad_num = pm.group(1)
        pad_content = pm.group(0)
        net_name = J2_CANONICAL_NETS.get(pad_num, "PWR_GND")
        if '(net ' in pad_content:
            pad_content = re.sub(r'\(net\s+(?:\d+\s+)?"[^"]*"\)', f'(net "{net_name}")', pad_content)
        else:
            c_pos = pad_content.rfind(')')
            pad_content = pad_content[:c_pos] + f'\n\t\t\t(net "{net_name}")\n\t\t)'
        return pad_content
    fp_block = re.sub(r'\(pad\s+"?(\d+)"?.*?\n\t\t\)', pad_replacer, fp_block, flags=re.DOTALL)
    return fp_block

pcb_text = re.sub(r'\(footprint\s+.*?\n\t\)', fix_j2_footprint, pcb_text, flags=re.DOTALL)

def fix_cc1101_footprint(match):
    fp_block = match.group(0)
    if 'Reference" "CC1101"' not in fp_block:
        return fp_block
    CC_NETS = {
        "1": "PWR_GND", "2": "PWR_3V3_FLIPPER", "3": "GDO0_RF_CC1101",
        "4": "CS_RF_CC1101", "5": "SPI_FLIPPER_SCK", "6": "SPI_FLIPPER_MOSI",
        "7": "SPI_FLIPPER_MISO", "8": "NC_GDO2"
    }
    def pad_replacer(pm):
        pad_num = pm.group(1)
        pad_content = pm.group(0)
        net_name = CC_NETS.get(pad_num, "PWR_GND")
        if '(net ' in pad_content:
            pad_content = re.sub(r'\(net\s+(?:\d+\s+)?"[^"]*"\)', f'(net "{net_name}")', pad_content)
        else:
            c_pos = pad_content.rfind(')')
            pad_content = pad_content[:c_pos] + f'\n\t\t\t(net "{net_name}")\n\t\t)'
        return pad_content
    fp_block = re.sub(r'\(pad\s+"?(\d+)"?.*?\n\t\t\)', pad_replacer, fp_block, flags=re.DOTALL)
    return fp_block

pcb_text = re.sub(r'\(footprint\s+.*?\n\t\)', fix_cc1101_footprint, pcb_text, flags=re.DOTALL)

def fix_nrf24_footprint(match):
    fp_block = match.group(0)
    if 'Reference" "NRF24"' not in fp_block:
        return fp_block
    NRF_NETS = {
        "1": "PWR_GND", "2": "PWR_3V3_FLIPPER", "3": "CE_RF_NRF24",
        "4": "CS_RF_NRF24", "5": "SPI_FLIPPER_SCK", "6": "SPI_FLIPPER_MOSI",
        "7": "SPI_FLIPPER_MISO", "8": "NC_IRQ"
    }
    def pad_replacer(pm):
        pad_num = pm.group(1)
        pad_content = pm.group(0)
        net_name = NRF_NETS.get(pad_num, "PWR_GND")
        if '(net ' in pad_content:
            pad_content = re.sub(r'\(net\s+(?:\d+\s+)?"[^"]*"\)', f'(net "{net_name}")', pad_content)
        else:
            c_pos = pad_content.rfind(')')
            pad_content = pad_content[:c_pos] + f'\n\t\t\t(net "{net_name}")\n\t\t)'
        return pad_content
    fp_block = re.sub(r'\(pad\s+"?(\d+)"?.*?\n\t\t\)', pad_replacer, fp_block, flags=re.DOTALL)
    return fp_block

pcb_text = re.sub(r'\(footprint\s+.*?\n\t\)', fix_nrf24_footprint, pcb_text, flags=re.DOTALL)

def fix_u2_footprint(match):
    fp_block = match.group(0)
    if 'Reference" "U2"' not in fp_block:
        return fp_block
    U2_NETS = {
        "17": "ESP_IO9_CC_CS",
        "23": "ESP_IO21_CC_GDO0",
        "24": "ESP_IO47_NRF_CS",
        "25": "ESP_IO48_NRF_CE"
    }
    def pad_replacer(pm):
        pad_num = pm.group(1)
        pad_content = pm.group(0)
        if pad_num in U2_NETS:
            net_name = U2_NETS[pad_num]
            if '(net ' in pad_content:
                pad_content = re.sub(r'\(net\s+(?:\d+\s+)?"[^"]*"\)', f'(net "{net_name}")', pad_content)
            else:
                c_pos = pad_content.rfind(')')
                pad_content = pad_content[:c_pos] + f'\n\t\t\t(net "{net_name}")\n\t\t)'
        return pad_content
    fp_block = re.sub(r'\(pad\s+"?(\d+)"?.*?\n\t\t\)', pad_replacer, fp_block, flags=re.DOTALL)
    return fp_block

pcb_text = re.sub(r'\(footprint\s+.*?\n\t\)', fix_u2_footprint, pcb_text, flags=re.DOTALL)

def make_mounting_hole_fp(ref, x, y):
    return f"""\t(footprint "MountingHole:MountingHole_3.2mm_M3"
\t\t(layer "F.Cu")
\t\t(uuid "{str(uuid.uuid4())}")
\t\t(at {x:.2f} {y:.2f})
\t\t(descr "Mounting Hole 3.2mm, no annular, M3")
\t\t(tags "mounting hole 3.2mm m3")
\t\t(property "Reference" "{ref}"
\t\t\t(at 0 -2.5 0)
\t\t\t(layer "F.SilkS")
\t\t\t(hide yes)
\t\t\t(uuid "{str(uuid.uuid4())}")
\t\t\t(effects (font (size 1 1) (thickness 0.15)))
\t\t)
\t\t(property "Value" "MountingHole_3.2mm_M3"
\t\t\t(at 0 2.5 0)
\t\t\t(layer "F.Fab")
\t\t\t(hide yes)
\t\t\t(uuid "{str(uuid.uuid4())}")
\t\t\t(effects (font (size 1 1) (thickness 0.15)))
\t\t)
\t\t(pad "" np_thru_hole circle
\t\t\t(at 0 0)
\t\t\t(size 3.2 3.2)
\t\t\t(drill 3.2)
\t\t\t(layers "*.Cu" "*.Mask")
\t\t)
\t)"""

h1_fp = make_mounting_hole_fp("H1", 119.00, 86.50)
h2_fp = make_mounting_hole_fp("H2", 176.00, 86.50)
h3_fp = make_mounting_hole_fp("H3", 119.00, 123.50)
h4_fp = make_mounting_hole_fp("H4", 176.00, 123.50)

def make_resistor_0603_fp(ref, val, x, y, net1, net2):
    return f"""\t(footprint "Resistor_SMD:R_0603_1608Metric"
\t\t(layer "F.Cu")
\t\t(uuid "{str(uuid.uuid4())}")
\t\t(at {x:.2f} {y:.2f})
\t\t(descr "Resistor SMD 0603 (1608 Metric)")
\t\t(tags "resistor 0603")
\t\t(property "Reference" "{ref}"
\t\t\t(at 0 -1.4 0)
\t\t\t(layer "F.SilkS")
\t\t\t(hide yes)
\t\t\t(uuid "{str(uuid.uuid4())}")
\t\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))
\t\t)
\t\t(property "Value" "{val}"
\t\t\t(at 0 1.4 0)
\t\t\t(layer "F.Fab")
\t\t\t(hide yes)
\t\t\t(uuid "{str(uuid.uuid4())}")
\t\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))
\t\t)
\t\t(pad "1" smd roundrect
\t\t\t(at -0.775 0)
\t\t\t(size 0.8 0.95)
\t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
\t\t\t(roundrect_rratio 0.25)
\t\t\t(net "{net1}")
\t\t)
\t\t(pad "2" smd roundrect
\t\t\t(at 0.775 0)
\t\t\t(size 0.8 0.95)
\t\t\t(layers "F.Cu" "F.Paste" "F.Mask")
\t\t\t(roundrect_rratio 0.25)
\t\t\t(net "{net2}")
\t\t)
\t)"""

r_cc_cs_fp   = make_resistor_0603_fp("R_ISO_CC_CS",   "330", 143.50, 117.20, "ESP_IO9_CC_CS",   "CS_RF_CC1101")
r_cc_gdo0_fp = make_resistor_0603_fp("R_ISO_CC_GDO0", "330", 153.50, 117.20, "ESP_IO21_CC_GDO0", "GDO0_RF_CC1101")
r_nrf_cs_fp  = make_resistor_0603_fp("R_ISO_NRF_CS",  "330", 156.50, 117.20, "ESP_IO47_NRF_CS",  "CS_RF_NRF24")
r_nrf_ce_fp  = make_resistor_0603_fp("R_ISO_NRF_CE",  "330", 159.50, 117.20, "ESP_IO48_NRF_CE",  "CE_RF_NRF24")

new_pcb_elements = "\n".join([h1_fp, h2_fp, h3_fp, h4_fp, r_cc_cs_fp, r_cc_gdo0_fp, r_nrf_cs_fp, r_nrf_ce_fp])

def make_segment(net, x1, y1, x2, y2, layer="F.Cu", width=0.25):
    return f"""\t(segment (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) (width {width}) (layer "{layer}") (net "{net}") (uuid "{str(uuid.uuid4())}"))"""

def make_via(net, x, y, size=0.6, drill=0.3):
    return f"""\t(via (at {x:.4f} {y:.4f}) (size {size}) (drill {drill}) (layers "F.Cu" "B.Cu") (net "{net}") (uuid "{str(uuid.uuid4())}"))"""

routing_elements = [
    # 1. CS_RF_CC1101 from J2.4 (167.55, 121.00) -> CC1101.4 (175.04, 93.54) on B.Cu
    make_segment("CS_RF_CC1101", 167.55, 121.00, 175.04, 113.51, "B.Cu"),
    make_segment("CS_RF_CC1101", 175.04, 113.51, 175.04, 93.54, "B.Cu"),
    
    # 2. CS_RF_CC1101 from R_ISO_CC_CS Pad 2 (144.275, 117.20) -> J2.4 (167.55, 121.00)
    make_segment("CS_RF_CC1101", 144.275, 117.20, 144.275, 124.50, "F.Cu"),
    make_segment("CS_RF_CC1101", 144.275, 124.50, 167.55, 124.50, "F.Cu"),
    make_segment("CS_RF_CC1101", 167.55, 124.50, 167.55, 121.00, "F.Cu"),

    # 3. ESP_IO9_CC_CS from U2.17 (146.13, 113.835) -> R_ISO_CC_CS Pad 1 (142.725, 117.20)
    make_segment("ESP_IO9_CC_CS", 146.13, 113.835, 146.13, 115.30, "F.Cu"),
    make_segment("ESP_IO9_CC_CS", 146.13, 115.30, 142.725, 115.30, "F.Cu"),
    make_segment("ESP_IO9_CC_CS", 142.725, 115.30, 142.725, 117.20, "F.Cu"),

    # 4. ESP_IO21_CC_GDO0 from U2.23 (153.75, 113.835) -> R_ISO_CC_GDO0 Pad 1 (152.725, 117.20)
    make_segment("ESP_IO21_CC_GDO0", 153.75, 113.835, 153.75, 115.50, "F.Cu"),
    make_segment("ESP_IO21_CC_GDO0", 153.75, 115.50, 152.725, 115.50, "F.Cu"),
    make_segment("ESP_IO21_CC_GDO0", 152.725, 115.50, 152.725, 117.20, "F.Cu"),

    # 5. GDO0_RF_CC1101 from R_ISO_CC_GDO0 Pad 2 (154.275, 117.20) -> J2.6 (162.47, 121.00)
    make_segment("GDO0_RF_CC1101", 154.275, 117.20, 154.275, 123.80, "F.Cu"),
    make_segment("GDO0_RF_CC1101", 154.275, 123.80, 162.47, 123.80, "F.Cu"),
    make_segment("GDO0_RF_CC1101", 162.47, 123.80, 162.47, 121.00, "F.Cu"),

    # 6. ESP_IO47_NRF_CS from U2.24 (155.02, 113.835) -> R_ISO_NRF_CS Pad 1 (155.725, 117.20)
    make_segment("ESP_IO47_NRF_CS", 155.02, 113.835, 155.02, 115.00, "F.Cu"),
    make_segment("ESP_IO47_NRF_CS", 155.02, 115.00, 155.725, 115.00, "F.Cu"),
    make_segment("ESP_IO47_NRF_CS", 155.725, 115.00, 155.725, 117.20, "F.Cu"),

    # 7. CS_RF_NRF24 from R_ISO_NRF_CS Pad 2 (157.275, 117.20) -> J2.7 (159.93, 121.00)
    make_segment("CS_RF_NRF24", 157.275, 117.20, 157.275, 119.50, "F.Cu"),
    make_segment("CS_RF_NRF24", 157.275, 119.50, 159.93, 119.50, "F.Cu"),
    make_segment("CS_RF_NRF24", 159.93, 119.50, 159.93, 121.00, "F.Cu"),

    # 8. ESP_IO48_NRF_CE from U2.25 (156.29, 113.835) -> R_ISO_NRF_CE Pad 1 (158.725, 117.20)
    make_segment("ESP_IO48_NRF_CE", 156.29, 113.835, 156.29, 114.50, "F.Cu"),
    make_segment("ESP_IO48_NRF_CE", 156.29, 114.50, 158.725, 114.50, "F.Cu"),
    make_segment("ESP_IO48_NRF_CE", 158.725, 114.50, 158.725, 117.20, "F.Cu"),

    # 9. CE_RF_NRF24 from R_ISO_NRF_CE Pad 2 (160.275, 117.20) -> J2.16 (126.91, 121.00)
    make_segment("CE_RF_NRF24", 160.275, 117.20, 160.275, 125.20, "F.Cu"),
    make_segment("CE_RF_NRF24", 160.275, 125.20, 126.91, 125.20, "F.Cu"),
    make_segment("CE_RF_NRF24", 126.91, 125.20, 126.91, 121.00, "F.Cu"),

    # J2 GND Connections to Zone
    make_segment("PWR_GND", 139.61, 121.00, 139.61, 122.50, "F.Cu"),
    make_via("PWR_GND", 139.61, 122.50),
    make_segment("PWR_GND", 124.37, 121.00, 121.83, 121.00, "F.Cu"),
    make_segment("PWR_GND", 121.83, 121.00, 121.83, 122.50, "F.Cu"),
    make_via("PWR_GND", 121.83, 122.50),
]

new_routing_text = "\n".join(routing_elements)

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

last_pcb_paren = pcb_text.rfind(')')
pcb_text = pcb_text[:last_pcb_paren] + "\n" + new_pcb_elements + "\n" + new_routing_text + "\n" + zone_fcu + "\n" + zone_bcu + "\n)\n"

pcb_dst = out_dir_v4_1 / 'board.kicad_pcb'
with open(pcb_dst, 'w', encoding='utf-8') as f:
    f.write(pcb_text)

for ext in ['.kicad_pro', '.kicad_prl']:
    src_p = out_dir_v4 / f'board{ext}'
    if src_p.exists():
        shutil.copyfile(src_p, out_dir_v4_1 / f'board{ext}')

print("  [*] Exporting Gerbers and Drills with kicad-cli...")
subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "-o", str(gerber_dir) + "/", str(pcb_dst)], check=True)
subprocess.run(["kicad-cli", "pcb", "export", "drill", "-o", str(gerber_dir) + "/", str(pcb_dst)], check=True)
subprocess.run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", str(out_dir_v4_1 / "cpl.csv"), str(pcb_dst)], check=True)

# 4. STRUCTURED BOM & CPL
BOM_DATABASE = [
    {"Ref": "R1", "Val": "10k", "Package": "0805", "LCSC": "C17414", "Desc": "Resistor 10k 5% 0805 SMD", "Qty": 1},
    {"Ref": "R2, R3", "Val": "5.1k", "Package": "0402", "LCSC": "C25905", "Desc": "Resistor 5.1k 1% 0402 SMD (USB CC)", "Qty": 2},
    {"Ref": "R4", "Val": "330", "Package": "0603", "LCSC": "C22859", "Desc": "Resistor 330R 1% 0603 SMD", "Qty": 1},
    {"Ref": "R_BOOT_PU, R_SD_CS", "Val": "10k", "Package": "0603", "LCSC": "C25804", "Desc": "Resistor 10k 1% 0603 SMD", "Qty": 2},
    {"Ref": "R_ISO_SCK, R_ISO_MOSI, R_ISO_MISO, R_ISO_CC_CS, R_ISO_CC_GDO0, R_ISO_NRF_CS, R_ISO_NRF_CE", "Val": "330", "Package": "0603", "LCSC": "C22859", "Desc": "Resistor 330R 1% 0603 SMD (Bus Isolation)", "Qty": 7},
    {"Ref": "C1, C2, C_RF1", "Val": "10µF", "Package": "0805", "LCSC": "C15850", "Desc": "Capacitor 10uF 25V X5R 0805 SMD", "Qty": 3},
    {"Ref": "C3, C4, C_SD, C_RF2", "Val": "100nF", "Package": "0603", "LCSC": "C14663", "Desc": "Capacitor 100nF 50V X7R 0603 SMD", "Qty": 4},
    {"Ref": "D1", "Val": "BAT54C", "Package": "SOT-23", "LCSC": "C8084", "Desc": "Dual Schottky Diode Common Cathode 30V 200mA", "Qty": 1},
    {"Ref": "U1", "Val": "AMS1117-3.3", "Package": "SOT-223", "LCSC": "C6186", "Desc": "LDO Voltage Regulator 3.3V 1A", "Qty": 1},
    {"Ref": "U2", "Val": "ESP32-S3-WROOM-1U", "Package": "Module SMD", "LCSC": "C2913200", "Desc": "ESP32-S3 Dual-Core Wi-Fi & BLE IPEX Module", "Qty": 1},
    {"Ref": "CC1101", "Val": "CC1101_Header", "Package": "2x04 2.54mm THT", "LCSC": "C124376", "Desc": "Sub-GHz CC1101 Transceiver 2x4 Header", "Qty": 1},
    {"Ref": "NRF24", "Val": "nRF24L01+_Header", "Package": "2x04 2.54mm THT", "LCSC": "C124376", "Desc": "2.4GHz nRF24L01+ Transceiver 2x4 Header", "Qty": 1},
    {"Ref": "J1", "Val": "TYPE-C-31-M-12", "Package": "USB-C SMD/THT", "LCSC": "C165948", "Desc": "USB Type-C 16-Pin Receptacle", "Qty": 1},
    {"Ref": "J2", "Val": "Flipper_Zero_GPIO", "Package": "2x09 2.54mm THT", "LCSC": "C224360", "Desc": "Flipper Zero 18-Pin GPIO Header Interface", "Qty": 1},
    {"Ref": "J_SD", "Val": "DM3AT-SF-PEJM5", "Package": "MicroSD SMD", "LCSC": "C114217", "Desc": "Hirose MicroSD Push-Push Receptacle", "Qty": 1},
    {"Ref": "SW1, SW2", "Val": "EVQPE1", "Package": "SMD 3x2mm", "LCSC": "C139797", "Desc": "Pushbutton Switch SPST SMD (RESET/BOOT)", "Qty": 2},
    {"Ref": "LED1", "Val": "Green", "Package": "0603", "LCSC": "C72043", "Desc": "LED Green SMD 0603 Indicator", "Qty": 1},
    {"Ref": "H1, H2, H3, H4", "Val": "M3_3.2mm", "Package": "Mounting Hole", "LCSC": "N/A", "Desc": "Mounting Hole 3.2mm Mechanical M3", "Qty": 4},
]

with open(out_dir_v4_1 / "bom.csv", 'w', encoding='utf-8') as f:
    f.write("Reference,Value,Package,Quantity,Description,LCSC_Part\n")
    for row in BOM_DATABASE:
        f.write(f'"{row["Ref"]}","{row["Val"]}","{row["Package"]}",{row["Qty"]},"{row["Desc"]}","{row["LCSC"]}"\n')

with open(out_dir_v4_1 / "jlcpcb_bom.csv", 'w', encoding='utf-8') as f:
    f.write("Comment,Designator,Footprint,LCSC Part #\n")
    for row in BOM_DATABASE:
        if row["LCSC"] != "N/A":
            f.write(f'"{row["Val"]}","{row["Ref"]}","{row["Package"]}","{row["LCSC"]}"\n')

cpl_src = out_dir_v4_1 / "cpl.csv"
if cpl_src.exists():
    with open(cpl_src, 'r', encoding='utf-8') as f:
        cpl_raw = f.read()
    jlc_cpl = cpl_raw.replace('"Ref"', '"Designator"').replace('"Val"', '"Val"').replace('"Package"', '"Package"').replace('"PosX"', '"Mid X"').replace('"PosY"', '"Mid Y"').replace('"Rot"', '"Rotation"').replace('"Side"', '"Layer"')
    with open(out_dir_v4_1 / "jlcpcb_cpl.csv", 'w', encoding='utf-8') as f:
        f.write(jlc_cpl)

shutil.copyfile(out_dir_v4_1 / "bom.csv", out_dir_v4_1 / "pcbway_bom.csv")
if (out_dir_v4_1 / "jlcpcb_cpl.csv").exists():
    shutil.copyfile(out_dir_v4_1 / "jlcpcb_cpl.csv", out_dir_v4_1 / "pcbway_cpl.csv")

print("=== Release V4.1 Generation Done ===")
