"""
circuit_generator.py
====================
Generador de esquemas de circuito para el sistema EMP/PFN.

Utiliza schemdraw (BSD license) para producir diagramas de calidad IEEE.
Los PDF generados se incluyen directamente en report.tex via \includegraphics.

Salidas:
    - PDF: vectorial, listo para LaTeX (\includegraphics)
    - PNG: raster para preview o documentacion rapida

Uso:
    python circuit_generator.py                        # genera en docs/latex_fix/
    python circuit_generator.py --dir /ruta/salida     # directorio personalizado
"""

import os
import math
import argparse
import matplotlib
matplotlib.use('Agg')   # backend sin ventana: requerido para generacion offline

import schemdraw
import schemdraw.elements as elm


# =============================================================================
# Utilidades
# =============================================================================

def _save(drawing, basename: str, output_dir: str, dpi: int = 200) -> tuple:
    """Guarda el esquema en PDF y PNG. Devuelve (pdf_path, png_path)."""
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f'{basename}.pdf')
    png_path = os.path.join(output_dir, f'{basename}.png')
    drawing.save(pdf_path, dpi=dpi)
    drawing.save(png_path, dpi=dpi)
    print(f"  PDF: {pdf_path}")
    print(f"  PNG: {png_path}")
    return pdf_path, png_path


# =============================================================================
# Esquema 1: Circuito EMP Mejorado (SCR/IGBT + PFN)
# =============================================================================

def generate_emp_schematic(output_dir: str = '.', basename: str = 'circuit_redesign',
                           dpi: int = 200) -> tuple:
    """
    Genera el esquema del circuito EMP/PFN mejorado con conmutacion de estado solido.

    Topologia representada:
        HV PSU -> S1 (carga) -> R_limite -> BANCO -> SCR -> PFN (LC ladder) -> Antena (50 Ohm)
                                              |
                                            C_banco
                                              |
                                             GND

    Equivale al circuito de la subseccion 4.9 de report.tex.

    Returns:
        (pdf_path, png_path)
    """
    print("Generando esquema EMP mejorado...")
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.8, fontsize=11)

        # ── Fuente HV (vertical, izquierda) ──────────────────────────────
        V1 = d.add(elm.SourceV().up().label('HV PSU\n5 kV DC', loc='left'))

        # ── Switch de carga S1 ────────────────────────────────────────────
        d.add(elm.Line().right().length(0.8))
        S1 = d.add(elm.Switch().right().label('S1\nCarga', loc='top'))

        # ── Resistencia de limitacion ─────────────────────────────────────
        R_lim = d.add(elm.Resistor().right().label(
            '$R_{lim}$\n10 k$\\Omega$', loc='top'))

        # ── Nodo BANCO: condensador a tierra ──────────────────────────────
        banco_dot = d.add(elm.Dot())
        d.push()
        d.add(elm.Line().down().length(0.5))
        C_banco = d.add(elm.Capacitor().down().label(
            '$C_{banco}$\n0.6 µF', loc='right'))
        d.add(elm.Line().down().length(0.2))
        d.add(elm.Ground())
        d.pop()

        # ── Switch SCR/IGBT ───────────────────────────────────────────────
        # El SCR/IGBT es un interruptor controlado por señal de puerta (Gate).
        # Se representa como SPST con la linea de control indicada por etiqueta.
        d.add(elm.Line().right().length(0.5))
        SCR_in = d.add(elm.Dot())
        scr = d.add(elm.Switch().right().label('SCR / IGBT', loc='top'))
        scr_out = d.add(elm.Dot())

        # Linea de puerta (gate) del SCR: control via MCU/555
        d.push()
        d.add(elm.Line().at(SCR_in.end).down().length(1.2))
        d.add(elm.Dot(open=True))
        d.add(elm.Label().label('Gate\n(MCU / 555)', loc='right'))
        d.pop()

        # ── PFN: 2 secciones LC (representativas de las N_PFN=4) ─────────
        # Seccion 1
        L1 = d.add(elm.Inductor2(loops=2).right().label(
            '$L_k = 0.25\\,\\mu$H', loc='top'))
        pfn1 = d.add(elm.Dot())
        d.push()
        d.add(elm.Line().down().length(0.4))
        Ck1 = d.add(elm.Capacitor().down().label('$C_k$', loc='right'))
        d.add(elm.Ground())
        d.pop()

        # Seccion 2
        L2 = d.add(elm.Inductor2(loops=2).right().label('$L_k$', loc='top'))
        pfn2 = d.add(elm.Dot())
        d.push()
        d.add(elm.Line().down().length(0.4))
        Ck2 = d.add(elm.Capacitor().down().label('$C_k$', loc='right'))
        d.add(elm.Ground())
        d.pop()

        # Indicador de secciones adicionales
        d.add(elm.Line().right().length(0.3))
        d.add(elm.Label().label('$\\cdots$', loc='center'))
        d.add(elm.Line().right().length(0.5))
        ant_top = d.add(elm.Dot())

        # ── Carga: Antena TEM Horn (50 Ohm) ──────────────────────────────
        R_ant = d.add(elm.Resistor().down().label(
            '$Z_{ant}$\n50 $\\Omega$\nTEM Horn', loc='right'))
        d.add(elm.Ground())

        # ── Retorno de masa: conectar fondo de la fuente a GND ───────────
        d.add(elm.Ground().at(V1.start))

    print("Guardado en:")
    return _save(d, basename, output_dir, dpi)


