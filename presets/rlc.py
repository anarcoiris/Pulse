"""
presets/rlc.py
==============
Preset: circuito RLC serie (respuesta subamortiguada).

Topologia:
    V1 (24V) → R1 (10Ω) → L1 (1mH) → C1 (10µF) → GND

Constantes:
    omega_0 = 1/sqrt(LC) = 1/sqrt(1e-3 * 10e-6) = ~10 krad/s
    alpha   = R/(2L)     = 10/(2e-3) = 5 krad/s
    Sistema subamortiguado (alpha < omega_0)
"""

from core.circuit_graph import CircuitGraph


def load() -> CircuitGraph:
    g = CircuitGraph()

    # PSU: V, vertical en (2,4) → SRC → GND
    g.add('V', 2, 4, 'V', 24.0, 'V1 24V', 'SRC', 'GND')

    # R1: horizontal en (4,4) → SRC → M1
    g.add('R', 4, 4, 'H', 10.0, 'R1 10Ω', 'SRC', 'M1')

    # L1: horizontal en (6,4) → M1 → M2
    g.add('L', 6, 4, 'H', 1e-3, 'L1 1mH', 'M1', 'M2')

    # C1: vertical en (8,4) → M2 → GND
    g.add('C', 8, 4, 'V', 10e-6, 'C1 10µF', 'M2', 'GND')

    # Tierras
    g.add('GND', 2, 5, 'V', 0.0, 'GND', 'GND', 'GND')
    g.add('GND', 8, 5, 'V', 0.0, 'GND', 'GND', 'GND')

    return g


LABEL       = 'RLC Serie'
DESCRIPTION = 'V=24V | R=10Ω | L=1mH | C=10µF | subamortiguado'
