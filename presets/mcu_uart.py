"""
presets/mcu_uart.py
===================
Dibuja un circuito IoT Típico: ESP8266 + CH340 (USB a UART) + Capacitores para validar la nueva arquitectura Multi-Pin y la capacidad visual 2D del AutoRouter de KiCad.
"""
from ui.editor import CircuitGraph

def load() -> CircuitGraph:
    g = CircuitGraph()
    # Fuente de 5V (simulando que está conectado el USB)
    g.add('V', 2, 3, 'V', 5.0, '5V_USB', n1='VUSB', n2='GND')

    # Integrado 1: CH340C (SOP-16) - Puente USB a Serial
    ch340_pins = {
        '1': 'GND',
        '2': 'MCU_RX',  # CH340 TXD connects to MCU RX
        '3': 'MCU_TX',  # CH340 RXD connects to MCU TX
        '4': 'VCC33',   # V33 regulador interrno
        '5': 'USB_D+',
        '6': 'USB_D-',
        '16': 'VUSB'
    }
    g.add('IC', 5, 5, 'H', value='CH340C', label='U1', pins=ch340_pins, width=2, height=3)

    # Condensador de desacoplo para el CH340C
    g.add('C', 8, 8, 'H', 0.1e-6, '100nF', n1='VUSB', n2='GND')

    # Integrado 2: Módulo Wi-Fi ESP8266 (ESP-12)
    esp_pins = {
        '1': 'RST',
        '3': 'EN',
        '8': 'VCC33',
        '15': 'GND',
        '21': 'MCU_RX',
        '22': 'MCU_TX',
    }
    g.add('MCU', 12, 4, 'H', value='ESP8266_Node', label='U2', pins=esp_pins, width=4, height=4)

    # Condensador de rizado para estabilizar el ESP
    g.add('C', 10, 9, 'H', 10e-6, '10uF', n1='VCC33', n2='GND')
    
    # GND principal
    g.add('GND', 4, 11, 'V', 0, 'GND', n1='GND', n2='')

    return g
