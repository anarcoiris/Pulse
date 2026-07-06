"""
presets/esp32s2_usb_devkit.py
================================
ESP32-S2 devboard: native USB + optional UART header, 3.3V LDO from 5V USB.
"""
from core.circuit_graph import CircuitGraph


def load() -> CircuitGraph:
    g = CircuitGraph()

    g.add("V", 2, 2, "H", 5.0, "VUSB", n1="VUSB", n2="GND")

    ldo_pins = {"1": "GND", "2": "VCC33", "3": "VUSB"}
    u1 = g.add(
        "IC", 8, 6, "H", value="AMS1117-3.3", label="U1",
        pins=ldo_pins, width=3, height=3,
    )
    u1.symbol_id = "Regulator_Linear:AMS1117-3.3"

    esp_pins = {
        "1": "GND",
        "2": "VCC33",
        "3": "EN",
        "4": "GPIO0",
        "19": "USB_DM",
        "20": "USB_DP",
        "43": "MCU_TX",
        "44": "MCU_RX",
        "47": "GND",
    }
    u2 = g.add(
        "MCU", 16, 5, "V", value="ESP32-S2", label="U2",
        pins=esp_pins, width=6, height=16,
    )
    u2.symbol_id = "MCU_Espressif:ESP32-S2"

    r_en = g.add("R", 12, 4, "H", 10000, "R_EN")
    r_en.n1, r_en.n2 = "VCC33", "EN"

    g.add("C", 10, 10, "H", 10e-6, "C_VBUS", n1="VUSB", n2="GND")
    g.add("C", 18, 10, "H", 10e-6, "C_ESP_H", n1="VCC33", n2="GND")
    g.add("C", 20, 10, "H", 100e-9, "C_ESP_L", n1="VCC33", n2="GND")

    # Optional UART header for external CP2102 programming
    j_uart_pins = {
        "1": "VCC33", "2": "GND", "3": "MCU_TX", "4": "MCU_RX",
        "5": "EN", "6": "GPIO0",
    }
    j1 = g.add(
        "IC", 24, 6, "V", value="UART_HDR", label="J1",
        pins=j_uart_pins, width=2, height=4,
    )
    j1.symbol_id = "Connector_Generic:Conn_01x06"

    g.add("GND", 4, 14, "V", 0, "GND", n1="GND", n2="")

    return g
