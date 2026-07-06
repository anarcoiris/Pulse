"""
test_circuit_engine.py
Suite de tests para circuit_engine.py (Refactorizado para pytest)
"""
import math
import sys
import pytest
sys.path.insert(0, '.')
from core.circuit_engine import CircuitSimulator

def test_resistive_divider():
    sim = CircuitSimulator(dt=1e-6)
    sim.add_voltage_source('PSU', 'A', 'GND', 1000.0)
    sim.add_resistor('R1', 'A', 'B', 5000.0)
    sim.add_resistor('R2', 'B', 'GND', 5000.0)
    v, _ = sim.step()
    v_mid = v[sim.get_node('B')]
    assert abs(v_mid - 500.0) < 0.01

@pytest.mark.parametrize("dt_ms, expected_max_err_pct", [(1.0, 5.0), (0.1, 0.5)])
def test_rc_charge_convergence(dt_ms, expected_max_err_pct):
    V_SRC = 5000.0
    R_CHG = 10000.0
    C_BNK = 0.6e-6
    tau = R_CHG * C_BNK  # 6 ms
    V_exact_1tau = V_SRC * (1 - math.exp(-1))  # 3160.6V

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
    assert err < expected_max_err_pct

def test_switch_open_closed():
    # OPEN
    sim3 = CircuitSimulator(dt=1e-4)
    sim3.add_voltage_source('PSU', 'A', 'GND', 5000.0)
    sim3.add_resistor('R_lim', 'A', 'N1', 10000.0)
    sim3.add_capacitor('C', 'N1', 'GND', 0.6e-6)
    sim3.add_switch('SCR', 'N1', 'LOAD', is_closed=False)
    sim3.add_resistor('R_load', 'LOAD', 'GND', 50.0)
    v3, _ = sim3.step()
    v_load_open = v3[sim3.get_node('LOAD')]
    assert abs(v_load_open) < 0.1

    # CLOSED
    sim3b = CircuitSimulator(dt=1e-4)
    sim3b.add_voltage_source('PSU', 'A', 'GND', 5000.0)
    sim3b.add_resistor('R_lim', 'A', 'N1', 10000.0)
    sim3b.add_capacitor('C', 'N1', 'GND', 0.6e-6)
    sim3b.add_switch('SCR', 'N1', 'LOAD', is_closed=False)
    sim3b.add_resistor('R_load', 'LOAD', 'GND', 50.0)
    # Cargar 50 pasos
    for _ in range(50):
        v3b, _ = sim3b.step()
    # Cerrar switch
    sim3b.set_switch('SCR', True)
    for _ in range(3):
        v3b, _ = sim3b.step()
    v_load_closed = v3b[sim3b.get_node('LOAD')]
    assert v_load_closed > 1.0

def test_multi_section_pfn_no_crash():
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
    v4, x4 = sim4.step()
    n_expected = sim4.node_count + sim4.v_sources + sim4.inductors
    assert len(x4) == n_expected

def test_inductor_step_response():
    L_val = 250e-9
    R_val = 50.0
    tau_L = L_val / R_val
    V_rl = 100.0

    dt_rl = 1e-10
    n_rl = int(tau_L / dt_rl)

    sim5 = CircuitSimulator(dt=dt_rl)
    sim5.add_voltage_source('PSU', 'A', 'GND', V_rl)
    sim5.add_resistor('R', 'A', 'B', R_val)
    sim5.add_inductor('L', 'B', 'GND', L_val)
    for _ in range(n_rl):
        v5, x5 = sim5.step()
    i_L_sim = x5[sim5.node_count + sim5.v_sources]
    i_L_exact = (V_rl / R_val) * (1 - math.exp(-1))
    err5 = abs(i_L_sim - i_L_exact) / i_L_exact * 100
    assert err5 < 1.0

def test_double_inductor_current():
    sim6 = CircuitSimulator(dt=1e-9)
    sim6.add_voltage_source('V1', 'A', 'GND', 100.0)
    sim6.add_resistor('R1', 'A', 'B', 50.0)
    sim6.add_inductor('L1', 'B', 'C', 100e-9)
    sim6.add_inductor('L2', 'C', 'GND', 100e-9)
    
    assert 'L1' in sim6.i_prev
    assert 'L2' in sim6.i_prev
    
    v6, x6 = sim6.step()
    i_L1 = x6[sim6.node_count + sim6.v_sources]
    i_L2 = x6[sim6.node_count + sim6.v_sources + 1]
    diff = abs(i_L1 - i_L2)
    assert diff < 1e-6

def test_emp_pfn_charge_and_fire():
    sim7 = CircuitSimulator(dt=100e-6)
    sim7.add_voltage_source('PSU', 'A', 'GND', 5000.0)
    sim7.add_resistor('R_lim', 'A', 'N1', 10000.0)
    sim7.add_capacitor('C_banco', 'N1', 'GND', 0.6e-6)
    sim7.add_switch('SCR', 'N1', 'PFN_IN', False)
    sim7.add_resistor('R_ant', 'PFN_IN', 'GND', 50.0)

    target_v = 5000 * 0.80
    for _ in range(1000):
        v7, _ = sim7.step()
        if v7[sim7.get_node('N1')] >= target_v:
            break

    v_banco_before = v7[sim7.get_node('N1')]
    assert v_banco_before >= target_v * 0.99

    sim7.dt = 1e-9
    sim7.set_switch('SCR', True)
    for _ in range(10):
        v7, _ = sim7.step()
    v_load_fired = v7[sim7.get_node('PFN_IN')]
    assert v_load_fired > 10.0
