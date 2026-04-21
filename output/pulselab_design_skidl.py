#!/usr/bin/env python3
"""
SKiDL circuit script — generado por PulseLab Forge.
Generado: 2026-04-20T23:50:57.927225
"""
from skidl import *

# ── Nets ──────────────────────────────────────────────
ANT_IN = Net('ANT_IN')
BANCO = Net('BANCO')
CARGA_IN = Net('CARGA_IN')
PFN1 = Net('PFN1')
PFN2 = Net('PFN2')
PFN3 = Net('PFN3')
PFN_IN = Net('PFN_IN')
SRC = Net('SRC')
gnd = Net('GND')

# ── Components ────────────────────────────────────────
v1 = Part('Device', 'Battery', value='5000V', footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical')  # PSU 5kV
s1 = Part('Device', 'SW_SPST', value='SW', footprint='Button_Switch_THT:SW_PUSH_6mm')  # S1 Carga
r1 = Part('Device', 'R', value='1e+04Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R_lim 10kΩ
c1 = Part('Device', 'C', value='6e-07F', footprint='Capacitor_SMD:C_0805_2012Metric')  # C 0.6µF
s2 = Part('Device', 'SW_SPST', value='SW', footprint='Button_Switch_THT:SW_PUSH_6mm')  # SCR/IGBT
l1 = Part('Device', 'L', value='2.5e-07H', footprint='Inductor_SMD:L_0805_2012Metric')  # L0 0.25µH
l2 = Part('Device', 'L', value='2.5e-07H', footprint='Inductor_SMD:L_0805_2012Metric')  # L1 0.25µH
l3 = Part('Device', 'L', value='2.5e-07H', footprint='Inductor_SMD:L_0805_2012Metric')  # L2 0.25µH
l4 = Part('Device', 'L', value='2.5e-07H', footprint='Inductor_SMD:L_0805_2012Metric')  # L3 0.25µH
r2 = Part('Device', 'R', value='50Ω', footprint='Resistor_SMD:R_0805_2012Metric')  # R_ant 50Ω

# ── Connections ───────────────────────────────────────
v1['~'][1] += SRC
v1['~'][2] += gnd
s1['~'][1] += SRC
s1['~'][2] += CARGA_IN
r1['~'][1] += CARGA_IN
r1['~'][2] += BANCO
c1['~'][1] += BANCO
c1['~'][2] += gnd
s2['~'][1] += BANCO
s2['~'][2] += PFN_IN
l1['~'][1] += PFN_IN
l1['~'][2] += PFN1
l2['~'][1] += PFN1
l2['~'][2] += PFN2
l3['~'][1] += PFN2
l3['~'][2] += PFN3
l4['~'][1] += PFN3
l4['~'][2] += ANT_IN
r2['~'][1] += ANT_IN
r2['~'][2] += gnd

# ── Export ────────────────────────────────────────────
ERC()                        # Electrical Rules Check
generate_netlist()            # Salida: circuit.net

if __name__ == '__main__':
    # También se puede generar SVG del esquemático:
    # generate_schematic()
    pass