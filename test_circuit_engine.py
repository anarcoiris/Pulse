"""
test_circuit_engine.py
Suite de tests para circuit_engine.py
"""
import sys
import math
import numpy as np
sys.path.insert(0, '.')
from circuit_engine import CircuitSimulator

PASS = "[PASS]"
FAIL = "[FAIL]"

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"{status} {label}" + (f"  ({detail})" if detail else ""))
    return condition

all_pass = True

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Divisor de tension resistivo (resultado exacto, no dependiente de dt)
# ─────────────────────────────────────────────────────────────────────────────
sim = CircuitSimulator(dt=1e-6)
sim.add_voltage_source('PSU', 'A', 'GND', 1000.0)
sim.add_resistor('R1', 'A', 'B', 5000.0)
sim.add_resistor('R2', 'B', 'GND', 5000.0)
v, _ = sim.step()
v_mid = v[sim.get_node('B')]
all_pass &= check("Divisor tension R-R", abs(v_mid - 500.0) < 0.01, f"V_B={v_mid:.3f}V")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: Carga RC - convergencia de Backward Euler
# tau = R*C = 10000 * 0.6e-6 = 6ms
# Con dt pequenio, error < 1%  |  Con dt grande (1ms), error ~4.5% -> esperado
# ─────────────────────────────────────────────────────────────────────────────
V_SRC = 5000.0
R_CHG = 10000.0
C_BNK = 0.6e-6
tau = R_CHG * C_BNK  # 6 ms

V_exact_1tau = V_SRC * (1 - math.exp(-1))  # 3160.6V

