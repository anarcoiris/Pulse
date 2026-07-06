"""
core/rf_tools.py
================
Cálculos de radiofrecuencia y líneas de transmisión.

Todas las ecuaciones con referencia explícita:
  [P] Pozar, "Microwave Engineering", 4th ed., Wiley 2012.
  [H] Hammerstad & Jensen (1980), IEEE MTT-S, pp.407-409.
  [IPC] IPC-2221B, "Generic Standard on Printed Board Design", 2012.
  [W]  Wheeler, "Transmission Line Properties of Parallel Strips Separated
       by a Dielectric Sheet", IEEE Trans. MTT, 1965.
"""

from __future__ import annotations
import math
import cmath
from typing import Union

# ─── Constantes ──────────────────────────────────────────────────────────────

Z0_FREE_SPACE = 376.730  # Ω — impedancia del espacio libre


# ─── Microstrip ───────────────────────────────────────────────────────────────

def microstrip_impedance(
    w_mm: float,
    h_mm: float,
    er: float,
    t_mm: float = 0.035,
    freq_ghz: float = 1.0,
) -> dict:
    """
    Impedancia característica Z₀ de línea microstrip.

    Ref [H]: Hammerstad & Jensen, IEEE MTT-S 1980, eq. (1)-(5).
    Ref [P]: Pozar 4th ed., §3.8, eq. (3.195)-(3.197).

    Args:
        w_mm:     Ancho de pista (mm).
        h_mm:     Alto del substrato dieléctrico (mm).
        er:       Constante dieléctrica relativa del substrato (adim.).
        t_mm:     Grosor del cobre (mm). Default = 0.035 mm (1oz Cu).
        freq_ghz: Frecuencia (GHz) para cálculo de longitud de onda.

    Returns:
        dict con:
          Z0        – Impedancia característica (Ω)
          eff_er    – Constante dieléctrica efectiva (adim.)
          phase_vel – Velocidad de fase (m/s)
          lambda_mm – Longitud de onda a freq_ghz (mm)
          loss_conductor_dBpm – Pérdida conductora aprox (dB/m por GHz)
    """
    if w_mm <= 0 or h_mm <= 0 or er < 1.0:
        raise ValueError("w_mm, h_mm deben ser > 0 y er >= 1")

    # Corrección por grosor de cobre [H]
    if t_mm > 0 and t_mm < h_mm:
        dw = t_mm / math.pi * (1.0 + math.log(2.0 * h_mm / t_mm))
        w_eff = w_mm + dw
    else:
        w_eff = w_mm

    u = w_eff / h_mm  # razón W/h (adim.)

    # ─ Permitividad efectiva [H eq.3] ─
    a = 1.0 + (1.0/49.0) * math.log(
        (u**4 + (u/52.0)**2) / (u**4 + 0.432)
    ) + (1.0/18.7) * math.log(1.0 + (u/18.1)**3)

    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053

    eff_er = ((er + 1.0) / 2.0 + (er - 1.0) / 2.0
              * (1.0 + 10.0 / u) ** (-a * b))

    # ─ Impedancia [H eq.1-2] ─
    if u < 1.0:
        f = 6.0 + (2.0 * math.pi - 6.0) * math.exp(-(30.666 / u) ** 0.7528)
        Z0 = (Z0_FREE_SPACE / (2.0 * math.pi * math.sqrt(eff_er))
              * math.log(f / u + math.sqrt(1.0 + (2.0 / u) ** 2)))
    else:
        Z0 = (Z0_FREE_SPACE /
              (math.sqrt(eff_er)
               * (u + 1.393 + 0.667 * math.log(u + 1.444))))

    C = 3e11  # velocidad de la luz en mm/s (3×10¹¹ mm/s)
    phase_vel = C / math.sqrt(eff_er)  # mm/s → en mm/s
    freq_hz   = freq_ghz * 1e9
    lambda_mm = phase_vel / freq_hz if freq_hz > 0 else float('inf')

    # Pérdida conductora aproximada (Cu puro) [P §3.8]
    # α_c ≈ R_s / (Z0 × W_eff) [Np/m]  →  dB/m = 8.686 × α_c
    rho_cu  = 1.72e-8  # Ω·m resistividad cobre
    Rs      = math.sqrt(math.pi * freq_hz * rho_cu * 4e-7 * math.pi) / 2.0
    alpha_c = Rs / (Z0 * w_eff * 1e-3) if w_eff > 0 else 0.0
    loss_dBpm = 8.686 * alpha_c

    return {
        "Z0": round(Z0, 3),
        "eff_er": round(eff_er, 4),
        "phase_vel_m_s": round(phase_vel * 1e-3, 0),  # mm/s → m/s
        "lambda_mm": round(lambda_mm, 3),
        "loss_conductor_dB_per_m": round(loss_dBpm, 4),
        "W_h": round(u, 4),
        "inputs": {"w_mm": w_mm, "h_mm": h_mm, "er": er,
                   "t_mm": t_mm, "freq_ghz": freq_ghz},
    }


