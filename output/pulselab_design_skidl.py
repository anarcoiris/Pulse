#!/usr/bin/env python3
"""
SKiDL circuit script — generado por PulseLab Forge.
Generado: 2026-04-26T03:46:23.265017
"""
from skidl import *

# ── Nets ──────────────────────────────────────────────
OUT = Net('OUT')
VCC = Net('VCC')
gnd = Net('GND')

# ── Components ────────────────────────────────────────
v1 = Part('Device', 'Battery', value='5V', footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical')  # V1
r1 = Part('Device', 'R', value='1000Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R1
r2 = Part('Device', 'R', value='1000Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R2

# ── Connections ───────────────────────────────────────
v1['~'][1] += VCC
v1['~'][2] += gnd
r1['~'][1] += VCC
r1['~'][2] += OUT
r2['~'][1] += OUT
r2['~'][2] += gnd

# ── Export ────────────────────────────────────────────
ERC()                        # Electrical Rules Check
generate_netlist()            # Salida: circuit.net

if __name__ == '__main__':
    # También se puede generar SVG del esquemático:
    # generate_schematic()
    pass