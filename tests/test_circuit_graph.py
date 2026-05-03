"""
tests/test_circuit_graph.py
===========================
Suite de tests para core/circuit_graph.py — modelo de datos central.

Cubre: CRUD, wires, merge, serialización roundtrip, node helpers,
from_component_dicts, y SimulationRunner.
"""
import json
import math
import sys
import pytest

sys.path.insert(0, '.')

from core.circuit_graph import CircuitGraph, PlacedComponent, Wire, SimulationRunner


# ─── PlacedComponent ────────────────────────────────────────────────────────

class TestPlacedComponent:
    def test_basic_attrs(self):
        c = PlacedComponent(uid="R_0", etype="R", grid_c=0, grid_r=0,
                            orientation="H", value=1000.0, label="R1",
                            n1="A", n2="B")
        assert c.uid == "R_0"
        assert c.etype == "R"
        assert c.value == 1000.0
        assert c.pins == {'1': 'A', '2': 'B'}

    def test_grid_c2_horizontal(self):
        c = PlacedComponent(uid="R_0", etype="R", grid_c=3, grid_r=5,
                            orientation="H", value=100, label="R1",
                            n1="A", n2="B")
        assert c.grid_c2 == 4  # H → c + 1
        assert c.grid_r2 == 5  # H → r unchanged

    def test_grid_c2_vertical(self):
        c = PlacedComponent(uid="C_0", etype="C", grid_c=3, grid_r=5,
                            orientation="V", value=1e-6, label="C1",
                            n1="A", n2="B")
        assert c.grid_c2 == 3  # V → c unchanged
        assert c.grid_r2 == 6  # V → r + 1

    def test_gnd_single_pin(self):
        c = PlacedComponent(uid="GND_0", etype="GND", grid_c=0, grid_r=0,
                            orientation="H", value=0, label="GND",
                            n1="GND", n2="")
        assert c.pins == {'1': 'GND'}
        layout = c.get_pins_layout()
        assert len(layout) == 1

    def test_ic_pins_layout(self):
        c = PlacedComponent(uid="IC_0", etype="IC", grid_c=10, grid_r=10,
                            orientation="V", value=0, label="NE555",
                            n1="", n2="", width=4, height=4,
                            pins={"1": "GND", "2": "TRIG", "3": "OUT", "4": "VCC"})
        layout = c.get_pins_layout()
        assert len(layout) == 4

    def test_to_json_roundtrip(self):
        c = PlacedComponent(uid="L_0", etype="L", grid_c=1, grid_r=2,
                            orientation="V", value=0.01, label="L1 10mH",
                            n1="X", n2="Y")
        d = c.to_json()
        c2 = PlacedComponent(**d)
        assert c2.uid == c.uid
        assert c2.value == c.value
        assert c2.n1 == c.n1


# ─── CircuitGraph CRUD ──────────────────────────────────────────────────────

class TestCircuitGraphCRUD:
    def test_add_and_get(self):
        g = CircuitGraph()
        comp = g.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')
        assert comp.uid == 'R_000'
        assert len(g.components) == 1
        assert g.get('R_000') is comp

    def test_add_multiple(self):
        g = CircuitGraph()
        g.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')
        g.add('C', 2, 0, 'H', 1e-6, 'C1', 'B', 'GND')
        g.add('V', 4, 0, 'H', 5.0, 'V1', 'A', 'GND')
        assert len(g.components) == 3

    def test_remove(self):
        g = CircuitGraph()
        g.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')
        g.add('C', 2, 0, 'H', 1e-6, 'C1', 'B', 'GND')
        g.remove('R_000')
        assert len(g.components) == 1
        assert g.get('R_000') is None

    def test_duplicate(self):
        g = CircuitGraph()
        g.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')
        dup = g.duplicate('R_000', dc=3, dr=2)
        assert dup is not None
        assert dup.grid_c == 3
        assert dup.grid_r == 2
        assert dup.value == 1000
        assert len(g.components) == 2

    def test_clear(self):
        g = CircuitGraph()
        g.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')
        g.add_wire([(0, 0), (1, 0)])
        g.clear()
        assert len(g.components) == 0
        assert len(g.wires) == 0

    def test_get_nonexistent(self):
        g = CircuitGraph()
        assert g.get('XXX') is None


# ─── Wire CRUD ──────────────────────────────────────────────────────────────

