#!/usr/bin/env python3
"""
SKiDL circuit script — generado por PulseLab Forge.
Generado: 2026-04-25T22:48:43.245876
"""
from skidl import *

# ── Nets ──────────────────────────────────────────────
VCC = Net('VCC')
gnd = Net('GND')

# ── Components ────────────────────────────────────────
r1 = Part('Device', 'R', value='1e+04Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R1
c1 = Part('Device', 'C', value='1e-07F', footprint='Capacitor_SMD:C_0805_2012Metric')  # C1

# ── Connections ───────────────────────────────────────
r1['~'][1] += VCC
r1['~'][2] += gnd
c1['~'][1] += VCC
c1['~'][2] += gnd

# ── Export ────────────────────────────────────────────
ERC()                        # Electrical Rules Check
generate_netlist()            # Salida: circuit.net

if __name__ == '__main__':
    # También se puede generar SVG del esquemático:
    # generate_schematic()
    pass