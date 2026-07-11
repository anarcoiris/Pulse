"""
core/component_types.py
=======================
Centralized mappings and reverse patterns for component type (etype) translation,
symbols, footprints, and formatting between PulseLab visual model and KiCad.
"""

# 1. Component type (etype) to KiCad symbol library ID mappings
KICAD_SYMBOLS: dict[str, str] = {
    "R":   "Device:R",
    "C":   "Device:C",
    "L":   "Device:L",
    "V":   "Device:Battery",
    "S":   "Device:SW_SPST",
    "GND": "power:GND",
}

# 2. Component type (etype) to KiCad default footprint mappings
DEFAULT_FOOTPRINTS: dict[str, str] = {
    "R":   "Resistor_SMD:R_0805_2012Metric",
    "C":   "Capacitor_SMD:C_0805_2012Metric",
    "L":   "Inductor_SMD:L_0805_2012Metric",
    "V":   "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "S":   "Button_Switch_THT:SW_PUSH_6mm",
    "GND": "TestPoint:TestPoint_Pad_D1.0mm",
}

# 3. Component value formatter templates by type
VALUE_FMT: dict[str, str] = {
    "R": "{:.4g}Ω",
    "C": "{:.4g}F",
    "L": "{:.4g}H",
    "V": "{:.4g}V",
    "S": "SW",
    "GND": "GND",
}

# 4. Canonical symbol mappings for specific common IC/MCU component values
VALUE_SYMBOL_MAP: dict[str, str] = {
    "CH340": "Interface_USB:CH340G",
    "CH340C": "Interface_USB:CH340G",
    "CH340G": "Interface_USB:CH340G",
    "CP2102": "Interface_USB:CP2102N-A02-GQFN28",
    "AMS1117": "Regulator_Linear:AMS1117-3.3",
    "ESP32": "RF_Module:ESP32-WROOM-32",
    "ESP8266": "RF_Module:ESP-12F",
    "ESP32-S2": "MCU_Espressif:ESP32-S2",
    "ESP32-S3": "RF_Module:ESP32-WROOM-32",
    "ESP32-WROOM-32": "RF_Module:ESP32-WROOM-32",
}

# 5. Regex patterns for mapping KiCad Symbol IDs/libraries back to PulseLab etypes
SYMBOL_TO_ETYPE_PATTERNS: dict[str, str] = {
    r'Device:R': 'R',
    r'Device:C': 'C',
    r'Device:L': 'L',
    r'Device:LED': 'S',
    r'Device:D': 'S',
    r'Device:Battery': 'V',
    r'power:VCC': 'V',
    r'power:GND': 'GND'
}

# 6. Regex patterns for mapping KiCad Footprint IDs back to PulseLab etypes
FOOTPRINT_TO_ETYPE_PATTERNS: dict[str, str] = {
    r'Resistor': 'R',
    r'Capacitor': 'C',
    r'Inductor': 'L',
    r'LED': 'S',
    r'Diode': 'S',
    r'Battery': 'V',
    r'VCC': 'V',
    r'GND': 'GND'
}