class TestWireCRUD:
    def test_add_wire(self):
        g = CircuitGraph()
        w = g.add_wire([(0, 0), (1, 0), (1, 1)])
        assert w.uid == 'W_000'
        assert len(w.path) == 3
        assert len(g.wires) == 1

    def test_remove_wire(self):
        g = CircuitGraph()
        g.add_wire([(0, 0), (1, 0)])
        g.add_wire([(2, 2), (3, 3)])
        g.remove_wire('W_000')
        assert len(g.wires) == 1
        assert g.wires[0].uid == 'W_001'

    def test_get_wire(self):
        g = CircuitGraph()
        g.add_wire([(0, 0), (5, 5)])
        w = g.get_wire('W_000')
        assert w is not None
        assert w.path == [(0, 0), (5, 5)]


# ─── Node Helpers ──────────────────────────────────────────────────────────

class TestNodeHelpers:
    def test_all_nodes(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'OUT')
        g.add('R', 4, 0, 'H', 2200, 'R2', 'OUT', 'GND')
        nodes = g.all_nodes
        # GND is excluded from all_nodes by design
        assert 'VCC' in nodes
        assert 'OUT' in nodes
        assert 'GND' not in nodes

    def test_merge_nodes(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', '0')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', '0')
        g.merge_nodes('GND', '0')
        assert g.components[0].n2 == 'GND'
        assert g.components[1].n2 == 'GND'
        assert g.components[0].pins['2'] == 'GND'

    def test_node_at_grid(self):
        g = CircuitGraph()
        g.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')
        # Pin 1 is at (0, 0) → node A
        assert g.node_at_grid(0, 0) == 'A'
        # Pin 2 is at (1, 0) → node B (horizontal)
        assert g.node_at_grid(1, 0) == 'B'
        # Nothing at (5, 5)
        assert g.node_at_grid(5, 5) is None


# ─── Serialization ──────────────────────────────────────────────────────────

class TestSerialization:
    def test_json_roundtrip_empty(self):
        g = CircuitGraph()
        data = g.to_json()
        g2 = CircuitGraph.from_json(data)
        assert len(g2.components) == 0
        assert len(g2.wires) == 0

    def test_json_roundtrip_full(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'OUT')
        g.add_wire([(0, 0), (2, 0)])
        g.add_wire([(3, 0), (3, 2)])

        data = g.to_json()
        j_str = json.dumps(data)
        g2 = CircuitGraph.from_json(json.loads(j_str))

        assert len(g2.components) == 2
        assert len(g2.wires) == 2
        assert g2.components[0].value == 5.0
        assert g2.components[1].label == 'R1'
        assert g2.wires[0].path == [(0, 0), (2, 0)]
        assert json.dumps(g.to_json()) == json.dumps(g2.to_json())

    def test_json_preserves_counters(self):
        g = CircuitGraph()
        g.add('R', 0, 0, 'H', 100, 'R1', 'A', 'B')
        g.add('C', 2, 0, 'H', 1e-6, 'C1', 'B', 'C')
        g.add_wire([(0, 0), (1, 0)])
        data = g.to_json()
        assert data['_counter'] == 2
        assert data['_wcounter'] == 1

        g2 = CircuitGraph.from_json(data)
        # Next add should not collide UIDs
        r3 = g2.add('R', 4, 0, 'H', 200, 'R3', 'C', 'D')
        assert r3.uid == 'R_002'

    def test_from_component_dicts_basic(self):
        g = CircuitGraph.from_component_dicts([
            {"etype": "V", "value": 5.0, "n1": "VCC", "n2": "GND", "label": "Fuente"},
            {"etype": "R", "value": 1000, "n1": "VCC", "n2": "OUT"},
            {"etype": "R", "value": 2200, "n1": "OUT", "n2": "GND"},
        ])
        assert len(g.components) == 3
        assert g.components[0].label == "Fuente"
        assert g.components[0].value == 5.0
        # Default grid positions: 0*2, 1*2, 2*2
        assert g.components[0].grid_c == 0
        assert g.components[1].grid_c == 2
        assert g.components[2].grid_c == 4

    def test_from_component_dicts_type_alias(self):
        """Accepts 'type' as alias for 'etype'."""
        g = CircuitGraph.from_component_dicts([
            {"type": "C", "value": "1e-6", "n1": "A", "n2": "B"},
        ])
        assert g.components[0].etype == "C"
        assert g.components[0].value == 1e-6

    def test_from_component_dicts_invalid_value(self):
        """Non-numeric values default to 0.0."""
        g = CircuitGraph.from_component_dicts([
            {"etype": "R", "value": "ten thousand ohms", "n1": "A", "n2": "B"},
        ])
        assert g.components[0].value == 0.0

    def test_from_component_dicts_custom_grid(self):
        """Explicit grid positions override auto-layout."""
        g = CircuitGraph.from_component_dicts([
            {"etype": "R", "value": 100, "n1": "A", "n2": "B", "grid_c": 10, "grid_r": 5},
        ])
        assert g.components[0].grid_c == 10
        assert g.components[0].grid_r == 5


