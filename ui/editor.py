"""
ui/editor.py  v3
================
Correcciones y mejoras:
  - BUG FIX: arrastrar componentes ya NO resetea n1/n2 a "N_gc_gr"
  - BUG FIX: zoom via rueda del raton ahora funciona (tambien botones 4/5,
             y teclas = / - / F para fit)
  - Seleccion por recuadro (SELECT + arrastrar zona vacia)
  - fit_to_screen(): F key o boton
  - Ctrl+D: duplicar componente seleccionado
  - Multi-seleccion: DEL borra todo lo seleccionado
  - Tooltip de nodo al pasar el raton sobre un terminal
"""

import math
import json
import random
from dataclasses import dataclass, field
from typing      import Optional, Dict, List, Tuple, Set
from collections import deque

import pygame

from ui.theme import (
    CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H, GRID_SIZE, GRID_COLS, GRID_ROWS,
    BG, GRID_COL, ACCENT, ACCENT2, WARN, DANGER, SAFE, DIM, WHITE,
    PANEL_BG, PANEL_BORDER, SELECT_COL, COMP_COLORS,
    draw_text, lerp_color,
)

WIRE_COL   = (100, 140, 200)
RECT_SEL_C = (  0, 160, 255)   # colour for selection rectangle


# ─── PlacedComponent ─────────────────────────────────────────────────────────

@dataclass
class PlacedComponent:
    """Un componente colocado en la cuadricula del editor."""
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
            # Distribución de pines:
            # Izquierda (1 a N/2), Derecha (N/2+1 a N)
            num_pins = len(self.pins)
            half = num_pins // 2
            # Los pines se asocian por ID de pin (str)
            pin_ids = sorted(self.pins.keys(), key=lambda x: int(x) if x.isdigit() else x)
            for i, p_id in enumerate(pin_ids):
                if i < half:
                    # Lado izquierdo (hacia abajo)
                    layout.append((self.grid_c, self.grid_r + i, p_id))
                else:
                    # Lado derecho (hacia arriba o igualando)
                    layout.append((self.grid_c + self.width, self.grid_r + (num_pins - 1 - i), p_id))
        elif self.etype == 'GND':
            layout.append((self.grid_c, self.grid_r, '1'))
        else:
            layout.append((self.grid_c, self.grid_r, '1'))
            layout.append((self.grid_c2, self.grid_r2, '2'))
        return layout


# ─── Wire ─────────────────────────────────────────────────────────────────────

@dataclass
class Wire:
    """
    Cable dibujado por el usuario en la cuadricula.
    path = lista de puntos de cuadricula [(gc, gr), ...].
    """
    uid:  str
    path: List[Tuple[int, int]]


# ─── CircuitGraph ─────────────────────────────────────────────────────────────

class CircuitGraph:
    """Representacion visual + logica del circuito."""

    def __init__(self):
        self.components: List[PlacedComponent] = []
        self.wires:      List[Wire]            = []
        self._counter:   int = 0
        self._wcounter:  int = 0

    # ── Component CRUD ────────────────────────────────────────

    def add(self, etype, grid_c, grid_r, orientation, value, label,
            n1="", n2="", **kwargs) -> PlacedComponent:
        uid  = f"{etype}_{self._counter:03d}"
        self._counter += 1
        comp = PlacedComponent(uid=uid, etype=etype, grid_c=grid_c,
                               grid_r=grid_r, orientation=orientation,
                               value=value, label=label, n1=n1, n2=n2,
                               **kwargs)
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
            if c.n1 == name_drop: c.n1 = name_keep
            if c.n2 == name_drop: c.n2 = name_keep
            for pin_id, net in c.pins.items():
                if net == name_drop: c.pins[pin_id] = name_keep

    def node_at_grid(self, gc: int, gr: int, visited_wires: Set[str] = None) -> Optional[str]:
        if visited_wires is None: visited_wires = set()
        
        # 1. Check components terminals
        for c in self.components:
            for p_gc, p_gr, p_id in c.get_pins_layout():
                if p_gc == gc and p_gr == gr:
                    if c.etype == 'GND': return 'GND'
                    if c.etype in ('IC', 'MCU'):
                        return c.pins.get(p_id, "")
                    if p_id == '1': return c.n1
                    return c.n2
        
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
            if c.etype != 'GND':
                nodes.add(c.n1)
                nodes.add(c.n2)
                for net in c.pins.values():
                    nodes.add(net)
        return sorted(nodes - {'GND', ''})

    # ── MNA integration ───────────────────────────────────────

    def to_simulator(self):
        from circuit_engine import CircuitSimulator
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
            'components': [
                dict(uid=c.uid, etype=c.etype,
                     grid_c=c.grid_c, grid_r=c.grid_r,
                     orientation=c.orientation, value=c.value,
                     label=c.label, n1=c.n1, n2=c.n2,
                     R_on=c.R_on, R_off=c.R_off, is_closed=c.is_closed,
                     pins=c.pins, width=c.width, height=c.height,
                     footprint_id=c.footprint_id)
                for c in self.components
            ],
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


# ─── SimulationRunner ─────────────────────────────────────────────────────────

_DT_OPTIONS = [1e-3, 1e-4, 1e-5, 1e-6, 1e-8]
_DT_LABELS  = ['1 ms', '100 µs', '10 µs', '1 µs', '10 ns']


class SimulationRunner:
    """Ejecuta el motor MNA frame-a-frame de forma generica."""

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


# ─── Current particle system ──────────────────────────────────────────────────

