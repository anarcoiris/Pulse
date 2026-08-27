import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from knowledge.design_experience import record_design_outcome

# Record comprehensive design experience for Flipper Killer MK II V4
exp = record_design_outcome(
    board_id="flipper_killer_mk2_v4_canonical",
    mcu="ESP32-S3-WROOM-1U",
    mcu_package="Custom:ESP32-S3-WROOM-1U-N16R8",
    board_size_mm=(64.0, 48.0),
    component_count=19,
    layer_count=2,
    drc_violations=0,
    routing_success_rate=1.0,
    manufacturing_target="JLCPCB_and_PCBWay",
    gerber_path="output/flipper_killer_production_v4/gerbers/",
    passed=True,
    lessons=[
        "Hirose DM3AT MicroSD pads must be rotated individually by 270 degrees while keeping footprint orientation to avoid 0.10mm pad bridges and solder mask DRC errors.",
        "Ground copper zones in KiCad 10 must use dynamic polygon definitions (pts ...) without static filled_polygon blocks to allow KiCad's polygon engine to compute 0.20mm thermal clearances dynamically.",
        "Flipper Zero 18-pin canonical GPIO header pinout requires shared SPI on Pins 2 (MOSI), 3 (MISO), 5 (SCK); CC1101 CSN on Pin 4 and GDO0 on Pin 6; NRF24 CSN on Pin 7 and CE on Pin 16; ESP32-S3 UART on Pins 13 (RX) and 14 (TX).",
        "BAT54C dual Schottky diode (D1) with common cathode allows seamless OR-ing of 5V power from Flipper Zero (Pin 1) and USB-C VBUS without back-feeding.",
        "USB-C alignment holes are non-plated through-holes (pad np_thru_hole) governed by hole_to_copper_clearance (0.25mm) and must not be connected to copper planes.",
        "AMS1117-3.3 Tab (Pad 4) and ESP32 EPAD (Pad 41) require solid copper tab connections to ground planes for low thermal resistance."
    ],
    component_placement_rules=[
        "Place RF modules (CC1101 and NRF24) near top edges to minimize trace inductance and antenna shadowing.",
        "Keep USB-C connector on left edge aligned with board mechanical cutout.",
        "Position 18-pin 2.54mm header along bottom edge centered for standard Flipper Zero plug-and-play mating."
    ],
    critical_nets=["SPI_MOSI", "SPI_MISO", "SPI_SCK", "CC1101_CSN", "NRF24_CSN", "UART_RX", "UART_TX", "PWR_GND", "PWR_3V3_ESP"]
)

print(f"Recorded and ingested experience: {exp.board_id}")
print(f"Total lessons: {len(exp.lessons_learned)}")
print(f"Ingested to RAG successfully!")
