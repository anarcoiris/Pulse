#!/usr/bin/env python3
"""
SKiDL circuit script — generado por PulseLab Forge.
Generado: 2026-04-19T01:26:44.240461
"""
from skidl import *

# ── Nets ──────────────────────────────────────────────
A = Net('A')
B = Net('B')
gnd = Net('GND')

# ── Components ────────────────────────────────────────
v1 = Part('Device', 'Battery', value='5V', footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical')  # V1 5V
r1 = Part('Device', 'R', value='1000Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R1 1kΩ
c1 = Part('Device', 'C', value='0.0001F', footprint='Capacitor_SMD:C_0805_2012Metric')  # C1 100µF

# ── Connections ───────────────────────────────────────
v1['~'][1] += A
v1['~'][2] += gnd
r1['~'][1] += A
r1['~'][2] += B
c1['~'][1] += B
c1['~'][2] += gnd

# ── Export ────────────────────────────────────────────
ERC()                        # Electrical Rules Check
generate_netlist()            # Salida: circuit.net

if __name__ == '__main__':
    # También se puede generar SVG del esquemático:
    # generate_schematic()
    pass