def microstrip_width_for_impedance(
    Z0_target: float,
    h_mm: float,
    er: float,
    t_mm: float = 0.035,
) -> dict:
    """
    Ancho de pista microstrip para una Z₀ objetivo.

    Ref [P]: Pozar 4th ed., §3.8, eq. (3.197) inverted.

    Returns:
        dict con W_mm (ancho calculado) y verificación Z0_check.
    """
    if Z0_target <= 0 or h_mm <= 0 or er < 1.0:
        raise ValueError("Parámetros deben ser positivos y er >= 1")

    # Fórmulas de Wheeler inversas [P eq.3.197 inverted]
    A = (Z0_target / 60.0) * math.sqrt((er + 1.0) / 2.0) + \
        ((er - 1.0) / (er + 1.0)) * (0.23 + 0.11 / er)

    B = (377.0 * math.pi) / (2.0 * Z0_target * math.sqrt(er))

    # Solución para W/h < 2
    u_thin = 8.0 * math.exp(A) / (math.exp(2.0 * A) - 2.0)

    # Solución para W/h >= 2
    u_wide = (2.0 / math.pi) * (
        B - 1.0 - math.log(2.0 * B - 1.0)
        + ((er - 1.0) / (2.0 * er))
        * (math.log(B - 1.0) + 0.39 - 0.61 / er)
    )

    # Elegir la solución consistente
    if u_thin < 2.0:
        u = u_thin
    else:
        u = u_wide

    w_mm = u * h_mm

    # Corrección inversa por grosor de cobre
    if t_mm > 0 and t_mm < h_mm:
        dw = t_mm / math.pi * (1.0 + math.log(2.0 * h_mm / t_mm))
        w_mm = max(w_mm - dw, 0.01)

    # Verificación
    check = microstrip_impedance(w_mm, h_mm, er, t_mm)
    return {
        "W_mm": round(w_mm, 4),
        "Z0_check": check["Z0"],
        "error_pct": round(abs(check["Z0"] - Z0_target) / Z0_target * 100, 2),
        "eff_er": check["eff_er"],
    }


def differential_microstrip_impedance(
    w_mm: float,
    s_mm: float,
    h_mm: float,
    er: float,
    t_mm: float = 0.035,
) -> dict:
    """
    Differential impedance Zdiff for edge-coupled microstrip pair.
    Uses single-ended Z0 with coupling reduction (approximation).
    Ref: IPC / Pozar coupled line model (simplified).
    """
    if w_mm <= 0 or s_mm <= 0 or h_mm <= 0:
        raise ValueError("w_mm, s_mm, h_mm must be > 0")
    z_se = microstrip_impedance(w_mm, h_mm, er, t_mm)["Z0"]
    # Coupling factor k increases as spacing decreases
    k = 0.12 / (1.0 + s_mm / h_mm)
    z_odd = z_se * (1.0 - k)
    z_diff = 2.0 * z_odd
    return {
        "Zdiff": round(z_diff, 2),
        "Z0_single": z_se,
        "W_mm": w_mm,
        "S_mm": s_mm,
        "h_mm": h_mm,
        "er": er,
        "coupling_k": round(k, 4),
    }