@dataclass
class _Particle:
    comp_uid: str
    progress: float   # 0.0 = at t1 → 1.0 = at t2
    life:     float   # 1.0 opaque, 0.0 dead
    speed:    float   # progress units/sec
    forward:  bool    # True = n1→n2


class CurrentParticleSystem:
    MAX_PARTICLES = 200
    THRESHOLD     = 0.01

    def __init__(self):
        self._particles: List[_Particle] = []
        self._accum: Dict[str, float]    = {}

    def update(self, dt: float, graph: CircuitGraph, runner: SimulationRunner) -> None:
        alive = []
        for p in self._particles:
            p.progress += p.speed * dt
            p.life     -= dt * 0.8
            if p.progress < 1.0 and p.life > 0:
                alive.append(p)
        self._particles = alive

        if not runner.is_running or runner.is_paused:
            self._accum.clear()
            return

        for comp in graph.components:
            if comp.etype == 'GND':
                continue
            I = runner.estimate_current(comp)
            if abs(I) < self.THRESHOLD:
                continue
            rate = min(math.sqrt(abs(I)) * 0.8, 4.0)
            key  = comp.uid
            self._accum[key] = self._accum.get(key, 0.0) + rate * dt
            while (self._accum[key] >= 1.0 and
                   len(self._particles) < self.MAX_PARTICLES):
                self._accum[key] -= 1.0
                spd = 0.4 + min(math.log10(abs(I) + 1) * 0.6, 2.0)
                self._particles.append(_Particle(
                    comp_uid=comp.uid, progress=0.0, life=1.0,
                    speed=spd, forward=(I >= 0),
                ))

    def draw(self, surf: pygame.Surface, canvas: 'EditorCanvas') -> None:
        for p in self._particles:
            comp = canvas.graph.get(p.comp_uid)
            if comp is None:
                continue
            t1 = canvas.comp_t1px(comp)
            t2 = canvas.comp_t2px(comp)
            if not p.forward:
                t1, t2 = t2, t1
            prog = max(0.0, min(1.0, p.progress))
            px   = int(t1[0] + (t2[0] - t1[0]) * prog)
            py   = int(t1[1] + (t2[1] - t1[1]) * prog)
            r    = max(2, int(p.life * 5))
            col  = (lerp_color(ACCENT,  WHITE, p.life * 0.3) if p.forward
                    else lerp_color(WARN, WHITE, p.life * 0.3))
            col_c = tuple(max(0, min(255, int(c * p.life))) for c in col)
            pygame.draw.circle(surf, col_c, (px, py), r)


# ─── EditorCanvas ─────────────────────────────────────────────────────────────

