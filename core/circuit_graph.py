"""
core/circuit_graph.py
=====================
Modelo de datos central de PulseLab Forge.

Contiene las clases puras (sin dependencias GUI) que representan
un circuito en el editor:

  - PlacedComponent: un componente en la cuadrícula
  - Wire: un cable dibujado por el usuario
  - CircuitGraph: grafo visual + lógico del circuito
  - SimulationRunner: wrapper frame-a-frame del motor MNA

Estas clases son usadas por todos los subsistemas:
  - ui/ (rendering Pygame)
  - mcp_server/ (API MCP para LLMs)
  - bridge/ (KiCad, PCB layout, Gerbers)
  - knowledge/ (RAG, AI review, synthesis)
  - presets/ (circuitos predefinidos)

Historial:
  Extraído de ui/editor.py para eliminar la dependencia transitiva
  de pygame en módulos headless (MCP server, bridge, presets, etc.)
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Set
from collections import deque


# ─── PlacedComponent ─────────────────────────────────────────────────────────

@dataclass
class PlacedComponent:
    """Un componente colocado en la cuadrícula del editor."""
    uid:         str
    etype:       str    # 'R' | 'C' | 'L' | 'V' | 'S' | 'GND'
    grid_c:      int
    grid_r:      int
    orientation: str    # 'H' | 'V'
    value:       float
    label:       str
    n1:          str
    n2:          str
    R_on:        float = 0.01
    R_off:       float = 1e9
    is_closed:   bool  = False
    pins:        Dict[str, str] = field(default_factory=dict)
    width:       int   = 2
    height:      int   = 2
    footprint_id: Optional[str] = None
    symbol_id:    Optional[str] = None
    pkg_type:     Optional[str] = None
    position:     Optional[Dict[str, float]] = None
    rotation:     float = 0.0

    def __post_init__(self):
        # Asegurar que pins esté poblado para componentes de 2 pines
        if self.etype != 'GND' and self.etype not in ('IC', 'MCU'):
            if '1' not in self.pins: self.pins['1'] = self.n1
            if '2' not in self.pins: self.pins['2'] = self.n2
        elif self.etype == 'GND':
            if '1' not in self.pins: self.pins['1'] = 'GND'

    @property
    def grid_c2(self) -> int:
        if self.etype in ('IC', 'MCU'): return self.grid_c + self.width
        return self.grid_c + (1 if self.orientation == 'H' else 0)

    @property
    def grid_r2(self) -> int:
        if self.etype in ('IC', 'MCU'): return self.grid_r + self.height
        return self.grid_r + (1 if self.orientation == 'V' else 0)

    def get_pins_layout(self) -> List[Tuple[int, int, str]]:
        """
        Devuelve una lista de (grid_c, grid_r, pin_id) para cada pin del componente.
        Para R/C/L/V/S usa n1/n2. Para IC/MCU usa el diccionario 'pins'.
        """
        layout = []
        if self.etype in ('IC', 'MCU'):
            # Distribución de pines lateral para ICs
            num_pins = len(self.pins)
            half = num_pins // 2
            pin_ids = sorted(self.pins.keys(), key=lambda x: int(x) if x.isdigit() else x)
            for i, p_id in enumerate(pin_ids):
                if i < half:
                    layout.append((self.grid_c, self.grid_r + i, p_id))
                else:
                    layout.append((self.grid_c + self.width, self.grid_r + (num_pins - 1 - i), p_id))
        else:
            # Componentes estándar (R, C, L, V, S, GND)
            layout.append((self.grid_c, self.grid_r, '1'))
            if self.etype != 'GND':
                layout.append((self.grid_c2, self.grid_r2, '2'))
        return layout

    def to_json(self) -> dict:
        """Serializa el componente a un dict JSON-compatible."""
        return dict(
            uid=self.uid, etype=self.etype,
            grid_c=self.grid_c, grid_r=self.grid_r,
            orientation=self.orientation, value=self.value,
            label=self.label, n1=self.n1, n2=self.n2,
            R_on=self.R_on, R_off=self.R_off, is_closed=self.is_closed,
            pins=self.pins, width=self.width, height=self.height,
            footprint_id=self.footprint_id,
        )


# ─── Wire ─────────────────────────────────────────────────────────────────────

@dataclass
class Wire:
    """
    Cable dibujado por el usuario en la cuadrícula.
    path = lista de puntos de cuadrícula [(gc, gr), ...].
    """
    uid:  str
    path: List[Tuple[int, int]]


# ─── CircuitGraph ─────────────────────────────────────────────────────────────

class CircuitGraph:
    """Representación visual + lógica del circuito."""

    def merge(self, other: "CircuitGraph", offset: Tuple[int, int] = (0, 0)) -> None:
        """Fusiona otro grafo de circuitos en este, con un desplazamiento opcional."""
        ox, oy = offset
        for comp in other.components:
            # Crear una copia con UID único
            new_uid = f"{comp.etype}_{random.getrandbits(16):04x}"
            new_comp = PlacedComponent(
                uid=new_uid,
                etype=comp.etype,
                grid_c=comp.grid_c + ox,
                grid_r=comp.grid_r + oy,
                orientation=comp.orientation,
                value=comp.value,
                label=comp.label,
                n1=comp.n1,
                n2=comp.n2,
                R_on=comp.R_on,
                R_off=comp.R_off,
                is_closed=comp.is_closed,
                pins=comp.pins.copy(),
                width=comp.width,
                height=comp.height,
                footprint_id=comp.footprint_id
            )
            self.components.append(new_comp)
            self._counter += 1

        for wire in other.wires:
            new_path = [(gc + ox, gr + oy) for gc, gr in wire.path]
            new_wire = Wire(f"W_{random.getrandbits(16):04x}", new_path)
            self.wires.append(new_wire)

    def __init__(self):
        self.components: List[PlacedComponent] = []
        self.wires:      List[Wire]            = []
        self._counter:   int = 0
        self._wcounter:  int = 0

    # ── Component CRUD ────────────────────────────────────────

    def add(self, etype, grid_c, grid_r, orientation, value, label,
            n1="", n2="", pkg_type=None, **kwargs) -> PlacedComponent:
        uid  = f"{etype}_{self._counter:03d}"
        self._counter += 1
        comp = PlacedComponent(uid=uid, etype=etype, grid_c=grid_c,
                               grid_r=grid_r, orientation=orientation,
                               value=value, label=label, n1=n1, n2=n2,
                               pkg_type=pkg_type, **kwargs)
        self.components.append(comp)
        return comp

    def duplicate(self, uid: str, dc: int = 1, dr: int = 1) -> Optional[PlacedComponent]:
        src = self.get(uid)
        if src is None:
            return None
        return self.add(src.etype, src.grid_c + dc, src.grid_r + dr,
                        src.orientation, src.value, src.label,
                        src.n1, src.n2, R_on=src.R_on, R_off=src.R_off,
                        is_closed=src.is_closed)

    def remove(self, uid: str) -> None:
        self.components = [c for c in self.components if c.uid != uid]
        self.wires      = [w for w in self.wires      if w.uid != uid]

    def get(self, uid: str) -> Optional[PlacedComponent]:
        return next((c for c in self.components if c.uid == uid), None)

    def clear(self) -> None:
        self.components.clear()
        self.wires.clear()
        self._counter  = 0
        self._wcounter = 0

    # ── Wire CRUD ─────────────────────────────────────────────

    def add_wire(self, path: List[Tuple[int, int]]) -> Wire:
        uid = f"W_{self._wcounter:03d}"
        self._wcounter += 1
        w = Wire(uid=uid, path=list(path))
        self.wires.append(w)
        return w

    def remove_wire(self, uid: str) -> None:
        self.wires = [w for w in self.wires if w.uid != uid]

    def get_wire(self, uid: str) -> Optional[Wire]:
        return next((w for w in self.wires if w.uid == uid), None)

    # ── Node helpers ──────────────────────────────────────────

    def merge_nodes(self, name_keep: str, name_drop: str) -> None:
        if name_keep == name_drop:
            return
        for c in self.components:
            for pin_id, net in c.pins.items():
                if net == name_drop:
                    c.pins[pin_id] = name_keep
                    # Mantener n1/n2 sincronizados para compatibilidad legacy si es necesario
                    if pin_id == '1': c.n1 = name_keep
                    if pin_id == '2': c.n2 = name_keep

    def node_at_grid(self, gc: int, gr: int, visited_wires: Set[str] = None) -> Optional[str]:
        if visited_wires is None: visited_wires = set()
        
        # 1. Check components terminals
        for c in self.components:
            for p_gc, p_gr, p_id in c.get_pins_layout():
                if p_gc == gc and p_gr == gr:
                    return c.pins.get(p_id, "")
        
        # 2. Check wires
        for w in self.wires:
            if w.uid in visited_wires: continue
            if (gc, gr) in w.path:
                visited_wires.add(w.uid)
                # Check endpoints of this wire
                n1 = self.node_at_grid(*w.path[0], visited_wires)
                if n1: return n1
                n2 = self.node_at_grid(*w.path[-1], visited_wires)
                if n2: return n2
                # Fallback to auto-name based on wire start
                return f"N_{w.path[0][0]}_{w.path[0][1]}"
        return None

    @property
    def all_nodes(self) -> List[str]:
        nodes = set()
        for c in self.components:
            for net in c.pins.values():
                if net:
                    nodes.add(net)
        return sorted(nodes - {'GND', ''})

    # ── MNA integration ───────────────────────────────────────

    def to_simulator(self):
        from core.circuit_engine import CircuitSimulator
        sim = CircuitSimulator(dt=1e-3)
        for c in self.components:
            if c.etype in ('GND', 'IC', 'MCU'):
                continue
            n1, n2 = c.n1, c.n2
            try:
                if   c.etype == 'R': sim.add_resistor(c.uid, n1, n2, c.value)
                elif c.etype == 'C': sim.add_capacitor(c.uid, n1, n2, c.value)
                elif c.etype == 'L': sim.add_inductor(c.uid, n1, n2, c.value)
                elif c.etype == 'V': sim.add_voltage_source(c.uid, n1, n2, c.value)
                elif c.etype == 'S': sim.add_switch(c.uid, n1, n2,
                                                    is_closed=c.is_closed,
                                                    R_on=c.R_on, R_off=c.R_off)
            except ValueError as e:
                print(f"[CircuitGraph] Skip {c.uid}: {e}")
        return sim

    # ── Serialization ─────────────────────────────────────────

    def to_json(self) -> dict:
        return {
            'version':   '1.2',
            '_counter':  self._counter,
            '_wcounter': self._wcounter,
            'components': [c.to_json() for c in self.components],
            'wires': [
                {'uid': w.uid, 'path': w.path}
                for w in self.wires
            ],
        }

    @classmethod
    def from_json(cls, data: dict) -> 'CircuitGraph':
        g = cls()
        for cd in data.get('components', []):
            g.components.append(PlacedComponent(**cd))
        for wd in data.get('wires', []):
            g.wires.append(Wire(uid=wd['uid'],
                                path=[tuple(p) for p in wd['path']]))
        g._counter  = data.get('_counter',  len(g.components))
        g._wcounter = data.get('_wcounter', len(g.wires))
        return g

    @classmethod
    def from_component_dicts(cls, components: list[dict]) -> 'CircuitGraph':
        """
        Construye un CircuitGraph desde una lista de dicts LLM-friendly.

        Cada dict puede tener las keys:
          - etype / type: Tipo ("R", "C", "L", "V", "S", "GND")
          - value:  Valor numérico (Ω, F, H, V)
          - n1:     Nodo terminal 1 (string)
          - n2:     Nodo terminal 2 (string)
          - label:  Etiqueta descriptiva (opcional)
          - grid_c, grid_r: Posición en cuadrícula (auto-asignada si omitida)

        Ejemplo::

            CircuitGraph.from_component_dicts([
                {"etype": "V", "value": 5.0, "n1": "VCC", "n2": "GND", "label": "Fuente 5V"},
                {"etype": "R", "value": 1000, "n1": "VCC", "n2": "OUT", "label": "R1 1kΩ"},
            ])
        """
        g = cls()
        for i, c in enumerate(components):
            # Conversión segura de valor (por si la IA devuelve texto)
            val_raw = c.get("value", 0)
            try:
                val_f = float(val_raw)
            except (ValueError, TypeError):
                val_f = val_raw

            g.add(
                etype       = c.get("etype", c.get("type", "R")),
                grid_c      = c.get("grid_c", i * 2),
                grid_r      = c.get("grid_r", 0),
                orientation = c.get("orientation", "H"),
                value       = val_f,
                label       = c.get("label", f"{c.get('etype', c.get('type', '?'))}{i+1}"),
                n1          = c.get("n1", f"N{i}"),
                n2          = c.get("n2", f"N{i+1}"),
                pins        = (c.get("pins") or {}).copy(),
                symbol_id   = c.get("symbol", ""),
                footprint_id= c.get("footprint", ""),
                pkg_type    = c.get("pkg_type", None),
                position    = c.get("position", None),
                rotation    = c.get("rotation", 0.0)
            )
        g.apply_design_rules()
        return g

    def apply_design_rules(self) -> None:
        """
        Aplica reglas de diseño avanzadas (desacoplo para ICs/MCUs) directamente
        sobre el grafo, asegurando que todos los componentes suplementarios 
        existan en el Single Source of Truth (SSOT).
        """
        existing_labels = {c.label for c in self.components}
        power_net_candidates = ('3V3', 'VCC33', 'VCC', 'VBUS', '5V', '3.3V', '3.3V_ESP', '3.3V_FLIPPER', '5V_USB', '+5V', '+3V3', 'VDD', 'V_IN')

        for c in list(self.components):
            if c.etype in ('IC', 'MCU'):
                comp_ref = c.label or c.uid
                power_nets = [n for n in getattr(c, 'pins', {}).values() if n in power_net_candidates]
                if power_nets:
                    p_net = power_nets[0]
                    cap_h_label = f"C_{comp_ref}_H"
                    cap_l_label = f"C_{comp_ref}_L"
                    if cap_h_label not in existing_labels:
                        self.add(
                            etype='C',
                            grid_c=c.grid_c + c.width + 1,
                            grid_r=c.grid_r,
                            orientation='V',
                            value='10uF',
                            label=cap_h_label,
                            n1=p_net,
                            n2='GND',
                        )
                        existing_labels.add(cap_h_label)
                    if cap_l_label not in existing_labels:
                        self.add(
                            etype='C',
                            grid_c=c.grid_c + c.width + 1,
                            grid_r=c.grid_r + 2,
                            orientation='V',
                            value='100nF',
                            label=cap_l_label,
                            n1=p_net,
                            n2='GND',
                        )
                        existing_labels.add(cap_l_label)



# ─── SimulationRunner ─────────────────────────────────────────────────────────

_DT_OPTIONS = [1e-3, 1e-4, 1e-5, 1e-6, 1e-8]
_DT_LABELS  = ['1 ms', '100 µs', '10 µs', '1 µs', '10 ns']


class SimulationRunner:
    """Ejecuta el motor MNA frame-a-frame de forma genérica."""

    STEPS_PER_FRAME = 1

    def __init__(self):
        self.sim        = None
        self.is_running = False
        self.is_paused  = False
        self.sim_time   = 0.0
        self.error_msg  = ''
        self.history:   Dict[str, deque] = {}
        self._dt_idx    = 0

    @property
    def dt(self) -> float:      return _DT_OPTIONS[self._dt_idx]

    @property
    def dt_label(self) -> str:  return _DT_LABELS[self._dt_idx]

    def cycle_dt(self) -> None:
        self._dt_idx = (self._dt_idx + 1) % len(_DT_OPTIONS)
        if self.sim: self.sim.set_dt(self.dt)

    def load(self, graph: CircuitGraph) -> bool:
        self.error_msg = ''
        try:
            self.sim = graph.to_simulator()
            self.sim.set_dt(self.dt)
        except Exception as e:
            self.error_msg  = str(e)
            self.sim        = None
            self.is_running = False
            return False
        self.history = {n: deque(maxlen=600) for n in self.sim.nodes}
        self.history['GND'] = deque(maxlen=600)
        self.sim_time   = 0.0
        self.is_running = True
        self.is_paused  = False
        return True

    def step(self) -> None:
        if not self.is_running or self.is_paused or self.sim is None:
            return
        for _ in range(self.STEPS_PER_FRAME):
            try:
                v, _ = self.sim.step()
            except Exception as e:
                self.error_msg  = str(e)
                self.is_running = False
                return
            for name, idx in self.sim.nodes.items():
                if name in self.history:
                    self.history[name].append(float(v[idx]))
            if 'GND' in self.history:
                self.history['GND'].append(0.0)
            self.sim_time += self.dt

    def pause(self) -> None:    self.is_paused = not self.is_paused

    def reset(self) -> None:
        if self.sim: self.sim.reset_state()
        for q in self.history.values(): q.clear()
        self.sim_time = 0.0

    def get_voltage(self, node: str) -> float:
        q = self.history.get(node)
        return float(q[-1]) if q else 0.0

    def estimate_current(self, comp: PlacedComponent) -> float:
        v1 = self.get_voltage(comp.n1)
        v2 = self.get_voltage(comp.n2)
        vd = v1 - v2
        if   comp.etype == 'R': return vd / max(comp.value, 1.0)
        elif comp.etype == 'S': return vd / (comp.R_on if comp.is_closed else comp.R_off)
        elif comp.etype == 'C': return vd * max(comp.value, 1e-12) * 1e4
        elif comp.etype == 'L': return vd / max(comp.value * 2e3, 1e-3)
        return 0.0

    def set_switch(self, uid: str, closed: bool) -> None:
        if self.sim:
            try: self.sim.set_switch(uid, closed)
            except Exception: pass