def usb_diff_pair_dimensions(
    Zdiff_target: float = 90.0,
    h_mm: float = 1.6,
    er: float = 4.4,
    t_mm: float = 0.035,
) -> dict:
    """
    Search trace width W and spacing S for target differential impedance (USB: 90 ohm).
    """
    best = None
    for w in [i * 0.05 for i in range(4, 80)]:
        for s in [i * 0.05 for i in range(2, 60)]:
            r = differential_microstrip_impedance(w, s, h_mm, er, t_mm)
            err = abs(r["Zdiff"] - Zdiff_target)
            if best is None or err < best["error_pct"]:
                best = {
                    "W_mm": round(w, 3),
                    "S_mm": round(s, 3),
                    "Zdiff": r["Zdiff"],
                    "Z0_single": r["Z0_single"],
                    "error_pct": round(err / Zdiff_target * 100, 2),
                    "h_mm": h_mm,
                    "er": er,
                    "target_Zdiff": Zdiff_target,
                }
    return best or {"error": "no solution found"}

def stripline_impedance(
    w_mm: float,
    b_mm: float,
    er: float,
    t_mm: float = 0.035,
) -> dict:
    """
    Impedancia característica Z₀ de línea stripline (centrada).

    Ref [W]: Wheeler, IEEE Trans MTT 1965.
    Ref [P]: Pozar 4th ed., §3.9, eq. (3.198).

    Args:
        w_mm: Ancho de pista (mm).
        b_mm: Separación total entre planos de masa (mm).
        er:   Constante dieléctrica del substrato.
        t_mm: Grosor del cobre (mm).

    Returns:
        dict con Z0 y parámetros derivados.
    """
    if w_mm <= 0 or b_mm <= 0 or er < 1.0:
        raise ValueError("Parámetros deben ser positivos y er >= 1")
    if t_mm >= b_mm:
        raise ValueError("Grosor de cobre t_mm debe ser < separación b_mm")

    # Corrección por grosor [W]
    d = b_mm - t_mm
    if t_mm > 0:
        w_eff = w_mm + (t_mm / math.pi) * \
            (1.0 + math.log(4.0 * math.pi * w_mm / t_mm))
        w_eff = min(w_eff, d * (1.0 - 1.0e-6))
    else:
        w_eff = w_mm

    x = w_eff / b_mm

    if x < 0.05:
        # Narrow trace approximation [W]
        Z0 = (60.0 / math.sqrt(er)) * math.log(4.0 * b_mm / (math.pi * w_eff))
    else:
        # Wide trace (parallel plate region) [P]
        C_eff = (er * 8.854e-12 * w_eff) / (b_mm * 1e-3)  # F/m approximation
        Z0 = (1.0 / (C_eff * 3e8)) if C_eff > 0 else float('inf')
        # Better: Wheeler formula
        Z0 = (30.0 * math.pi / math.sqrt(er)) * (b_mm / (w_eff + 0.441 * b_mm))

    C = 3e11  # mm/s
    phase_vel = C / math.sqrt(er)

    return {
        "Z0": round(Z0, 3),
        "er": er,
        "phase_vel_m_s": round(phase_vel * 1e-3, 0),
        "W_eff_mm": round(w_eff, 4),
        "W_b": round(x, 4),
        "inputs": {"w_mm": w_mm, "b_mm": b_mm, "er": er, "t_mm": t_mm},
    }


# ─── Matching Networks ────────────────────────────────────────────────────────

