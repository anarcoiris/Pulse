#!/usr/bin/env python3
"""
SKiDL circuit script — generado por PulseLab Forge.
Generado: 2026-04-20T06:03:15.061474
"""
from skidl import *

# ── Nets ──────────────────────────────────────────────
M1 = Net('M1')
M2 = Net('M2')
SRC = Net('SRC')
gnd = Net('GND')

# ── Components ────────────────────────────────────────
v1 = Part('Device', 'Battery', value='24V', footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical')  # V1 24V
r1 = Part('Device', 'R', value='10Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R1 10Ω
l1 = Part('Device', 'L', value='0.001H', footprint='Inductor_SMD:L_0805_2012Metric')  # L1 1mH
c1 = Part('Device', 'C', value='1e-05F', footprint='Capacitor_SMD:C_0805_2012Metric')  # C1 10µF

# ── Connections ───────────────────────────────────────
v1['~'][1] += SRC
v1['~'][2] += gnd
r1['~'][1] += SRC
r1['~'][2] += M1
l1['~'][1] += M1
l1['~'][2] += M2
c1['~'][1] += M2
c1['~'][2] += gnd

# ── Export ────────────────────────────────────────────
ERC()                        # Electrical Rules Check
generate_netlist()            # Salida: circuit.net

if __name__ == '__main__':
    # También se puede generar SVG del esquemático:
    # generate_schematic()
    pass