"""
presets/emp_pfn.py
==================
Preset: Circuito EMP con Red Formadora de Pulso (PFN) del reporte tecnico.

Topologia:
    PSU 5kV → S1 (carga) → R_LIM (10kΩ) → BANCO → SCR/IGBT → PFN(4×LC) → R_ANT 50Ω
                                            |
                                        C_BANCO (0.6µF) → GND

Corresponde a la subseccion 4.9 de docs/latex_fix/report.tex.

Layout en la cuadricula (GRID_SIZE = 40px):
    Fila 4 = bus positivo (rail horizontal)
    Fila 5 = bus de tierra (GND rail)
    CANVAS_X = 200, CANVAS_Y = 50
"""

from core.circuit_graph import CircuitGraph, PlacedComponent


def load() -> CircuitGraph:
    """
    Devuelve un CircuitGraph pre-cargado con la topologia EMP/PFN.

    Nodos principales:
        SRC      = salida positiva de la PSU (antes de S1)
        CARGA_IN = entrada de la resistencia de carga (entre S1 y R_LIM)
        BANCO    = nodo del banco de condensadores (entre R_LIM, C_BANCO y SCR)
        PFN_IN   = entrada de la red LC (salida del SCR)
        PFN1-3   = nodos intermedios de la PFN
        ANT_IN   = nodo de entrada a la antena (salida de la PFN)
        GND      = referencia de tierra
    """
    g = CircuitGraph()

    # ── Fuente de alta tension (V, vertical) ──────────────────────────────────
    # col=1, fila 4→5: t1='SRC', t2='GND'
    g.add('V', 1, 4, 'V', 5000.0, 'PSU 5kV', 'SRC', 'GND')
    g._counter = 1  # force uid formatting

    # ── Switch de carga S1 (H) ────────────────────────────────────────────────
    # col=2, fila 4: SRC → CARGA_IN (40px wire: t1 at col2, t2 at col3)
    g.add('S', 2, 4, 'H', 0.0, 'S1 Carga', 'SRC', 'CARGA_IN',
          R_on=0.001, R_off=1e9, is_closed=False)

    # ── Resistencia de limitacion R_LIM (H) ───────────────────────────────────
    # col=4, fila 4: CARGA_IN → BANCO
    g.add('R', 4, 4, 'H', 10000.0, 'R_lim 10kΩ', 'CARGA_IN', 'BANCO')

    # ── Banco de condensadores C_BANCO (V) ────────────────────────────────────
    # col=6, fila 4→5: BANCO → GND
    g.add('C', 6, 4, 'V', 0.6e-6, 'C 0.6µF', 'BANCO', 'GND')

    # ── Interruptor SCR/IGBT (H) ──────────────────────────────────────────────
    # col=7, fila 4: BANCO → PFN_IN
    g.add('S', 7, 4, 'H', 0.0, 'SCR/IGBT', 'BANCO', 'PFN_IN',
          R_on=0.01, R_off=1e9, is_closed=False)

    # ── Red Formadora de Pulso: 4 inductores en serie (H) ─────────────────────
    # L0: col=9,  PFN_IN → PFN1
    # L1: col=11, PFN1   → PFN2
    # L2: col=13, PFN2   → PFN3
    # L3: col=15, PFN3   → ANT_IN
    pfn_nodes = ['PFN_IN', 'PFN1', 'PFN2', 'PFN3', 'ANT_IN']
    for k in range(4):
        col  = 9 + k * 2
        n1   = pfn_nodes[k]
        n2   = pfn_nodes[k + 1]
        lbl  = f'L{k} 0.25µH'
        g.add('L', col, 4, 'H', 0.25e-6, lbl, n1, n2)

    # ── Carga: Antena TEM Horn 50 Ohm (V) ────────────────────────────────────
    # col=17, fila 4→5: ANT_IN → GND
    g.add('R', 17, 4, 'V', 50.0, 'R_ant 50Ω', 'ANT_IN', 'GND')

    # ── Marcas de tierra (GND) ───────────────────────────────────────────────
    # Tierra junto a PSU (col=1, fila=5)
    g.add('GND', 1, 5, 'V', 0.0, 'GND', 'GND', 'GND')
    # Tierra junto a C_BANCO (col=6, fila=5)
    g.add('GND', 6, 5, 'V', 0.0, 'GND', 'GND', 'GND')
    # Tierra junto a R_ANT (col=17, fila=5)
    g.add('GND', 17, 5, 'V', 0.0, 'GND', 'GND', 'GND')

    return g


# Metadata for the preset picker
LABEL       = 'EMP PFN 5kV'
DESCRIPTION = ('Banco 6×0.1µF / 5kV / 50Ω  |  '
               'SCR/IGBT  |  PFN 4 secciones LC  |  '
               'Antena TEM Horn')
