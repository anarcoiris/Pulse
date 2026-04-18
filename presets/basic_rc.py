"""
presets/basic_rc.py
===================
Preset: circuito RC simple (carga exponencial).

Topologia:
    V1 (5V) → R1 (1kΩ) → C1 (100µF) → GND

Util como introduccion al uso del editor y para verificar la exponencial
de carga: V_C(t) = V1 * (1 - exp(-t / RC))
  tau = RC = 1000 * 100e-6 = 100 ms
"""

from ui.editor import CircuitGraph


def load() -> CircuitGraph:
    """
    Devuelve un CircuitGraph con un divisor RC basico.

    Nodos:
        A   = salida positiva de la fuente
        B   = nodo intermedio (entre R y C)
        GND = referencia
    """
    g = CircuitGraph()

    # PSU: V, vertical en (3,4) → A → GND
    g.add('V', 3, 4, 'V', 5.0, 'V1 5V', 'A', 'GND')

    # R1: horizontal en (5,4) → A → B
    g.add('R', 5, 4, 'H', 1000.0, 'R1 1kΩ', 'A', 'B')

    # C1: vertical en (7,4) → B → GND
    g.add('C', 7, 4, 'V', 100e-6, 'C1 100µF', 'B', 'GND')

    # Tierra GND
    g.add('GND', 3, 5, 'V', 0.0, 'GND', 'GND', 'GND')
    g.add('GND', 7, 5, 'V', 0.0, 'GND', 'GND', 'GND')

    return g


LABEL       = 'RC Simple'
DESCRIPTION = 'V1=5V | R=1kΩ | C=100µF | tau=100ms'
