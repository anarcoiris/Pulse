
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.forge_api import generate_pcb
from core.circuit_graph import CircuitGraph, PlacedComponent

def create_esp32_devboard_v2():
    graph = CircuitGraph()
    
    # 1. MCU Core (ESP32-WROOM-32)
    mcu = graph.add('MCU', 10, 10, 'V', 'ESP32-WROOM-32', 'U3')
    mcu.width, mcu.height = 6, 19
    mcu.symbol_id = 'RF_Module:ESP32-WROOM-32'
    mcu.footprint_id = 'RF_Module:ESP32-WROOM-32'
    mcu.pins = {
        "1": "GND", "2": "VCC33", "3": "EN",
        "25": "IO0", "24": "IO2",
        "35": "MCU_TX", "34": "MCU_RX",
        "38": "GND",
    }
    
    # 2. Power Stage (AMS1117-3.3)
    ldo = graph.add('IC', 22, 10, 'V', 3.3, 'U2')
    ldo.width, ldo.height = 3, 3
    ldo.symbol_id = 'Regulator_Linear:AMS1117-3.3'
    ldo.pins = {"1": "GND", "2": "VCC33", "3": "VBUS"}
    
    # 3. USB-UART Bridge (CH340G)
    usb = graph.add('IC', 4, 10, 'V', 5.0, 'U1')
    usb.width, usb.height = 4, 8
    usb.symbol_id = 'Interface_USB:CH340G'
    usb.pins = {
        "1": "GND", "2": "MCU_TX", "3": "MCU_RX", "4": "VCC33",
        "5": "USB_D+", "6": "USB_D-", "16": "VBUS"
    }

    # 4. Connectors (VBUS input)
    vbus = graph.add('V', 2, 2, 'H', 5.0, 'USB_5V')
    vbus.n1, vbus.n2 = "VBUS", "GND"
    
    r_en = graph.add('R', 10, 8, 'H', 10000, 'R_EN_PULLUP')
    r_en.n1, r_en.n2 = "VCC33", "EN"
    
    r_led = graph.add('R', 18, 10, 'H', 330, 'R_LED')
    r_led.n1, r_led.n2 = "IO2", "LED_A"
    led = graph.add('L', 18, 12, 'V', 0.02, 'LED_IO2')
    led.n1, led.n2 = "LED_A", "GND"

    result = generate_pcb(graph, out_dir='output/esp32_v2')
    return result

if __name__ == "__main__":
    try:
        res = create_esp32_devboard_v2()
        print(f"SUCCESS: PCB generated at {res['path']}")
        stats = res.get('stats', {})
        print(f"FACT: Stats: {stats}")
    except Exception as e:
        print(f"FAILURE: {str(e)}")