class EditorCanvas:
    """
    Canvas interactivo.

    Controles:
        Rueda raton       → zoom centrado en cursor
        Botones 4/5       → zoom (ratones sin rueda)
        = / -             → zoom +10% / -10%
        F                 → fit-to-screen
        Boton central     → pan
        SELECT + arrastre → seleccion por recuadro
        R                 → rotar orientacion
        DEL               → borrar seleccionados
        Ctrl+D            → duplicar componente
        ESC               → deseleccionar / cancelar wire
    """

    ZOOM_MIN  = 0.20
    ZOOM_MAX  = 6.0
    ZOOM_STEP = 1.12   # factor por clic de rueda

    def __init__(self, rect: pygame.Rect, graph: CircuitGraph):
        self.rect  = rect
        self.graph = graph

        # Zoom / Pan
        self.zoom:   float = 1.0
        self.pan_px: float = 0.0
        self.pan_py: float = 0.0
        self._panning     = False
        self._pan_mouse:  Tuple[int, int]     = (0, 0)
        self._pan_origin: Tuple[float, float] = (0.0, 0.0)

        # Tool / selection
        self.active_tool:  str           = 'SELECT'
        self.place_orient: str           = 'H'
        self.selected_uid: Optional[str] = None
        self.selected_uids: Set[str]     = set()  # multi-select
        self._sel_wire_uid: Optional[str] = None

        # Hover
        self._hover_gc: Optional[int] = None
        self._hover_gr: Optional[int] = None

        # Drag-move (single component)
        self._drag_uid: Optional[str]       = None
        self._drag_off: Tuple[int, int]     = (0, 0)
        self._drag_orig_positions: Dict[str, Tuple[int,int]] = {}

        # Rect selection
        self._rect_sel:  bool           = False
        self._rect_p1:   Tuple[int,int] = (0, 0)
        self._rect_p2:   Tuple[int,int] = (0, 0)

        # Particles & BG
        self.particles = CurrentParticleSystem()
        self.bg_dots   = [(random.randint(0, 2000), random.randint(0, 2000)) 
                          for _ in range(120)]
        self.bg_phase  = 0.0
        
        self.search_term: str = ""

    # ── Coordinate helpers ────────────────────────────────────

    def _g2p(self, gc: float, gr: float) -> Tuple[int, int]:
        gs = GRID_SIZE * self.zoom
        return (int(CANVAS_X + gc * gs + self.pan_px),
                int(CANVAS_Y + gr * gs + self.pan_py))

    def _p2g(self, px: int, py: int) -> Tuple[int, int]:
        gs = GRID_SIZE * self.zoom
        if gs == 0:
            return 0, 0
        gc = int((px - CANVAS_X - self.pan_px) / gs)
        gr = int((py - CANVAS_Y - self.pan_py) / gs)
        return gc, gr

    def _gs(self) -> float:
        return GRID_SIZE * self.zoom

    def comp_t1px(self, comp: PlacedComponent) -> Tuple[int, int]:
        return self._g2p(comp.grid_c, comp.grid_r)

    def comp_t2px(self, comp: PlacedComponent) -> Tuple[int, int]:
        return self._g2p(comp.grid_c2, comp.grid_r2)

    def comp_cpx(self, comp: PlacedComponent) -> Tuple[int, int]:
        t1, t2 = self.comp_t1px(comp), self.comp_t2px(comp)
        return ((t1[0] + t2[0]) // 2, (t1[1] + t2[1]) // 2)

    # ── Zoom helpers ──────────────────────────────────────────

    def zoom_at(self, factor: float, mouse_pos: Tuple[int, int]) -> None:
        """Zoom centrado en la posicion del raton (o centro del canvas)."""
        mx, my = mouse_pos
        gs_old  = GRID_SIZE * self.zoom
        if gs_old == 0:
            return
        # fractional grid position under mouse
        gc_f = (mx - CANVAS_X - self.pan_px) / gs_old
        gr_f = (my - CANVAS_Y - self.pan_py) / gs_old
        new_zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        self.zoom   = new_zoom
        gs_new      = GRID_SIZE * self.zoom
        self.pan_px = mx - CANVAS_X - gc_f * gs_new
        self.pan_py = my - CANVAS_Y - gr_f * gs_new

    def zoom_center(self, factor: float) -> None:
        """Zoom centrado en el canvas (para teclas +/-)."""
        cx = CANVAS_X + CANVAS_W // 2
        cy = CANVAS_Y + CANVAS_H // 2
        self.zoom_at(factor, (cx, cy))

    def reset_view(self) -> None:
        self.zoom   = 1.0
        self.pan_px = 0.0
        self.pan_py = 0.0

    def fit_to_screen(self) -> None:
        """Ajusta zoom y pan para que todos los componentes quepan en pantalla."""
        comps = self.graph.components
        if not comps:
            self.reset_view()
            return
        min_c = min(c.grid_c  for c in comps) - 1
        max_c = max(c.grid_c2 for c in comps) + 2
        min_r = min(c.grid_r  for c in comps) - 1
        max_r = max(c.grid_r2 for c in comps) + 2
        w_cells = max(max_c - min_c, 1)
        h_cells = max(max_r - min_r, 1)
        zoom_x  = CANVAS_W / (w_cells * GRID_SIZE)
        zoom_y  = CANVAS_H / (h_cells * GRID_SIZE)
        self.zoom   = max(self.ZOOM_MIN, min(self.ZOOM_MAX,
                          min(zoom_x, zoom_y) * 0.88))
        gs          = GRID_SIZE * self.zoom
        content_w   = w_cells * gs
        content_h   = h_cells * gs
        self.pan_px = (CANVAS_W - content_w) / 2 - min_c * gs
        self.pan_py = (CANVAS_H - content_h) / 2 - min_r * gs

    # ── Hit tests ─────────────────────────────────────────────

    def _comp_at(self, px: int, py: int) -> Optional[PlacedComponent]:
        slack = max(14, int(18 * self.zoom))
        best, best_d = None, slack
        for c in self.graph.components:
            cx, cy = self.comp_cpx(c)
            d = math.hypot(px - cx, py - cy)
            if d < best_d:
                best_d, best = d, c
        return best

    def _wire_at(self, px: int, py: int) -> Optional[Wire]:
        thr = max(8, int(10 * self.zoom))
        for w in self.graph.wires:
            pts = [self._g2p(*p) for p in w.path]
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]; x2, y2 = pts[i + 1]
                dx, dy = x2 - x1, y2 - y1
                L2 = dx*dx + dy*dy
                if L2 == 0:
                    d = math.hypot(px - x1, py - y1)
                else:
                    t = max(0.0, min(1.0, ((px-x1)*dx + (py-y1)*dy) / L2))
                    d = math.hypot(px - (x1 + t*dx), py - (y1 + t*dy))
                if d < thr:
                    return w
        return None

    def _comps_in_rect(self, r: pygame.Rect) -> Set[str]:
        """Return UIDs of components whose centre pixel is inside r."""
        return {c.uid for c in self.graph.components
                if r.collidepoint(self.comp_cpx(c))}

    # ── Events ────────────────────────────────────────────────

    def handle_event(self, event, runner: SimulationRunner) -> Optional[dict]:

        # ── MOUSEMOTION ───────────────────────────────────────
        if event.type == pygame.MOUSEMOTION:
            px, py = event.pos
            if self.rect.collidepoint(event.pos):
                self._hover_gc, self._hover_gr = self._p2g(px, py)
            else:
                self._hover_gc = self._hover_gr = None

            # Pan
            if self._panning:
                dx = px - self._pan_mouse[0]
                dy = py - self._pan_mouse[1]
                self.pan_px = self._pan_origin[0] + dx
                self.pan_py = self._pan_origin[1] + dy
                return None

            # Multi-drag: move all selected components together
            if self._drag_uid and self._drag_orig_positions:
                gc, gr = self._p2g(px, py)
                # Delta from drag start
                orig_gc, orig_gr = self._drag_orig_positions.get(
                    self._drag_uid, (gc, gr))
                # Compute offset relative to original anchor
                anchor_c = orig_gc + self._drag_off[0]
                anchor_r = orig_gr + self._drag_off[1]
                delta_c  = gc - anchor_c - self._drag_off[0]
                delta_r  = gr - anchor_r - self._drag_off[1]
                # Actually move by distance from anchor start
                gc_new = gc - self._drag_off[0]
                gr_new = gr - self._drag_off[1]
                delta_c2 = gc_new - self._drag_orig_positions[self._drag_uid][0]
                delta_r2 = gr_new - self._drag_orig_positions[self._drag_uid][1]
                for uid, (oc, or_) in self._drag_orig_positions.items():
                    comp = self.graph.get(uid)
                    if comp:
                        new_c = max(0, min(GRID_COLS - 2, oc + delta_c2))
                        new_r = max(0, min(GRID_ROWS - 2, or_ + delta_r2))
                        # ✅ FIX: NEVER reset node names while dragging
                        comp.grid_c = new_c
                        comp.grid_r = new_r
                return None

            # Rect selection preview
            if self._rect_sel:
                self._rect_p2 = (px, py)
            return None

        # ── MOUSEBUTTONDOWN ───────────────────────────────────
        if event.type == pygame.MOUSEBUTTONDOWN:
            px, py = event.pos

            # Middle button → pan
            if event.button == 2:
                self._panning    = True
                self._pan_mouse  = (px, py)
                self._pan_origin = (self.pan_px, self.pan_py)
                return None

            # Scroll buttons 4/5 (old-style) → zoom
            if event.button == 4:
                self.zoom_at(self.ZOOM_STEP, (px, py))
                return None
            if event.button == 5:
                self.zoom_at(1 / self.ZOOM_STEP, (px, py))
                return None

            # Right-click → finalize wire or cancel
            if event.button == 3:
                if self.active_tool == 'WIRE' and len(self._wire_path) >= 2:
                    return self._finalize_wire_result()
                self._wire_path.clear()
                return None

            if event.button != 1:
                return None
            if not self.rect.collidepoint(event.pos):
                return None

            gc, gr = self._p2g(px, py)

            # ── SELECT ──────────────────────────────────────
            if self.active_tool == 'SELECT':
                wire = self._wire_at(px, py)
                if wire:
                    self._sel_wire_uid = wire.uid
                    self.selected_uid  = None
                    self.selected_uids.clear()
                    self._rect_sel = False
                    return {'action': 'wire_selected', 'wire': wire}

                comp = self._comp_at(px, py)
                if comp:
                    # Toggle switch
                    if comp.etype == 'S':
                        comp.is_closed = not comp.is_closed
                        runner.set_switch(comp.uid, comp.is_closed)

                    # Ctrl+click → add to multi-selection
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_CTRL:
                        if comp.uid in self.selected_uids:
                            self.selected_uids.discard(comp.uid)
                        else:
                            self.selected_uids.add(comp.uid)
                        self.selected_uid = comp.uid
                    else:
                        # Single select: if comp already in multi-sel, keep group
                        if comp.uid not in self.selected_uids:
                            self.selected_uids = {comp.uid}
                        self.selected_uid = comp.uid

                    self._sel_wire_uid = None
                    self._rect_sel     = False

                    # Start drag: record original positions of all selected
                    self._drag_uid = comp.uid
                    self._drag_off = (gc - comp.grid_c, gr - comp.grid_r)
                    self._drag_orig_positions = {
                        uid: (c.grid_c, c.grid_r)
                        for uid in self.selected_uids
                        if (c := self.graph.get(uid)) is not None
                    }
                    return {'action': 'selected', 'comp': comp}

                else:
                    # Click on empty → start rect-select (unless Ctrl held)
                    mods = pygame.key.get_mods()
                    if not (mods & pygame.KMOD_CTRL):
                        self.selected_uid  = None
                        self.selected_uids.clear()
                        self._sel_wire_uid = None
                    self._rect_sel = True
                    self._rect_p1  = (px, py)
                    self._rect_p2  = (px, py)
                    return {'action': 'deselected', 'comp': None}

            # ── WIRE ────────────────────────────────────────
            elif self.active_tool == 'WIRE':
                if 0 <= gc < GRID_COLS and 0 <= gr < GRID_ROWS:
                    if not self._wire_path:
                        self._wire_path = [(gc, gr)]
                    else:
                        last = self._wire_path[-1]
                        if (gc, gr) != last:
                            self._wire_path.append((gc, gr))
                    return {'action': 'wire_point', 'pos': (gc, gr)}

            # ── Placement ───────────────────────────────────
            elif self.active_tool in ('R', 'C', 'L', 'V', 'S', 'GND'):
                if 0 <= gc < GRID_COLS - 1 and 0 <= gr < GRID_ROWS - 1:
                    comp = self._place(gc, gr)
                    if comp:
                        self.selected_uid = comp.uid
                        self.selected_uids = {comp.uid}
                        return {'action': 'placed', 'comp': comp}

        # ── MOUSEBUTTONUP ─────────────────────────────────────
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2:
                self._panning = False

            if event.button == 1:
                # Finalize rect selection
                if self._rect_sel:
                    self._rect_sel = False
                    x1 = min(self._rect_p1[0], self._rect_p2[0])
                    y1 = min(self._rect_p1[1], self._rect_p2[1])
                    x2 = max(self._rect_p1[0], self._rect_p2[0])
                    y2 = max(self._rect_p1[1], self._rect_p2[1])
                    if x2 - x1 > 4 or y2 - y1 > 4:
                        sel_rect = pygame.Rect(x1, y1, x2-x1, y2-y1)
                        found = self._comps_in_rect(sel_rect)
                        mods  = pygame.key.get_mods()
                        if mods & pygame.KMOD_CTRL:
                            self.selected_uids |= found
                        else:
                            self.selected_uids = found
                        if found:
                            self.selected_uid = next(iter(found))
                            return {'action': 'selected',
                                    'comp': self.graph.get(self.selected_uid)}
                self._drag_uid             = None
                self._drag_orig_positions  = {}

        # ── MOUSEWHEEL → Zoom ─────────────────────────────────
        if event.type == pygame.MOUSEWHEEL:
            mpos = pygame.mouse.get_pos()
            if self.rect.collidepoint(mpos):
                # event.y > 0 = scroll up = zoom in
                dy = event.y if event.y != 0 else -event.x
                factor = self.ZOOM_STEP if dy > 0 else 1 / self.ZOOM_STEP
                self.zoom_at(factor, mpos)
                return None

        # ── KEYDOWN ───────────────────────────────────────────
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()

            # DELETE: remove all selected
            if event.key == pygame.K_DELETE:
                deleted = False
                if self._sel_wire_uid:
                    self.graph.remove_wire(self._sel_wire_uid)
                    self._sel_wire_uid = None
                    deleted = True
                uids = list(self.selected_uids)
                if self.selected_uid and self.selected_uid not in uids:
                    uids.append(self.selected_uid)
                for uid in uids:
                    self.graph.remove(uid)
                    deleted = True
                self.selected_uid   = None
                self.selected_uids.clear()
                if deleted:
                    return {'action': 'deleted', 'comp': None}

            # R: rotate
            if event.key == pygame.K_r and not mods:
                self.place_orient = 'V' if self.place_orient == 'H' else 'H'

            # F: fit to screen
            if event.key == pygame.K_f and not mods:
                self.fit_to_screen()

            # = / + : zoom in
            if event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                self.zoom_center(self.ZOOM_STEP)

            # - : zoom out
            if event.key == pygame.K_MINUS:
                self.zoom_center(1 / self.ZOOM_STEP)

            # 0 / HOME: reset view
            if event.key in (pygame.K_0, pygame.K_HOME) and not mods:
                self.reset_view()

            # ESC: cancel wire / revert to SELECT
            if event.key == pygame.K_ESCAPE:
                self._wire_path.clear()
                self.active_tool   = 'SELECT'
                self.selected_uid  = None
                self.selected_uids.clear()

            # Enter: finalize wire
            if event.key == pygame.K_RETURN and self.active_tool == 'WIRE':
                if len(self._wire_path) >= 2:
                    return self._finalize_wire_result()

            # Ctrl+D: duplicate
            if event.key == pygame.K_d and (mods & pygame.KMOD_CTRL):
                if self.selected_uid:
                    new_comp = self.graph.duplicate(self.selected_uid, 1, 1)
                    if new_comp:
                        self.selected_uid  = new_comp.uid
                        self.selected_uids = {new_comp.uid}
                        return {'action': 'placed', 'comp': new_comp}

            # Ctrl+A: select all
            if event.key == pygame.K_a and (mods & pygame.KMOD_CTRL):
                self.selected_uids = {c.uid for c in self.graph.components}
                if self.graph.components:
                    self.selected_uid = self.graph.components[0].uid

        return None

    # ── Wire helpers ──────────────────────────────────────────

    def _finalize_wire_result(self) -> Optional[dict]:
        w = self._finalize_wire()
        if w:
            return {'action': 'wire_placed', 'wire': w}
        return None

    def _finalize_wire(self) -> Optional[Wire]:
        if len(self._wire_path) < 2:
            self._wire_path.clear()
            return None
        w = self.graph.add_wire(self._wire_path)
        gc1, gr1 = self._wire_path[0]
        gc2, gr2 = self._wire_path[-1]
        n_start  = self.graph.node_at_grid(gc1, gr1)
        n_end    = self.graph.node_at_grid(gc2, gr2)
        if n_start and n_end and n_start != n_end:
            auto_pfx = 'N_'
            if (n_start.startswith(auto_pfx) and not n_end.startswith(auto_pfx)):
                self.graph.merge_nodes(n_end, n_start)
            else:
                self.graph.merge_nodes(n_start, n_end)
        self._wire_path.clear()
        self.selected_uid  = None
        self._sel_wire_uid = w.uid
        return w

    # ── Placement ─────────────────────────────────────────────

    def _place(self, gc: int, gr: int) -> Optional[PlacedComponent]:
        etype  = self.active_tool
        orient = self.place_orient
        if etype == 'GND':
            orient = 'V'
        n1 = f"N_{gc}_{gr}"
        n2 = f"N_{gc+1}_{gr}" if orient == 'H' else f"N_{gc}_{gr+1}"
        if etype == 'GND':
            n1 = n2 = 'GND'
        defaults = {
            'R':   (1000.0, 'R 1kΩ'),
            'C':   (1e-6,   'C 1µF'),
            'L':   (1e-6,   'L 1µH'),
            'V':   (5000.0, 'V 5kV'),
            'S':   (0.0,    'Switch'),
            'GND': (0.0,    'GND'),
        }
        value, label = defaults.get(etype, (0.0, etype))
        return self.graph.add(etype, gc, gr, orient, value, label, n1, n2)

    # ── Drawing ───────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, fonts: dict, runner: SimulationRunner) -> None:
        r  = self.rect
        gs = self._gs()

        # Canvas BG
        pygame.draw.rect(surf, BG, r)
        
        # ── Animated Background ───────────────────────────────
        self.bg_phase += 0.01
        for bx, by in self.bg_dots:
            px = int((bx + self.pan_px*0.5) % CANVAS_W) + CANVAS_X
            py = int((by + self.pan_py*0.5 + math.sin(self.bg_phase + bx)*5) % CANVAS_H) + CANVAS_Y
            surf.set_at((px, py), (30, 40, 60))

        # ── Grid ─────────────────────────────────────────────
        # Extended range to cover panned canvas
        start_c = max(0, int(-self.pan_px / gs) - 1)
        end_c   = min(GRID_COLS + 10, int((CANVAS_W - self.pan_px) / gs) + 2)
        start_r = max(0, int(-self.pan_py / gs) - 1)
        end_r   = min(GRID_ROWS + 10, int((CANVAS_H - self.pan_py) / gs) + 2)

        for gc in range(start_c, end_c):
            x = int(CANVAS_X + gc * gs + self.pan_px)
            if CANVAS_X <= x <= CANVAS_X + CANVAS_W:
                pygame.draw.line(surf, GRID_COL,
                                 (x, CANVAS_Y), (x, CANVAS_Y + CANVAS_H))
        for gr in range(start_r, end_r):
            y = int(CANVAS_Y + gr * gs + self.pan_py)
            if CANVAS_Y <= y <= CANVAS_Y + CANVAS_H:
                pygame.draw.line(surf, GRID_COL,
                                 (CANVAS_X, y), (CANVAS_X + CANVAS_W, y))

        # Clip to canvas
        old_clip = surf.get_clip()
        surf.set_clip(pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H))

        # ── Node wires ────────────────────────────────────────
        self._draw_node_wires(surf, runner)

        # ── Explicit wires ────────────────────────────────────
        self._draw_explicit_wires(surf, runner)

        # --- Highlighting search results ---
        if self.search_term:
            self.bg_phase += 0.1 # Reuse phase for blinking
            alpha = int(120 + 80 * math.sin(self.bg_phase))
            for comp in self.graph.components:
                if (self.search_term.lower() in comp.uid.lower() or 
                    self.search_term.lower() in comp.label.lower()):
                    cpx = self.comp_cpx(comp)
                    pygame.draw.circle(surf, (255, 255, 0, alpha), cpx, 45, 3)
                    
        for comp in self.graph.components:
            is_sel = (comp.uid in self.selected_uids)
            # Match check for draw_comp styling
            is_match = (self.search_term and 
                        (self.search_term.lower() in comp.uid.lower() or 
                         self.search_term.lower() in comp.label.lower()))
                
            primary   = (comp.uid == self.selected_uid)
            multi_sel = is_sel
            self._draw_comp(surf, comp, primary, multi_sel, fonts, runner)

        # ── Current particles ─────────────────────────────────
        self.particles.draw(surf, self)

        # ── Wire preview ─────────────────────────────────────
        self._draw_wire_preview(surf, fonts)

        # ── Placement ghost ───────────────────────────────────
        if self._hover_gc is not None and self.active_tool not in ('SELECT', 'WIRE'):
            gx, gy = self._g2p(self._hover_gc, self._hover_gr)
            ghost  = pygame.Surface((max(1, int(gs)), max(1, int(gs))),
                                    pygame.SRCALPHA)
            ghost.fill((*ACCENT, 25))
            surf.blit(ghost, (gx, gy))

        # ── Rect-selection overlay ────────────────────────────
        if self._rect_sel:
            x1 = min(self._rect_p1[0], self._rect_p2[0])
            y1 = min(self._rect_p1[1], self._rect_p2[1])
            x2 = max(self._rect_p1[0], self._rect_p2[0])
            y2 = max(self._rect_p1[1], self._rect_p2[1])
            if x2 > x1 and y2 > y1:
                ovl = pygame.Surface((x2 - x1, y2 - y1), pygame.SRCALPHA)
                ovl.fill((*RECT_SEL_C, 28))
                surf.blit(ovl, (x1, y1))
                pygame.draw.rect(surf, RECT_SEL_C,
                                 pygame.Rect(x1, y1, x2-x1, y2-y1), 1)

        # ── Hover terminal tooltip ────────────────────────────
        if (self._hover_gc is not None and
                self.active_tool == 'SELECT' and gs >= 28):
            n = self.graph.node_at_grid(self._hover_gc, self._hover_gr)
            if n:
                tx, ty = self._g2p(self._hover_gc, self._hover_gr)
                draw_text(surf, f' {n} ', tx + 8, ty - 16, fonts['xs'],
                          WHITE, bg=(0, 0, 0))

        surf.set_clip(old_clip)

        # ── HUD ───────────────────────────────────────────────
        n_sel = len(self.selected_uids)
        zoom_str = f'zoom {self.zoom:.2f}x'
        if n_sel > 1:
            zoom_str += f'  [{n_sel} seleccionados]'
        draw_text(surf, zoom_str,
                  CANVAS_X + 6, CANVAS_Y + CANVAS_H - 16, fonts['xs'], (35, 48, 68))

        if self.active_tool == 'WIRE':
            tip = (f'Wire: {len(self._wire_path)} pts  '
                   'Clic=punto  Clic-der/Enter=finalizar  ESC=cancelar')
            draw_text(surf, tip, CANVAS_X + 100, CANVAS_Y + CANVAS_H - 16,
                      fonts['xs'], WIRE_COL)

        # Grid coords of hover
        if self._hover_gc is not None:
            draw_text(surf,
                      f'({self._hover_gc},{self._hover_gr})',
                      CANVAS_X + CANVAS_W - 6, CANVAS_Y + CANVAS_H - 16,
                      fonts['xs'], (35, 48, 68), 'topright')

        pygame.draw.rect(surf, PANEL_BORDER, r, 1, border_radius=4)

    def _draw_node_wires(self, surf, runner):
        node_pts: Dict[str, List] = {}
        for comp in self.graph.components:
            for gc, gr, p_id in comp.get_pins_layout():
                node_name = self.graph.node_at_grid(gc, gr)
                if node_name:
                    node_pts.setdefault(node_name, []).append(self._g2p(gc, gr))

        for node_name, pts in node_pts.items():
            unique = list(dict.fromkeys(map(tuple, pts)))
            if len(unique) < 2:
                continue
            color = WIRE_GND if node_name == 'GND' else WIRE_COL
            
            if runner.is_running:
                v = runner.get_voltage(node_name)
                if abs(v) > 50:
                    glow_color = lerp_color(color, ACCENT, min(abs(v) / 5000, 1.0))
                    # Multi-pass glow
                    for thick in range(6, 1, -2):
                        pygame.draw.lines(surf, glow_color, False, unique, thick)
                    color = glow_color

            pygame.draw.lines(surf, color, False, unique, 2)
            for p in unique:
                pygame.draw.circle(surf, color, p, 3)

    def _draw_explicit_wires(self, surf, runner):
        for wire in self.graph.wires:
            if len(wire.path) < 2:
                continue
            pts    = [self._g2p(*p) for p in wire.path]
            is_sel = (wire.uid == self._sel_wire_uid)
            col    = SELECT_COL if is_sel else WIRE_COL
            thick  = 3 if is_sel else 2
            
            if runner.is_running:
                gc0, gr0 = wire.path[0]
                n = self.graph.node_at_grid(gc0, gr0)
                if n:
                    v = runner.get_voltage(n)
                    if abs(v) > 50:
                        glow_color = lerp_color(col, ACCENT, min(abs(v)/5000, 1.0))
                        for gw in range(6, 1, -2):
                            pygame.draw.lines(surf, glow_color, False, pts, gw)
                        col = glow_color

            pygame.draw.lines(surf, col, False, pts, thick)
            for p in pts:
                pygame.draw.circle(surf, col, p, 4)

    def _draw_wire_preview(self, surf, fonts):
        if not self._wire_path:
            return
        pts = [self._g2p(*p) for p in self._wire_path]
        if len(pts) >= 2:
            pygame.draw.lines(surf, WIRE_COL, False, pts, 2)
        for p in pts:
            pygame.draw.circle(surf, WIRE_COL, p, 5)
        if self._hover_gc is not None:
            last = pts[-1]
            cur  = self._g2p(self._hover_gc, self._hover_gr)
            pygame.draw.line(surf, (*WIRE_COL, 100), last, cur, 1)
            pygame.draw.circle(surf, WIRE_COL, cur, 4)

    def _draw_comp(self, surf, comp: PlacedComponent,
                   selected: bool, multi_sel: bool,
                   fonts: dict, runner: SimulationRunner) -> None:
        t1   = self.comp_t1px(comp)
        t2   = self.comp_t2px(comp)
        cp   = self.comp_cpx(comp)
        gs   = self._gs()
        base = COMP_COLORS.get(comp.etype, WHITE)
        col  = SELECT_COL if selected else \
               lerp_color(base, SELECT_COL, 0.4) if multi_sel else base

        # Multi-select glow background
        if multi_sel and not selected:
            glow_r = pygame.Rect(t1[0]-4, t1[1]-4,
                                 abs(t2[0]-t1[0])+8, abs(t2[1]-t1[1])+8)
            glow_s = pygame.Surface(glow_r.size, pygame.SRCALPHA)
            glow_s.fill((*RECT_SEL_C, 40))
            surf.blit(glow_s, glow_r.topleft)

        r_dot = max(2, int(3 * self.zoom))
        for gc, gr, p_id in comp.get_pins_layout():
            pt = self._g2p(gc, gr)
            pygame.draw.circle(surf, col, pt, r_dot)

        if   comp.etype == 'R':   self._drw_R(surf, t1, t2, cp, col)
        elif comp.etype == 'C':   self._drw_C(surf, t1, t2, cp, col, comp.orientation)
        elif comp.etype == 'L':   self._drw_L(surf, t1, t2, cp, col, comp.orientation)
        elif comp.etype == 'V':   self._drw_V(surf, t1, t2, cp, col, fonts)
        elif comp.etype == 'S':   self._drw_S(surf, t1, t2, cp, col, comp.is_closed)
        elif comp.etype == 'GND': self._drw_GND(surf, t1, col)
        elif comp.etype in ('IC', 'MCU'):
            # Dibujar caja del IC
            w_px = comp.width * gs
            h_px = comp.height * gs
            pygame.draw.rect(surf, (40, 50, 70), (t1[0], t1[1], w_px, h_px))
            pygame.draw.rect(surf, col, (t1[0], t1[1], w_px, h_px), 2)
            # Notch
            pygame.draw.circle(surf, col, (t1[0] + w_px//2, t1[1]), 4)

        # Label
        if gs >= 22:
            ly = cp[1] - max(10, int(13 * min(self.zoom, 1.5)))
            draw_text(surf, comp.label, cp[0], ly, fonts['xs'], col, 'center')

        # Node names when selected
        if selected:
            for gc, gr, p_id in comp.get_pins_layout():
                pt = self._g2p(gc, gr)
                node_name = ""
                if comp.etype == 'GND': node_name = 'GND'
                elif comp.etype in ('IC', 'MCU'): node_name = comp.pins.get(p_id, "")
                else: node_name = comp.n1 if p_id == '1' else comp.n2
                
                if node_name:
                    draw_text(surf, node_name,
                              pt[0], pt[1] - max(10, int(14 * self.zoom)),
                              fonts['xs'], ACCENT, 'center')

        # Live voltage at terminal 1
        if runner.is_running and comp.etype not in ('GND',) and gs >= 32:
            v1 = runner.get_voltage(comp.n1)
            draw_text(surf, f'{v1:.0f}V',
                      t1[0], t1[1] + max(4, int(6 * self.zoom)),
                      fonts['xs'], DIM, 'center')

    # ── Component symbols ─────────────────────────────────────

    def _drw_R(self, surf, t1, t2, cp, col):
        z  = min(self.zoom, 1.5)
        w  = int(28 * z)
        h  = int(10 * z)
        pygame.draw.line(surf, col, t1, (cp[0]-w//2, cp[1]), 2)
        pygame.draw.line(surf, col, (cp[0]+w//2, cp[1]), t2, 2)
        
        # Body Gradient
        r_body = pygame.Rect(cp[0]-w//2, cp[1]-h//2, w, h)
        pygame.draw.rect(surf, PANEL_BG, r_body, border_radius=2)
        pygame.draw.rect(surf, col,      r_body, 2, border_radius=2)
        
        # Color bands simulation
        for i in range(3):
            bx = cp[0] - w//2 + 4 + i*6*z
            pygame.draw.line(surf, ACCENT2, (bx, cp[1]-h//2+2), (bx, cp[1]+h//2-2), 2)

    def _drw_C(self, surf, t1, t2, cp, col, orient):
        z = min(self.zoom, 1.5)
        g = int(5  * z)
        s = int(12 * z)
        if orient == 'H':
            pygame.draw.line(surf, col, t1, (cp[0]-g, cp[1]), 2)
            pygame.draw.line(surf, col, (cp[0]+g, cp[1]), t2, 2)
            pygame.draw.line(surf, col, (cp[0]-g, cp[1]-s), (cp[0]-g, cp[1]+s), 3)
            pygame.draw.line(surf, col, (cp[0]+g, cp[1]-s), (cp[0]+g, cp[1]+s), 3)
        else:
            pygame.draw.line(surf, col, t1, (cp[0], cp[1]-g), 2)
            pygame.draw.line(surf, col, (cp[0], cp[1]+g), t2, 2)
            pygame.draw.line(surf, col, (cp[0]-s, cp[1]-g), (cp[0]+s, cp[1]-g), 3)
            pygame.draw.line(surf, col, (cp[0]-s, cp[1]+g), (cp[0]+s, cp[1]+g), 3)

    def _drw_L(self, surf, t1, t2, cp, col, orient):
        z   = min(self.zoom, 1.5)
        arm = int(14 * z)
        s   = int(4  * z)
        if orient == 'H':
            pygame.draw.line(surf, col, t1, (cp[0]-arm, cp[1]), 2)
            pygame.draw.line(surf, col, (cp[0]+arm, cp[1]), t2, 2)
            for i in range(4):
                cx = cp[0] - int(10*z) + i * int(7*z)
                pygame.draw.arc(surf, col,
                                pygame.Rect(cx-s, cp[1]-int(8*z), s*2, int(14*z)),
                                0, math.pi, 2)
        else:
            pygame.draw.line(surf, col, t1, (cp[0], cp[1]-arm), 2)
            pygame.draw.line(surf, col, (cp[0], cp[1]+arm), t2, 2)
            for i in range(4):
                cy = cp[1] - int(10*z) + i * int(7*z)
                pygame.draw.arc(surf, col,
                                pygame.Rect(cp[0]-int(8*z), cy-s, int(14*z), s*2),
                                math.pi*1.5, math.pi*2.5, 2)

    def _drw_V(self, surf, t1, t2, cp, col, fonts):
        r = max(8, int(13 * min(self.zoom, 1.5)))
        pygame.draw.line(surf, col, t1, cp, 2)
        pygame.draw.line(surf, col, cp, t2, 2)
        pygame.draw.circle(surf, PANEL_BG, cp, r)
        pygame.draw.circle(surf, col,      cp, r, 2)
        x, y = cp
        s = max(3, int(4 * self.zoom))
        pygame.draw.line(surf, SAFE,   (x-s, y-s), (x+s, y-s), 2)
        pygame.draw.line(surf, SAFE,   (x,   y-s-3), (x, y-s+3), 2)
        pygame.draw.line(surf, DANGER, (x-s, y+s), (x+s, y+s), 2)

    def _drw_S(self, surf, t1, t2, cp, col, closed: bool):
        r = max(4, int(5 * self.zoom))
        pygame.draw.circle(surf, col, t1, r, 2)
        pygame.draw.circle(surf, col, t2, r, 2)
        if closed:
            pygame.draw.line(surf, SAFE, t1, t2, 4)
            pygame.draw.circle(surf, SAFE, cp, r-1)
        else:
            mx = (t1[0]+t2[0])//2
            my = (t1[1]+t2[1])//2
            off = max(10, int(15 * self.zoom))
            # Draw lever with mechanical look
            pygame.draw.line(surf, WARN, t1, (mx, my - off), 3)
            pygame.draw.circle(surf, WARN, (mx, my - off), 3)

    def _drw_GND(self, surf, t1, col):
        x, y = t1
        z = min(self.zoom, 1.5)
        for i, ww in enumerate([16, 11, 7]):
            ws = max(4, int(ww * z))
            yy = y + 2 + i * max(3, int(5 * z))
            pygame.draw.line(surf, col,
                             (x - ws//2, yy), (x + ws//2, yy),
                             max(1, int(z)) + 1)