def matching_network_L(
    z_source: complex,
    z_load:   complex,
    freq_mhz: float,
) -> dict:
    """
    Red L de adaptación de impedancias (dos elementos reactivos).

    Ref [P]: Pozar 4th ed., §5.1, eq. (5.1)-(5.6).

    Adapta Z_source → Z_load. Asume componentes sin pérdidas.
    Puede devolver dos soluciones (shunt primero / serie primero).

    Args:
        z_source: Impedancia de fuente (Ω, compleja).
        z_load:   Impedancia de carga (Ω, compleja).
        freq_mhz: Frecuencia de trabajo (MHz).

    Returns:
        dict con soluciones, valores de L y C, y Q de la red.
    """
    omega = 2.0 * math.pi * freq_mhz * 1e6

    Rs = z_source.real
    Xs = z_source.imag
    Rl = z_load.real
    Xl = z_load.imag

    if Rs <= 0 or Rl <= 0:
        raise ValueError("Las partes reales de Zs y Zl deben ser positivas")

    solutions = []

    # ── Configuración 1: shunt junto a la carga (Rl > Rs caso base) ──
    # [P eq. 5.3]
    R_high = max(Rs, Rl)
    R_low  = min(Rs, Rl)

    if R_high / R_low <= 1.0:
        raise ValueError("Las impedancias son iguales, no se necesita red L")

    Q = math.sqrt(R_high / R_low - 1.0)

    # Dos signos de Q → dos soluciones topológicas
    for sign in (+1, -1):
        Qn = sign * Q

        if Rs < Rl:
            # Elemento serie en el lado de la fuente
            X_series = Qn * Rs
            B_shunt  = Qn / Rl
        else:
            # Elemento shunt en el lado de la fuente
            B_shunt  = Qn / Rs
            X_series = Qn * Rl

        X_series_comp = X_series  # Reactancia del elemento serie
        X_shunt_comp  = -1.0 / B_shunt  # Reactancia del elemento shunt

        def _lc_from_reactance(X, omega, label):
            if abs(X) < 1e-12:
                return {"type": "wire", "value_nH_or_pF": 0, "reactance": 0}
            if X > 0:
                L_nH = X / omega * 1e9
                return {"type": "L", "value_nH": round(L_nH, 4),
                        "reactance_ohm": round(X, 4)}
            else:
                C_pF = -1.0 / (X * omega) * 1e12
                return {"type": "C", "value_pF": round(C_pF, 4),
                        "reactance_ohm": round(X, 4)}

        sol = {
            "Q": round(abs(Qn), 4),
            "series_element": _lc_from_reactance(X_series_comp, omega, "series"),
            "shunt_element":  _lc_from_reactance(X_shunt_comp, omega, "shunt"),
            "topology": ("series-shunt" if Rs < Rl else "shunt-series"),
            "bandwidth_mhz": round(freq_mhz / abs(Qn), 3) if Qn != 0 else float('inf'),
        }
        solutions.append(sol)

    return {
        "freq_mhz": freq_mhz,
        "z_source": {"R": Rs, "X": Xs},
        "z_load":   {"R": Rl, "X": Xl},
        "solutions": solutions,
        "ref": "Pozar §5.1",
    }


def stub_length(
    Z0_line: float,
    Z_load:  complex,
    freq_mhz: float,
    stub_type: str = "short",
) -> dict:
    """
    Longitud de stub para cancelar la parte reactiva de Z_load.

    Ref [P]: Pozar 4th ed., §5.2.

    Args:
        Z0_line:  Impedancia del stub (Ω).
        Z_load:   Impedancia de carga compleja (Ω).
        freq_mhz: Frecuencia (MHz).
        stub_type: "short" (cortocircuito) o "open" (circuito abierto).

    Returns:
        dict con longitud_lambda (fracción de λ) y longitud_mm (para substrate dado).
    """
    omega = 2.0 * math.pi * freq_mhz * 1e6
    B_needed = -Z_load.imag / (Z_load.real**2 + Z_load.imag**2)

    if stub_type == "short":
        # B_stub = -1/(Z0 × tan(βl))  →  βl = arctan(-1/(Z0 × B_needed))
        yl = -1.0 / (Z0_line * B_needed) if abs(B_needed) > 1e-15 else float('inf')
        arg = math.atan(yl)
    else:  # open
        # B_stub = tan(βl)/Z0  →  βl = arctan(Z0 × B_needed)
        arg = math.atan(Z0_line * B_needed)

    # Normalizar a [0, π]
    if arg < 0:
        arg += math.pi

    length_lambda = arg / (2.0 * math.pi)

    return {
        "stub_type": stub_type,
        "length_lambda": round(length_lambda, 5),
        "beta_l_rad": round(arg, 5),
        "B_needed_S": round(B_needed, 8),
        "note": "llength_mm depends on substrate εr and h",
        "ref": "Pozar §5.2",
    }


