
from bridge.forge_api import generate_pcb
from core.circuit_graph import CircuitGraph, PlacedComponent

def create_esp32_devboard_v2():
    graph = CircuitGraph()
    
    # 1. MCU Core (ESP32-WROOM-32) - 38 pins total (approx)
    mcu = graph.add('MCU', 10, 10, 'V', 'ESP32', 'ESP32-CORE')
    mcu.width, mcu.height = 6, 19
    mcu.pins = {
        "1": "GND", "2": "3V3", "3": "EN", "4": "SENSOR_VP", "5": "SENSOR_VN",
        "30": "TXD0", "31": "RXD0", "38": "GND", "25": "IO2" # GPIO2 LED
    }
    
    # 2. Power Stage (AMS1117-3.3)
    ldo = graph.add('IC', 22, 10, 'V', 3.3, 'AMS1117')
    ldo.width, ldo.height = 3, 3
    ldo.pins = {"1": "GND", "2": "3V3", "3": "VBUS"}
    
    # 3. USB-UART Bridge (CH340G)
    usb = graph.add('IC', 4, 10, 'V', 5.0, 'CH340G')
    usb.width, usb.height = 4, 8
    usb.pins = {
        "1": "GND", "2": "TXD0", "3": "RXD0", "4": "V3", 
        "13": "DTR", "14": "RTS", "16": "VBUS"
    }

    # 4. Connectors (VBUS input)
    vbus = graph.add('V', 2, 2, 'H', 5.0, 'USB_5V')
    vbus.n1, vbus.n2 = "VBUS", "GND"
    
    # 5. Pasivos & Auto-reset
    # (Simplificado para el primer FACT de generación)
    r_en = graph.add('R', 10, 8, 'H', 10000, 'R_EN_PULLUP')
    r_en.n1, r_en.n2 = "3V3", "EN"
    
    led = graph.add('L', 18, 10, 'V', 0.02, 'LED_IO2')
    led.n1, led.n2 = "IO2", "GND"

    # Exportación
    result = generate_pcb(graph, out_dir='output/esp32_v2')
    return result

if __name__ == "__main__":
    try:
        res = create_esp32_devboard_v2()
        print(f"SUCCESS: PCB generated at {res['path']}")
        print(f"FACT: Netlist pins mapped: {len(res['pcb'].nets)}")
    except Exception as e:
        print(f"FAILURE: {str(e)}")
