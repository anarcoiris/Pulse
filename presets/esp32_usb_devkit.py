"""
presets/esp32_usb_devkit.py
============================
ESP32-WROOM-32 devboard: 5V USB, CH340G UART, AMS1117 3.3V, GPIO headers.
"""
from core.circuit_graph import CircuitGraph


def load() -> CircuitGraph:
    g = CircuitGraph()

    # USB 5V input
    g.add("V", 2, 2, "H", 5.0, "VUSB", n1="VUSB", n2="GND")

    # CH340G USB-UART bridge
    ch340_pins = {
        "1": "GND",
        "2": "MCU_TX",   # CH340 TXD -> ESP RX (GPIO3)
        "3": "MCU_RX",   # CH340 RXD -> ESP TX (GPIO1)
        "4": "VCC33",
        "5": "USB_D+",
        "6": "USB_D-",
        "13": "DTR",
        "14": "RTS",
        "16": "VUSB",
    }
    u1 = g.add(
        "IC", 6, 6, "H", value="CH340G", label="U1",
        pins=ch340_pins, width=3, height=4,
    )
    u1.symbol_id = "Interface_USB:CH340G"
    u1.footprint_id = "Package_SO:SOP-16_3.9x9.9mm_P1.27mm"

    # AMS1117-3.3 LDO
    ldo_pins = {"1": "GND", "2": "VCC33", "3": "VUSB"}
    u2 = g.add(
        "IC", 12, 6, "H", value="AMS1117-3.3", label="U2",
        pins=ldo_pins, width=3, height=3,
    )
    u2.symbol_id = "Regulator_Linear:AMS1117-3.3"

    # ESP32-WROOM-32
    esp_pins = {
        "1": "GND",
        "2": "VCC33",
        "3": "EN",
        "25": "IO0",
        "24": "IO2",
        "35": "MCU_TX",
        "34": "MCU_RX",
        "38": "GND",
    }
    u3 = g.add(
        "MCU", 18, 5, "V", value="ESP32-WROOM-32", label="U3",
        pins=esp_pins, width=6, height=19,
    )
    u3.symbol_id = "RF_Module:ESP32-WROOM-32"
    u3.footprint_id = "RF_Module:ESP32-WROOM-32"

    # EN pull-up
    r_en = g.add("R", 14, 4, "H", 10000, "R_EN")
    r_en.n1, r_en.n2 = "VCC33", "EN"

    # BOOT button (GPIO0 to GND when pressed)
    g.add("S", 16, 8, "V", 0, "SW_BOOT", n1="IO0", n2="GND")

    # Decoupling
    g.add("C", 10, 10, "H", 10e-6, "C_VBUS", n1="VUSB", n2="GND")
    g.add("C", 20, 10, "H", 10e-6, "C_ESP_H", n1="VCC33", n2="GND")
    g.add("C", 22, 10, "H", 100e-9, "C_ESP_L", n1="VCC33", n2="GND")
    g.add("C", 8, 10, "H", 100e-9, "C_CH340", n1="VUSB", n2="GND")

    # Status LED on GPIO2
    r_led = g.add("R", 19, 12, "H", 330, "R_LED")
    r_led.n1, r_led.n2 = "IO2", "LED_A"
    g.add("L", 21, 12, "V", 0.02, "LED1", n1="LED_A", n2="GND")

    # GPIO breakout headers (simplified 2x10 representation)
    j1_pins = {str(i): f"GPIO_{i}" for i in range(1, 11)}
    j1_pins.update({"11": "VCC33", "12": "GND", "13": "VUSB", "14": "EN", "15": "IO0", "16": "IO2"})
    j1 = g.add(
        "IC", 26, 4, "V", value="GPIO_HDR_L", label="J1",
        pins=j1_pins, width=2, height=10,
    )
    j1.symbol_id = "Connector_Generic:Conn_02x10_Odd_Even"

    j2_pins = {str(i): f"GPIO_{i + 10}" for i in range(1, 11)}
    j2 = g.add(
        "IC", 29, 4, "V", value="GPIO_HDR_R", label="J2",
        pins=j2_pins, width=2, height=10,
    )
    j2.symbol_id = "Connector_Generic:Conn_02x10_Odd_Even"

    g.add("GND", 4, 14, "V", 0, "GND", n1="GND", n2="")

    return g