# =============================================================================
# Esquema 2: Circuito EMP Original (Spark Gap — para comparacion)
# =============================================================================

def generate_emp_original_schematic(output_dir: str = '.',
                                    basename: str = 'circuit_original',
                                    dpi: int = 200) -> tuple:
    """
    Genera el esquema del circuito EMP original con spark gap.
    Sirve como referencia comparativa frente al diseno mejorado SCR/IGBT.

    Returns:
        (pdf_path, png_path)
    """
    print("Generando esquema EMP original (spark gap)...")
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.8, fontsize=11)

        V1 = d.add(elm.SourceV().up().label('Fuente\nFlyback\n5 kV', loc='left'))
        d.add(elm.Line().right().length(0.5))
        R_lim = d.add(elm.Resistor().right().label(
            '$R_{lim}$\n100 k$\\Omega$', loc='top'))
        banco_dot = d.add(elm.Dot())

        d.push()
        d.add(elm.Line().down().length(0.5))
        C_banco = d.add(elm.Capacitor().down().label(
            '$C_{banco}$\n0.6 µF', loc='right'))
        d.add(elm.Ground())
        d.pop()

        d.add(elm.Line().right().length(0.5))
        # Spark gap: representado como gap de descarga
        sg = d.add(elm.Gap().right().label('Spark\nGap', loc='top'))

        L1 = d.add(elm.Inductor2(loops=2).right().label(
            '$L_{PFN}$', loc='top'))
        R_ant = d.add(elm.Resistor().down().label(
            'Antena\n50 $\\Omega$', loc='right'))
        d.add(elm.Ground())
        d.add(elm.Ground().at(V1.start))

    print("Guardado en:")
    return _save(d, basename, output_dir, dpi)


# =============================================================================
# Generador automatico desde CircuitSimulator
# =============================================================================

def generate_from_simulator(sim, output_dir: str = '.', basename: str = 'circuit_auto',
                             dpi: int = 200) -> tuple:
    """
    Genera un esquema de bloque a partir de un CircuitSimulator ya configurado.

    Limitacion: el layout es lineal (una fila). El layout espacial completo
    (posicion 2D de nodos) es una mejora futura pendiente.

    Args:
        sim: Instancia de CircuitSimulator con topologia definida.

    Returns:
        (pdf_path, png_path)
    """
    print(f"Generando esquema automatico desde CircuitSimulator ({len(sim.elements)} elementos)...")

    def node_name(idx: int) -> str:
        if idx == 0:
            return 'GND'
        return next((k for k, v in sim.nodes.items() if v == idx), str(idx))

    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.5, fontsize=10)

        for el in sim.elements:
            etype, name, n1_idx, n2_idx = el[0], el[1], el[2], el[3]
            n1_name = node_name(n1_idx)
            n2_name = node_name(n2_idx)
            top_label = f'{name}\n{n1_name}→{n2_name}'

            if etype == 'R':
                d.add(elm.Resistor().right().label(
                    f'{name}\n{el[4]:.0f} Ω', loc='top'))
            elif etype == 'C':
                d.add(elm.Capacitor().right().label(
                    f'{name}\n{el[4]*1e6:.2f} µF', loc='top'))
            elif etype == 'L':
                d.add(elm.Inductor2().right().label(
                    f'{name}\n{el[4]*1e6:.3f} µH', loc='top'))
            elif etype == 'V':
                d.add(elm.SourceV().right().label(
                    f'{name}\n{el[4]:.0f} V', loc='top'))
            elif etype == 'S':
                state = 'ON' if el[4] else 'OFF'
                d.add(elm.Switch().right().label(
                    f'{name}\n[{state}]', loc='top'))

    print("Guardado en:")
    return _save(d, basename, output_dir, dpi)


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generador de esquemas EMP')
    parser.add_argument('--dir', default=os.path.join('docs', 'latex_fix'),
                        help='Directorio de salida (default: docs/latex_fix)')
    parser.add_argument('--dpi', type=int, default=200,
                        help='Resolucion PNG (default: 200)')
    args = parser.parse_args()

    generate_emp_schematic(
        output_dir=args.dir, basename='circuit_redesign', dpi=args.dpi)

    generate_emp_original_schematic(
        output_dir=args.dir, basename='circuit_original', dpi=args.dpi)

    print("\nGeneracion completada.")