# ─── Merge ──────────────────────────────────────────────────────────────────

class TestMerge:
    def test_merge_components(self):
        g1 = CircuitGraph()
        g1.add('R', 0, 0, 'H', 1000, 'R1', 'A', 'B')

        g2 = CircuitGraph()
        g2.add('C', 0, 0, 'H', 1e-6, 'C1', 'B', 'GND')

        g1.merge(g2, offset=(5, 3))
        assert len(g1.components) == 2
        # The merged component should be offset
        merged = g1.components[1]
        assert merged.grid_c == 5
        assert merged.grid_r == 3
        assert merged.etype == 'C'

    def test_merge_wires(self):
        g1 = CircuitGraph()
        g1.add_wire([(0, 0), (1, 0)])

        g2 = CircuitGraph()
        g2.add_wire([(0, 0), (0, 1)])

        g1.merge(g2, offset=(10, 10))
        assert len(g1.wires) == 2
        assert g1.wires[1].path == [(10, 10), (10, 11)]


# ─── MNA Integration ────────────────────────────────────────────────────────

class TestMNAIntegration:
    def test_to_simulator(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'GND')

        sim = g.to_simulator()
        assert sim is not None
        v, _ = sim.step()
        v_vcc = v[sim.get_node('VCC')]
        assert abs(v_vcc - 5.0) < 0.01

    def test_to_simulator_skips_gnd_component(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'GND')
        g.add('GND', 4, 0, 'H', 0, 'GND', 'GND', '')

        # Should not crash — GND etype is skipped
        sim = g.to_simulator()
        v, _ = sim.step()
        assert abs(v[sim.get_node('VCC')] - 5.0) < 0.01


# ─── SimulationRunner ──────────────────────────────────────────────────────

class TestSimulationRunner:
    def test_load_and_step(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'GND')

        runner = SimulationRunner()
        ok = runner.load(g)
        assert ok is True
        assert runner.is_running is True

        runner.step()
        assert runner.sim_time > 0
        assert abs(runner.get_voltage('VCC') - 5.0) < 0.01

    def test_get_voltage_unknown_node(self):
        runner = SimulationRunner()
        assert runner.get_voltage('NONEXISTENT') == 0.0

    def test_pause_resume(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'GND')

        runner = SimulationRunner()
        runner.load(g)
        runner.step()
        t1 = runner.sim_time

        runner.pause()
        runner.step()  # Should not advance
        assert runner.sim_time == t1

        runner.pause()  # Resume
        runner.step()
        assert runner.sim_time > t1

    def test_cycle_dt(self):
        runner = SimulationRunner()
        dt0 = runner.dt
        runner.cycle_dt()
        dt1 = runner.dt
        assert dt0 != dt1

    def test_reset(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 5.0, 'V1', 'VCC', 'GND')
        g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'GND')

        runner = SimulationRunner()
        runner.load(g)
        runner.step()
        runner.step()
        assert runner.sim_time > 0

        runner.reset()
        assert runner.sim_time == 0.0

    def test_estimate_current_resistor(self):
        g = CircuitGraph()
        g.add('V', 0, 0, 'H', 10.0, 'V1', 'VCC', 'GND')
        comp = g.add('R', 2, 0, 'H', 1000, 'R1', 'VCC', 'GND')

        runner = SimulationRunner()
        runner.load(g)
        runner.step()

        i = runner.estimate_current(comp)
        # V=10, R=1000 → I = 10mA
        assert abs(i - 0.01) < 0.001

    def test_load_empty_graph(self):
        g = CircuitGraph()
        runner = SimulationRunner()
        # Empty graph should still "load" without error
        ok = runner.load(g)
        # Depending on the engine, it may or may not succeed
        # but it shouldn't crash
        assert isinstance(ok, bool)
