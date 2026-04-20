import sys
import os

sys.path.append(os.path.abspath('.'))

from presets.mcu_uart import load
from bridge.pcb_layout import PCBLayout
from knowledge.layout_reviewer import LayoutReviewer

print("1. Cargando Circuito IoT (ESP8266 + CH340)...")
graph = load()

print("2. Generando Diseño PCB Multipin...")
pcb = PCBLayout(board_width=50, board_height=40, project_name="IoT_Node")

# Manual mapping logic from pulse_lab (since we're running headlessly)
row, col = 0, 0
for c in graph.components:
    x = 10 + col * 12
    y = 10 + row * 10
    val = str(c.value) if c.value else c.etype
    
    if c.etype == 'R': pcb.add_resistor(c.uid, val, x, y, net1=c.n1, net2=c.n2)
    elif c.etype == 'C': pcb.add_capacitor(c.uid, val, x, y, net1=c.n1, net2=c.n2)
    elif c.etype == 'L': pcb.add_inductor(c.uid, val, x, y, net1=c.n1, net2=c.n2)
    elif c.etype in ('IC', 'MCU'):
        pkg = "SOP16"
        if "ESP" in val.upper(): pkg = "ESP12"
        pcb.add_ic(c.uid, val, x, y, pins=getattr(c, 'pins', {}), pkg_type=pkg)
    elif c.etype == 'GND': pcb.add_pin_header(c.uid, 1, x, y, value="GND")
    else: pcb.add_pin_header(c.uid, 2, x, y, value=c.etype)
        
    col += 1
    if col > 3:
        col = 0
        row += 1

print("3. Ejecutando A* Autorouter 2D multipin...")
pcb.add_copper_pour("GND")
pcb.autoroute(width=0.25, grid_size=0.25)
out = 'output/test_mcu/board.kicad_pcb'
os.makedirs('output/test_mcu', exist_ok=True)
pcb.save(out)
print(f"PCB Guardado: {out}")
print("Stats:", pcb.stats())

print("\n4. Revisando DCR AI...")
rev = LayoutReviewer(pcb)
status = rev.audit()
print(f"AI Approved: {status}")

print("5. Renderizando SVG...")
from bridge.gerber_export import export_svg
from bridge.kicad_bridge import KiCadBridge
kb = KiCadBridge()
export_svg(kb._cli, out, 'output/test_mcu')