for dt_ms, expected_max_err_pct in [(1.0, 5.0), (0.1, 0.5)]:
    dt = dt_ms * 1e-3
    n = int(tau / dt)
    s = CircuitSimulator(dt=dt)
    s.add_voltage_source('PSU', 'A', 'GND', V_SRC)
    s.add_resistor('R', 'A', 'B', R_CHG)
    s.add_capacitor('C', 'B', 'GND', C_BNK)
    for _ in range(n):
        v_rc, _ = s.step()
    v_sim = v_rc[s.get_node('B')]
    err = abs(v_sim - V_exact_1tau) / V_exact_1tau * 100
    all_pass &= check(
        f"RC carga Backward Euler (dt={dt_ms}ms, err<{expected_max_err_pct}%)",
        err < expected_max_err_pct,
        f"V_sim={v_sim:.1f} V_exact={V_exact_1tau:.1f} err={err:.2f}%"
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Interruptor abierto / cerrado
# ─────────────────────────────────────────────────────────────────────────────
sim3 = CircuitSimulator(dt=1e-4)
sim3.add_voltage_source('PSU', 'A', 'GND', 5000.0)
sim3.add_resistor('R_lim', 'A', 'N1', 10000.0)
sim3.add_capacitor('C', 'N1', 'GND', 0.6e-6)
sim3.add_switch('SCR', 'N1', 'LOAD', is_closed=False)
sim3.add_resistor('R_load', 'LOAD', 'GND', 50.0)
v3, _ = sim3.step()
v_load_open = v3[sim3.get_node('LOAD')]
all_pass &= check("Switch OPEN: V_LOAD ~0", abs(v_load_open) < 0.1, f"V_LOAD={v_load_open:.4f}V")

sim3.set_switch('SCR', True)
# Cargar un poco el capacitor primero (sin SCR) luego disparar
sim3.set_switch('SCR', False)
sim3b = CircuitSimulator(dt=1e-4)
sim3b.add_voltage_source('PSU', 'A', 'GND', 5000.0)
sim3b.add_resistor('R_lim', 'A', 'N1', 10000.0)
sim3b.add_capacitor('C', 'N1', 'GND', 0.6e-6)
sim3b.add_switch('SCR', 'N1', 'LOAD', is_closed=False)
sim3b.add_resistor('R_load', 'LOAD', 'GND', 50.0)
# Cargar 50 pasos
for _ in range(50):
    v3b, _ = sim3b.step()
v_n1_charged = v3b[sim3b.get_node('N1')]
# Cerrar switch
sim3b.set_switch('SCR', True)
for _ in range(3):
    v3b, _ = sim3b.step()
v_load_closed = v3b[sim3b.get_node('LOAD')]
all_pass &= check("Switch CLOSED: V_LOAD propagado", v_load_closed > 1.0, f"V_LOAD={v_load_closed:.3f}V")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: PFN multi-sección - no debe crashear
# ─────────────────────────────────────────────────────────────────────────────
sim4 = CircuitSimulator(dt=1e-8)
sim4.add_voltage_source('PSU', 'A', 'GND', 5000.0)
sim4.add_resistor('R_lim', 'A', 'N1', 10000.0)
sim4.add_capacitor('C_banco', 'N1', 'GND', 0.6e-6)
sim4.add_switch('SCR', 'N1', 'N2', False)
sim4.add_inductor('L1', 'N2', 'N3', 125e-9)
sim4.add_capacitor('Ck1', 'N3', 'GND', 0.1e-6)
sim4.add_inductor('L2', 'N3', 'N4', 125e-9)
sim4.add_capacitor('Ck2', 'N4', 'GND', 0.1e-6)
sim4.add_resistor('R_load', 'N4', 'GND', 50.0)
try:
    v4, x4 = sim4.step()
    n_expected = sim4.node_count + sim4.v_sources + sim4.inductors
    all_pass &= check("PFN multi-LC sin crash", len(x4) == n_expected,
                      f"x.shape={len(x4)} expected={n_expected}")
except Exception as e:
    all_pass &= check("PFN multi-LC sin crash", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Inductor bloquea la corriente inicialmente
# RL con escalon: i(0) = 0, i(inf) = V/R = 100/50 = 2A
# tau_L = L/R = 250e-9 / 50 = 5ns
# Con dt=1ns en t=5ns, i deberia ~0.63*2 = 1.26A
# ─────────────────────────────────────────────────────────────────────────────
L_val = 250e-9
R_val = 50.0
tau_L = L_val / R_val   # 5 ns
V_rl = 100.0

dt_rl = 1e-10  # 0.1 ns
n_rl = int(tau_L / dt_rl)  # 50 pasos para llegar a 1 tau

sim5 = CircuitSimulator(dt=dt_rl)
sim5.add_voltage_source('PSU', 'A', 'GND', V_rl)
sim5.add_resistor('R', 'A', 'B', R_val)
sim5.add_inductor('L', 'B', 'GND', L_val)
for _ in range(n_rl):
    v5, x5 = sim5.step()
i_L_sim = x5[sim5.node_count + sim5.v_sources]  # Corriente a través del inductor
i_L_exact = (V_rl / R_val) * (1 - math.exp(-1))  # 0.632 * 2 = 1.264A
err5 = abs(i_L_sim - i_L_exact) / i_L_exact * 100
all_pass &= check(
    "Inductor RL paso escalon (err<1% a 0.1ns)",
    err5 < 1.0,
    f"i_sim={i_L_sim:.4f}A  i_exact={i_L_exact:.4f}A  err={err5:.2f}%"
)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Bug potencial - i_prev con el indice correcto de inductor
# Si hay 2 inductores, el segundo debe leer x[node_count + v_sources + 1]
# ─────────────────────────────────────────────────────────────────────────────
sim6 = CircuitSimulator(dt=1e-9)
sim6.add_voltage_source('V1', 'A', 'GND', 100.0)
sim6.add_resistor('R1', 'A', 'B', 50.0)
sim6.add_inductor('L1', 'B', 'C', 100e-9)
sim6.add_inductor('L2', 'C', 'GND', 100e-9)
# Verificar que el mapeo de estado de i_prev sea correcto
expected_L1_key = 'L1'
expected_L2_key = 'L2'
all_pass &= check(
    "Doble inductor - i_prev keys existen",
    'L1' in sim6.i_prev and 'L2' in sim6.i_prev,
    f"keys={list(sim6.i_prev.keys())}"
)
v6, x6 = sim6.step()
i_L1 = x6[sim6.node_count + sim6.v_sources]       # Inductor #1
i_L2 = x6[sim6.node_count + sim6.v_sources + 1]   # Inductor #2
# En serie, ambos deben transportar la misma corriente
diff = abs(i_L1 - i_L2)
all_pass &= check(
    "Doble inductor en serie - misma corriente",
    diff < 1e-6,
    f"i_L1={i_L1:.6f}A  i_L2={i_L2:.6f}A  diff={diff:.2e}A"
)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: Compatibilidad con el flujo del proyecto (EMP 5kV / PFN 50Ω)
# Cargamos hasta 80% de 5kV = 4000V, cerramos SCR, verificamos que el
# nodo de carga recibe tension en nanosegundos
# ─────────────────────────────────────────────────────────────────────────────
# Fase 1: carga con pasos de 100us
sim7 = CircuitSimulator(dt=100e-6)
sim7.add_voltage_source('PSU', 'A', 'GND', 5000.0)
sim7.add_resistor('R_lim', 'A', 'N1', 10000.0)
sim7.add_capacitor('C_banco', 'N1', 'GND', 0.6e-6)
sim7.add_switch('SCR', 'N1', 'PFN_IN', False)
sim7.add_resistor('R_ant', 'PFN_IN', 'GND', 50.0)

# Carga hasta ~80%
target_v = 5000 * 0.80
for _ in range(1000):
    v7, _ = sim7.step()
    if v7[sim7.get_node('N1')] >= target_v:
        break

v_banco_before = v7[sim7.get_node('N1')]
all_pass &= check(
    "EMP: Banco cargado al 80% (4000V)",
    v_banco_before >= target_v * 0.99,
    f"V_banco={v_banco_before:.0f}V"
)

# Fase 2: disparar (SCR cerrar, dt pequenio)
sim7.dt = 1e-9
sim7.set_switch('SCR', True)
for _ in range(10):
    v7, _ = sim7.step()
v_load_fired = v7[sim7.get_node('PFN_IN')]
all_pass &= check(
    "EMP: Carga propagada a carga tras disparo",
    v_load_fired > 10.0,
    f"V_carga={v_load_fired:.1f}V"
)

# ─────────────────────────────────────────────────────────────────────────────
# Resumen
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 50)
if all_pass:
    print("TODOS LOS TESTS PASADOS")
else:
    print("ALGUNOS TESTS FALLARON - revisar circuit_engine.py")
print("=" * 50)