def electrical_length(
    physical_mm: float,
    er_eff: float,
    freq_mhz: float,
) -> dict:
    """
    Longitud eléctrica (grados) de una línea de longitud física dada.

    Args:
        physical_mm: Longitud física (mm).
        er_eff:     Permitividad efectiva (adim.).
        freq_mhz:   Frecuencia (MHz).

    Returns:
        dict con longitud eléctrica en grados y fracción de lambda.
    """
    c_mm_s = 3e11  # mm/s
    lambda_mm = c_mm_s / (freq_mhz * 1e6 * math.sqrt(er_eff))
    theta_deg = 360.0 * physical_mm / lambda_mm
    theta_frac = physical_mm / lambda_mm
    return {
        "theta_degrees": round(theta_deg, 3),
        "lambda_fraction": round(theta_frac, 5),
        "lambda_mm": round(lambda_mm, 3),
        "freq_mhz": freq_mhz,
    }


# ─── IPC-2221 Trace Width ─────────────────────────────────────────────────────

def trace_width_ipc2221(
    current_a: float,
    copper_oz: float = 1.0,
    temp_rise_c: float = 10.0,
    layer: str = "external",
) -> dict:
    """
    Ancho mínimo de pista según IPC-2221B, Table 6-1 / Chart 6-2.

    Ref [IPC]: IPC-2221B §6.2.

    Ecuación:
        A = (I / (K × ΔT^0.44))^(1/0.725)   [mil²]
        W = A / (t_cu_mils)                   [mils]
        W_mm = W × 0.0254

    Donde:
        K = 0.048 para pistas externas
        K = 0.024 para pistas internas
        t_cu_mils = copper_oz × 1.378  (1oz Cu ≈ 1.378 mils ≈ 35µm)

    Args:
        current_a:   Corriente máxima (A).
        copper_oz:   Peso de cobre en oz (1oz = 35µm).
        temp_rise_c: Máxima elevación de temperatura admisible (°C).
        layer:       "external" o "internal".

    Returns:
        dict con W_mm, A_mils2, resistencia aproximada.
    """
    if current_a <= 0:
        raise ValueError("La corriente debe ser positiva")
    if temp_rise_c <= 0:
        raise ValueError("La elevación de temperatura debe ser positiva")

    K = 0.048 if layer == "external" else 0.024
    t_cu_mils = copper_oz * 1.378  # mil

    # Área de sección transversal [IPC-2221B eq. chart 6-2]
    A_mils2 = (current_a / (K * (temp_rise_c ** 0.44))) ** (1.0 / 0.725)

    # Ancho
    W_mils = A_mils2 / t_cu_mils
    W_mm   = W_mils * 0.0254

    # Resistencia lineal aprox (ρ_Cu = 1.72e-8 Ω·m)
    rho_cu = 1.72e-8  # Ω·m
    A_m2   = A_mils2 * (25.4e-6) ** 2  # mils² → m²
    R_per_m = rho_cu / A_m2 if A_m2 > 0 else float('inf')

    return {
        "W_mm": round(max(W_mm, 0.01), 4),
        "W_mils": round(max(W_mils, 0.4), 3),
        "area_mils2": round(A_mils2, 3),
        "resistance_ohm_per_m": round(R_per_m, 4),
        "voltage_drop_mV_per_A_per_cm": round(R_per_m * 0.01 * 1000, 4),
        "layer": layer,
        "copper_oz": copper_oz,
        "temp_rise_c": temp_rise_c,
        "ref": "IPC-2221B §6.2",
    }


