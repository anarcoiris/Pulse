"""
examples/demo_pcb_layout.py
============================
Demo completo del motor de layout PCB de PulseLab Forge.

Genera 3 PCBs de ejemplo:
  1. Arduino Shield — regulador + bypass caps + header
  2. LED Driver — 555 astable + MOSFET + LEDs en línea
  3. Sensor Node ESP8266 — WiFi MCU + LDO + sensores

Cada uno se guarda como .kicad_pcb listo para abrir en KiCad.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.pcb_layout import PCBLayout, FootprintPresets


def demo_voltage_divider():
    """
    PCB minimal: Divisor de tensión con 2 resistencias + header.
    Board: 20×15mm — ideal para pruebas rápidas.
    """
    print("=== 1. Divisor de Tensión (20×15mm) ===")

    pcb = PCBLayout(
        board_width=20.0, board_height=15.0,
        corner_radius=1.0,
        trace_width=0.30,
        project_name="Voltage Divider",
    )

    # Componentes
    j1 = pcb.add_pin_header("J1", 3, x=3.0, y=5.0, value="VIN-VOUT-GND")
    r1 = pcb.add_resistor("R1", "10k", x=10.0, y=5.0,
                           net1="VIN", net2="VOUT")
    r2 = pcb.add_resistor("R2", "22k", x=10.0, y=10.0,
                           net1="VOUT", net2="GND")

    # Alineación
    pcb.align_vertical(r1, r2, x=12.0)

    # Trazas
    pcb.trace(j1, "1", r1, "1", net="VIN")
    pcb.trace(r1, "2", r2, "1", net="VOUT")
    pcb.trace(j1, "2", r1, "2", net="VOUT")
    pcb.trace(j1, "3", r2, "2", net="GND")

    # Texto
    pcb.add_text("PulseLab", 10.0, 13.5, size=1.0)

    out = pcb.save("output/01_voltage_divider/board.kicad_pcb")
    pcb.export_enclosure(Path("output/01_voltage_divider/enclosures"))
    print(f"  Guardado: {out}")
    print(f"  Stats: {pcb.stats()}")
    return pcb


def demo_555_led_driver():
    """
    PCB 555 LED Driver: 555 en modo astable + transistor + 4 LEDs.
    Board: 40×25mm
    """
    print("\n=== 2. 555 LED Driver (40×25mm) ===")

    pcb = PCBLayout(
        board_width=40.0, board_height=25.0,
        corner_radius=1.5,
        trace_width=0.30,
        project_name="555 LED Blinker",
    )

    # Header de alimentación
    j_pwr = pcb.add_pin_header("J1", 2, x=3.0, y=8.0, value="VCC/GND")

    # NE555 — DIP-8 centrado
    u1 = pcb.add_dip_ic("U1", 8, x=15.0, y=12.0, value="NE555")

    # Resistencias de timing
    r1 = pcb.add_resistor("R1", "10k", x=8.0, y=5.0, net1="VCC", net2="DIS")
    r2 = pcb.add_resistor("R2", "47k", x=8.0, y=10.0, net1="DIS", net2="THR")

    # Capacitor de timing
    c1 = pcb.add_capacitor("C1", "10uF", x=8.0, y=17.0, net1="THR", net2="GND")

    # Bypass cap
    c2 = pcb.add_capacitor("C2", "100nF", x=8.0, y=22.0, net1="VCC", net2="GND")

    # Resistencias de LEDs — distribuidas
    r_leds = []
    leds_x_start = 28.0
    for i in range(4):
        r = pcb.add_resistor(
            f"R{i+3}", "330",
            x=leds_x_start, y=6.0 + i * 5.0,
            net1="OUT", net2=f"LED{i+1}",
        )
        r_leds.append(r)

    # Alinear resistencias de timing verticalmente
    pcb.align_vertical(r1, r2, c1, c2, x=8.0)

    # Distribuir resistencias de LED uniformemente
    pcb.distribute_vertical(*r_leds, start_y=6.0, spacing=5.0, x=leds_x_start)

    # LEDs (representados como headers de 2 pines)
    for i in range(4):
        pcb.add_pin_header(f"D{i+1}", 2,
                           x=35.0, y=6.0 + i * 5.0,
                           value="LED")

    # Traza VCC bus
    pcb.trace_bus([(3.0, 8.0), (3.0, 3.0), (8.0, 3.0), (15.0, 3.0)],
                  width=0.5, net="VCC")

    # Mounting holes
    pcb.add_mounting_holes_corners(margin=3.0, drill=2.5)

    # Texto
    pcb.add_text("555 LED BLINKER", 20.0, 24.0, size=1.2)
    pcb.add_text("PulseLab Forge", 20.0, 1.5, size=0.8)

    out = pcb.save("output/02_555_led_driver/board.kicad_pcb")
    pcb.export_enclosure(Path("output/02_555_led_driver/enclosures"))
    print(f"  Guardado: {out}")
    print(f"  Stats: {pcb.stats()}")
    return pcb


def demo_esp8266_sensor_node():
    """
    PCB Sensor Node: ESP8266 + regulador AMS1117 + sensor header + bypass caps.
    Board: 60×45mm — diseño profesional con zonas funcionales separadas.

    Layout por zonas:
      ┌──────────────────────────────────────────────┐
      │  [Power Zone]    [MCU Zone]     [IO Zone]    │
      │  J1 → U1         U2 (ESP)       J2 sensor   │
      │  C1   C2         C3   C4        D1 LED      │
      │                  R1 R2 R3                    │
      │           [Programming Zone]                 │
      │                J3 UART                       │
      └──────────────────────────────────────────────┘
    """
    print("\n=== 3. ESP8266 Sensor Node (60×45mm) ===")

    pcb = PCBLayout(
        board_width=60.0, board_height=45.0,
        corner_radius=2.5,
        trace_width=0.25,
        project_name="ESP8266 Sensor Node",
    )

    # ── POWER ZONE (izquierda, x: 5-20) ──────────────
    # Entrada de alimentación — borde izquierdo
    j_pwr = pcb.add_pin_header("J1", 2, x=5.5, y=12.0, value="5V IN")

    # AMS1117-3.3 (SOT-223) — centrado en la zona de potencia
    u_reg = pcb.add_sot223("U1", "AMS1117-3.3", x=15.0, y=12.0,
                           net1="GND", net2="3V3", net3="5V")

    # Bypass caps del regulador — simétricos respecto a U1
    c_in  = pcb.add_capacitor("C1", "10uF", x=10.0, y=18.0,
                               net1="5V", net2="GND", package="0805")
    c_out = pcb.add_capacitor("C2", "10uF", x=20.0, y=18.0,
                               net1="3V3", net2="GND", package="0805")

    # ── MCU ZONE (centro, x: 22-45) ──────────────────
    mcu_x = 33.0
    mcu_y = 18.0

    # ESP-12F como DIP-16
    u_esp = pcb.add_dip_ic("U2", 16, x=mcu_x, y=mcu_y, value="ESP-12F")

    # Bypass caps — simétricos a ambos lados del ESP, arriba
    c3 = pcb.add_capacitor("C3", "100nF", x=mcu_x - 8, y=8.0,
                            net1="3V3", net2="GND")
    c4 = pcb.add_capacitor("C4", "100nF", x=mcu_x + 8, y=8.0,
                            net1="3V3", net2="GND")

    # Pull-ups — debajo del ESP, espaciados uniformemente
    r_en    = pcb.add_resistor("R1", "10k", x=mcu_x - 8, y=mcu_y + 12,
                                net1="3V3", net2="EN")
    r_gpio0 = pcb.add_resistor("R2", "10k", x=mcu_x,     y=mcu_y + 12,
                                net1="3V3", net2="GPIO0")
    r_gpio2 = pcb.add_resistor("R3", "10k", x=mcu_x + 8, y=mcu_y + 12,
                                net1="3V3", net2="GPIO2")

    # Alinear pull-ups horizontalmente
    pcb.align_horizontal(r_en, r_gpio0, r_gpio2, y=mcu_y + 12)

    # ── IO ZONE (derecha, x: 48-57) ──────────────────
    # Sensor header — borde derecho superior
    j_sensor = pcb.add_pin_header("J2", 4, x=52.0, y=10.0,
                                   value="I2C Sensor")

    # Status LED + resistencia
    r_led = pcb.add_resistor("R4", "330", x=48.0, y=32.0,
                              net1="GPIO2", net2="LED")
    j_led = pcb.add_pin_header("D1", 2, x=53.0, y=32.0, value="LED")

    # ── PROGRAMMING ZONE (abajo-centro) ──────────────
    j_prog = pcb.add_pin_header("J3", 6, x=mcu_x, y=40.0,
                                 rotation=90, value="UART PROG")

    # ── RUTEO AUTÓMOMAS (A* GRID) y COBRE ─────────────
    # Plano de Cobre envolvente para GND
    pcb.add_copper_pour(net="GND", margin=1.5)

    # Ruteo automático pin-a-pin (A*) para el resto de redes aéreas
    # El GND no se rutea con trazas por el plano de masa
    print("  Calculando Auto-route P2P Manhattan...")
    pcb.autoroute(layer="F.Cu", width=0.3, grid_size=0.5)

    # ── Mounting holes en las 4 esquinas ──────────────
    pcb.add_mounting_holes_corners(margin=3.5)

    # ── Texto ─────────────────────────────────────────
    pcb.add_text("ESP8266 Sensor Node", 30.0, 3.0, size=1.2)
    pcb.add_text("PulseLab Forge v1.0", 30.0, 43.5, size=0.8)
    pcb.add_text("3V3", 20.0, 5.0, size=0.7)
    pcb.add_text("GND", mcu_x, 37.5, size=0.7)
    pcb.add_text("PWR", 12.0, 8.5, size=0.7)
    pcb.add_text("MCU", mcu_x, mcu_y - 12, size=0.7)
    pcb.add_text("IO", 53.0, 6.0, size=0.7)

    out = pcb.save("output/03_esp8266_node/board.kicad_pcb")
    pcb.export_enclosure(Path("output/03_esp8266_node/enclosures"))
    
    # Run design review
    from knowledge.layout_reviewer import LayoutReviewer
    reviewer = LayoutReviewer(pcb)
    print("\n--- AI Layout Review ---")
    print(reviewer.generate_report())
    print("------------------------\n")
    
    print(f"  Guardado: {out}")
    print(f"  Stats: {pcb.stats()}")
    return pcb


def test_kicad_export():
    """Intenta exportar Gerbers si KiCad está disponible."""
    from bridge.kicad_bridge import KiCadBridge

    bridge = KiCadBridge()
    print(f"\n=== KiCad Detection ===")
    status = bridge.status()
    for k, v in status.items():
        print(f"  {k:20s}: {v}")

    if bridge.available:
        print("\n=== Exporting Gerbers from demo board ===")
        pcb_path = Path("output/01_voltage_divider/board.kicad_pcb")
        if pcb_path.exists():
            result = bridge.export_gerbers(pcb_path,
                                            Path("output/01_voltage_divider/gerbers"))
            print(f"  Success: {result.get('success')}")
            print(f"  Files: {result.get('count', 0)} Gerbers")
            if result.get('stderr'):
                print(f"  Stderr: {result['stderr'][:200]}")
            if result.get('files'):
                for f in result['files']:
                    print(f"    {f}")
    else:
        print("  KiCad no disponible — Gerbers no generados")
        print("  Las placas .kicad_pcb se pueden abrir manualmente en KiCad PCBNEW")


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════╗")
    print("║  PulseLab Forge — PCB Layout Engine Demo        ║")
    print("╚══════════════════════════════════════════════════╝\n")

    demo_voltage_divider()
    demo_555_led_driver()
    demo_esp8266_sensor_node()
    test_kicad_export()

    print("\n✅ Demo completo. Las placas están en output/")
    print("   Abre cualquier .kicad_pcb en KiCad 8 PCBNEW para verlas.")