def skin_depth(freq_hz: float, metal: str = "Cu") -> dict:
    """
    Profundidad de penetración (skin depth) δ.

    δ = √(2ρ / (ωμ)) = √(ρ / (π·f·μ))

    Ref [P]: Pozar 4th ed., §1.3.

    Args:
        freq_hz: Frecuencia (Hz).
        metal:   "Cu" (cobre), "Au" (oro), "Al" (aluminio).

    Returns:
        dict con δ_um y frecuencia de transición.
    """
    resistivity = {"Cu": 1.72e-8, "Au": 2.44e-8, "Al": 2.82e-8}
    rho = resistivity.get(metal, 1.72e-8)
    mu  = 4e-7 * math.pi  # μ₀ (no magnético)

    if freq_hz <= 0:
        raise ValueError("La frecuencia debe ser positiva")

    delta_m  = math.sqrt(rho / (math.pi * freq_hz * mu))
    delta_um = delta_m * 1e6

    return {
        "delta_um": round(delta_um, 4),
        "delta_mm": round(delta_m * 1e3, 6),
        "metal": metal,
        "freq_mhz": round(freq_hz * 1e-6, 4),
        "note": f"Cu de 35µm (1oz) es opaco a RF cuando δ << 35µm, "
                f"i.e., f >> {rho / (math.pi * (35e-6)**2 * mu) * 1e-6:.1f} MHz",
        "ref": "Pozar §1.3",
    }


# ─── Utilidades ───────────────────────────────────────────────────────────────

class RFTools:
    """
    Fachada estática para todos los cálculos RF.
    Útil para importar un solo objeto desde otros módulos.
    """
    microstrip_impedance         = staticmethod(microstrip_impedance)
    microstrip_width_for_Z0      = staticmethod(microstrip_width_for_impedance)
    differential_microstrip_impedance = staticmethod(differential_microstrip_impedance)
    usb_diff_pair_dimensions     = staticmethod(usb_diff_pair_dimensions)
    stripline_impedance          = staticmethod(stripline_impedance)
    matching_network_L           = staticmethod(matching_network_L)
    stub_length                  = staticmethod(stub_length)
    electrical_length            = staticmethod(electrical_length)
    trace_width_ipc2221          = staticmethod(trace_width_ipc2221)
    skin_depth                   = staticmethod(skin_depth)


# ─── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== RF Tools Self-test ===\n")

    # Caso de referencia: microstrip 50Ω en FR4
    # FR4: εr ≈ 4.4, h = 1.6mm → W ≈ 3.0mm para Z₀ = 50Ω [Pozar tabla 3.4]
    r = microstrip_impedance(w_mm=3.0, h_mm=1.6, er=4.4, freq_ghz=1.0)
    print(f"Microstrip FR4 (W=3mm, h=1.6mm, εr=4.4):")
    print(f"  Z₀ = {r['Z0']} Ω  (esperado ≈ 50 Ω)")
    print(f"  εeff = {r['eff_er']}")
    print(f"  λ@1GHz = {r['lambda_mm']} mm\n")

    # Inversión: W para 50Ω en FR4
    rw = microstrip_width_for_impedance(Z0_target=50.0, h_mm=1.6, er=4.4)
    print(f"Ancho para Z₀=50Ω en FR4 (h=1.6mm):")
    print(f"  W = {rw['W_mm']} mm  (esperado ≈ 3.0mm)")
    print(f"  Verificación Z₀ = {rw['Z0_check']} Ω  error={rw['error_pct']}%\n")

    # IPC-2221: ancho para 2A externo, 1oz, ΔT=10°C
    tw = trace_width_ipc2221(current_a=2.0, copper_oz=1.0, temp_rise_c=10.0)
    print(f"Ancho pista IPC-2221 para 2A externo 1oz ΔT=10°C:")
    print(f"  W = {tw['W_mm']} mm  (ref ≈ 0.76mm)\n")

    # Skin depth cobre a 1GHz
    sd = skin_depth(freq_hz=1e9, metal="Cu")
    print(f"Skin depth Cu @ 1GHz: δ = {sd['delta_um']} µm  (ref ≈ 2.1 µm)\n")

    print("=== Tests completados ===")
