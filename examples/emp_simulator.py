"""
╔══════════════════════════════════════════════════════════════════╗
║       SIMULADOR EMP - Red Formadora de Pulso (PFN)              ║
║       Banco de Condensadores 6×0.1µF → 0.6µF / 5kV             ║
║       Modelo físico: carga RC + descarga PFN 50Ω                ║
╚══════════════════════════════════════════════════════════════════╝

Dependencias:
    pip install pygame numpy

Controles:
    [S] - Activar/Desactivar carga (Switch S1)
    [A] - Armar sistema (Interlock de seguridad)
    [SPACE] - Disparar SCR (solo si armado y V > 80%)
    [P] - Activar resistencia de purga (descarga segura)
    [R] - Reset completo
    [ESC] - Salir
"""

import pygame
import numpy as np
import math
import time
import random
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional
from core.circuit_engine import CircuitSimulator

# ─────────────────────────────────────────────────────────
#  CONSTANTES FÍSICAS
# ─────────────────────────────────────────────────────────
V_FUENTE      = 5000.0      # Voltios (5 kV)
C_TOTAL       = 0.6e-6      # Faradios (0.6 µF)
R_LIMITE      = 10_000.0    # Ohmios  (10 kΩ - resistencia de carga)
R_PURGA       = 50_000.0    # Ohmios  (50 kΩ - resistencia de descarga segura)
Z_PFN         = 50.0        # Ohmios  (impedancia característica PFN)
TAU_CARGA     = R_LIMITE * C_TOTAL          # ~6 ms
ENERGIA_MAX   = 0.5 * C_TOTAL * V_FUENTE**2  # ~7.5 J
N_PFN         = 4           # secciones de la PFN
L_PFN         = 0.25e-6     # 0.25 µH por sección
TAU_PULSO     = 2 * N_PFN * math.sqrt(L_PFN * (C_TOTAL / N_PFN))  # ~100 ns

# ─────────────────────────────────────────────────────────
#  PYGAME / PANTALLA
# ─────────────────────────────────────────────────────────
W, H          = 1280, 800
FPS           = 60
SIM_DT        = 1.0 / FPS  # paso temporal de simulación (s)
SIM_SCALE     = 0.001       # 1 frame simula SIM_SCALE segundos reales

# Paleta "laboratorio industrial"
BG            = (10,  12,  18)
GRID          = (25,  30,  40)
ACCENT        = (0,  220, 160)   # verde-cian
WARN          = (255, 160,  30)  # ámbar
DANGER        = (220,  40,  60)  # rojo
SAFE          = (50,  200, 100)  # verde seguro
DIM           = (80,  90, 110)
WHITE         = (230, 235, 245)
PANEL_BG      = (18,  22,  32)
PANEL_BORDER  = (40,  50,  70)

# ─────────────────────────────────────────────────────────
#  PARTÍCULAS de corriente
# ─────────────────────────────────────────────────────────
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float        # 0..1
    decay: float       # cuánto muere por frame
    color: tuple
    radius: int = 3

# ─────────────────────────────────────────────────────────
#  MODELO FÍSICO
# ─────────────────────────────────────────────────────────
class PhysicsEngine:
    """
    Motor fisico del sistema EMP, implementado sobre CircuitSimulator (MNA).

    Topologia del circuito:
      PSU (5kV) -- S1 -- R_LIM -- BANCO -- C_BANCO -- GND
                                    |
                                  S_PURGE (R_on = R_PURGA = 50 kOhm) -- GND
                                    |
                                   SCR -- L0 -- L1 -- ... -- L(N-1) -- ANT_IN
                                                                           |
                                                                        R_ANT -- GND

    Los inductores en cadena (N_PFN * L_PFN) modelan la inductancia total de la PFN.
    La descarga es un transitorio RLC real resuelto por Backward Euler, no analitico.
    """

    PULSE_DT    = 10e-9    # 10 ns -- paso temporal durante el pulso
    PULSE_CHUNK = 25       # sub-pasos MNA por frame durante el pulso

    def __init__(self):
        self.reset()

    def reset(self):
        self.charging     = False
        self.armed        = False
        self.purging      = False
        self.pulse_active = False
        self.pulse_t      = 0.0
        self.sim_time     = 0.0
        self.pulse_history:  deque = deque(maxlen=400)
        self.charge_history: deque = deque(maxlen=400)
        self.pulse_count  = 0
        self.total_energy_discharged = 0.0
        self._v_cap_cache = 0.0
        self._build_circuit()

    def _build_circuit(self):
        """Construye la topologia MNA del circuito EMP."""
        self._sim = CircuitSimulator(dt=SIM_SCALE)

        # Fuente de alta tension
        self._sim.add_voltage_source('PSU', 'SRC', 'GND', V_FUENTE)

        # Switch de carga: controla la carga del banco
        self._sim.add_switch('S1', 'SRC', 'CARGA_IN',
                             is_closed=False, R_on=0.001, R_off=1e9)
        self._sim.add_resistor('R_LIM', 'CARGA_IN', 'BANCO', R_LIMITE)

        # Banco de condensadores (almacenamiento de energia)
        self._sim.add_capacitor('C_BANCO', 'BANCO', 'GND', C_TOTAL)

        # Switch de purga: R_on = R_PURGA => descarga controlada RC
        self._sim.add_switch('S_PURGE', 'BANCO', 'GND',
                             is_closed=False, R_on=R_PURGA, R_off=1e12)

        # SCR/IGBT: conmutacion del pulso de descarga
        self._sim.add_switch('SCR', 'BANCO', 'PFN_IN',
                             is_closed=False, R_on=0.01, R_off=1e9)

        # Inductores de la PFN (N_PFN en serie: inductancia total = N_PFN * L_PFN)
        prev = 'PFN_IN'
        for k in range(N_PFN):
            nxt = f'PFN{k + 1}' if k < N_PFN - 1 else 'ANT_IN'
            self._sim.add_inductor(f'L{k}', prev, nxt, L_PFN)
            prev = nxt

        # Carga: antena TEM Horn (50 Ohm)
        self._sim.add_resistor('R_ANT', 'ANT_IN', 'GND', Z_PFN)

        # Indices de nodos para extraccion rapida de resultados
        self._nBanco = self._sim.get_node('BANCO')
        self._nAnt   = self._sim.get_node('ANT_IN')

    # ── Propiedades de estado ──────────────────────────────────

    @property
    def v_cap(self) -> float:
        return self._v_cap_cache

    @property
    def energia(self) -> float:
        """Energia almacenada en el banco: E = 0.5 * C * V^2 (J)"""
        return 0.5 * C_TOTAL * self._v_cap_cache ** 2

    @property
    def nivel(self) -> float:
        """Fraccion de carga 0..1 respecto a V_FUENTE."""
        return min(self._v_cap_cache / V_FUENTE, 1.0)

    def can_fire(self) -> bool:
        return (self.armed
                and self._v_cap_cache > V_FUENTE * 0.3
                and not self.pulse_active
                and not self.purging)

    # ── Comandos de control ────────────────────────────────────

    def fire(self) -> bool:
        """Dispara el SCR. Devuelve True si el disparo fue posible."""
        if not self.can_fire():
            return False
        self._sim.set_switch('S1',  False)   # Abre camino de carga
        self._sim.set_switch('SCR', True)    # Cierra SCR -> inicio de descarga
        self.pulse_active = True
        self.pulse_t      = 0.0
        self.charging     = False
        self.pulse_count += 1
        self.total_energy_discharged += self.energia
        return True

    def activate_purge(self):
        """Inicia la descarga segura del banco a traves de R_PURGA."""
        self._sim.set_switch('S_PURGE', True)
        self._sim.set_switch('S1',      False)
        self.purging  = True
        self.charging = False
        self.armed    = False

    # ── Paso de simulacion ─────────────────────────────────────

    def step(self, dt_real: float):
        """
        Avanza la fisica dt_real segundos.

        Durante el pulso usa sub-pasos de PULSE_DT = 10 ns para capturar
        la dinamica nanosegundo del transitorio RLC de descarga.
        El transitorio se distribuye en PULSE_CHUNK sub-pasos por frame
        para que el osciloscopio muestre el pulso desplegandose en tiempo real.
        """
        self.sim_time += dt_real

        if self.pulse_active:
            self._sim.set_dt(self.PULSE_DT)
            for _ in range(self.PULSE_CHUNK):
                v, _ = self._sim.step()
                self.pulse_t         += self.PULSE_DT
                self._v_cap_cache     = v[self._nBanco]
                pulse_v               = v[self._nAnt]
                self.pulse_history.append(pulse_v)
                if self.pulse_t >= TAU_PULSO:
                    self._end_pulse()
                    break
        else:
            # Sincronizar switches con los flags de estado del UI
            self._sim.set_switch('S1',      self.charging and not self.purging)
            self._sim.set_switch('S_PURGE', self.purging)
            self._sim.set_dt(dt_real)
            v, _ = self._sim.step()
            self._v_cap_cache = v[self._nBanco]

            # Finalizacion de purga: banco casi descargado
            if self.purging and self._v_cap_cache < 1.0:
                self._v_cap_cache = 0.0
                self.purging      = False
                self._sim.set_switch('S_PURGE', False)

            self.pulse_history.append(v[self._nAnt])

        self.charge_history.append(self._v_cap_cache)

    def _end_pulse(self):
        """Finaliza el pulso y restaura la escala temporal de carga."""
        self._sim.set_switch('SCR', False)
        self._sim.set_dt(SIM_SCALE)
        self.pulse_active = False
        self.pulse_t      = 0.0

# ─────────────────────────────────────────────────────────
#  SISTEMA DE PARTÍCULAS
# ─────────────────────────────────────────────────────────
class ParticleSystem:
    def __init__(self):
        self.particles: List[Particle] = []

    def emit_charge_flow(self, path_points, intensity=0.3, color=ACCENT):
        """Emite partículas a lo largo de un camino (carga)"""
        if random.random() > intensity:
            return
        idx = random.randint(0, len(path_points) - 2)
        x, y = path_points[idx]
        nx, ny = path_points[idx + 1]
        dx, dy = nx - x, ny - y
        speed  = random.uniform(1.5, 4.0)
        length = math.hypot(dx, dy) or 1
        self.particles.append(Particle(
            x=x + random.gauss(0, 1),
            y=y + random.gauss(0, 1),
            vx=dx / length * speed,
            vy=dy / length * speed,
            life=1.0,
            decay=random.uniform(0.015, 0.035),
            color=color,
            radius=random.randint(2, 4),
        ))

    def emit_burst(self, cx, cy, n=80, color=DANGER):
        """Explosión de partículas al disparar"""
        for _ in range(n):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 8)
            self.particles.append(Particle(
                x=cx, y=cy,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=1.0,
                decay=random.uniform(0.02, 0.06),
                color=color,
                radius=random.randint(2, 5),
            ))

    def update(self):
        alive = []
        for p in self.particles:
            p.x    += p.vx
            p.y    += p.vy
            p.vx   *= 0.97
            p.vy   *= 0.97
            p.life -= p.decay
            if p.life > 0:
                alive.append(p)
        self.particles = alive

    def draw(self, surf):
        for p in self.particles:
            alpha = int(p.life * 255)
            r, g, b = p.color
            col = (min(r, 255), min(g, 255), min(b, 255))
            pygame.draw.circle(surf, col, (int(p.x), int(p.y)), p.radius)

# ─────────────────────────────────────────────────────────
#  UTILIDADES DE DIBUJO
# ─────────────────────────────────────────────────────────
def draw_text(surf, text, x, y, font, color=WHITE, anchor="topleft"):
    img = font.render(text, True, color)
    r   = img.get_rect(**{anchor: (x, y)})
    surf.blit(img, r)

def draw_panel(surf, rect, title="", font=None):
    pygame.draw.rect(surf, PANEL_BG,    rect, border_radius=8)
    pygame.draw.rect(surf, PANEL_BORDER, rect, 1, border_radius=8)
    if title and font:
        draw_text(surf, title, rect.x + 12, rect.y + 8, font, DIM)

def draw_grid(surf, rect, nx=10, ny=5, color=GRID):
    dx = rect.width  / nx
    dy = rect.height / ny
    for i in range(1, nx):
        x = int(rect.x + i * dx)
        pygame.draw.line(surf, color, (x, rect.y), (x, rect.bottom))
    for j in range(1, ny):
        y = int(rect.y + j * dy)
        pygame.draw.line(surf, color, (rect.x, y), (rect.right, y))

def draw_wire(surf, points, color, width=2):
    if len(points) >= 2:
        pygame.draw.lines(surf, color, False, points, width)

def lerp_color(c1, c2, t):
    """Interpolacion lineal de color. t se fija en [0,1] para evitar overflow."""
    t = max(0.0, min(1.0, t))
    return tuple(max(0, min(255, int(a + (b - a) * t))) for a, b in zip(c1, c2))

# ─────────────────────────────────────────────────────────
#  OSCILOSCOPIO VIRTUAL
# ─────────────────────────────────────────────────────────
class Oscilloscope:
    def __init__(self, rect: pygame.Rect):
        self.rect   = rect
        self.traces = {}   # name → deque of values
        self.colors = {}

    def add_trace(self, name, color, maxlen=400):
        self.traces[name] = deque(maxlen=maxlen)
        self.colors[name] = color

    def push(self, name, value):
        if name in self.traces:
            self.traces[name].append(value)

    def draw(self, surf, font_sm):
        draw_panel(surf, self.rect)
        draw_grid(surf, self.rect.inflate(-4, -4).move(2, 2))

        # Etiqueta
        draw_text(surf, "OSCILOSCOPIO  —  PULSO PFN", self.rect.x + 10, self.rect.y + 6, font_sm, DIM)

        inner = self.rect.inflate(-24, -30).move(0, 12)
        for name, data in self.traces.items():
            if len(data) < 2:
                continue
            color  = self.colors[name]
            pts    = list(data)
            # normalización automática
            mx     = max(abs(v) for v in pts) or 1.0
            points = []
            for i, v in enumerate(pts):
                px = inner.x + int(i / (len(pts) - 1) * inner.width)
                py = inner.centery - int((v / mx) * (inner.height // 2 - 4))
                points.append((px, py))
            if len(points) >= 2:
                pygame.draw.lines(surf, color, False, points, 2)

        # Escala Y
        v_scale = V_FUENTE / 2 / 1000
        draw_text(surf, f"↕ {v_scale:.1f} kV/div", self.rect.right - 10, self.rect.bottom - 16, font_sm, DIM, "bottomright")

# ─────────────────────────────────────────────────────────
#  ESQUEMA DEL CIRCUITO
# ─────────────────────────────────────────────────────────
class CircuitDiagram:
    """Dibuja el esquema simplificado del circuito EMP."""

    # Puntos clave (normalizados, se escalan al rect)
    NODES = {
        "fuente_top":  (0.05, 0.25),
        "fuente_bot":  (0.05, 0.75),
        "s1_in":       (0.20, 0.25),
        "s1_out":      (0.30, 0.25),
        "r_lim_in":    (0.30, 0.25),
        "r_lim_out":   (0.45, 0.25),
        "cap_top":     (0.55, 0.20),
        "cap_bot":     (0.55, 0.80),
        "scr_in":      (0.65, 0.25),
        "scr_out":     (0.75, 0.25),
        "pfn_in":      (0.75, 0.25),
        "pfn_out":     (0.88, 0.25),
        "antena":      (0.95, 0.25),
        "gnd_left":    (0.05, 0.75),
        "gnd_right":   (0.95, 0.75),
    }

    def __init__(self, rect: pygame.Rect):
        self.rect = rect

    def _n(self, name):
        nx, ny = self.NODES[name]
        return (int(self.rect.x + nx * self.rect.width),
                int(self.rect.y + ny * self.rect.height))

    def draw(self, surf, phys: PhysicsEngine, font_sm, font_xs):
        r = self.rect
        draw_panel(surf, r, "ESQUEMA DEL CIRCUITO", font_sm)

        wire_color = lerp_color(DIM, ACCENT, phys.nivel * 0.6) if phys.charging else DIM
        pulse_wire = DANGER if phys.pulse_active else DIM

        def n(name):
            return self._n(name)

        # ── Líneas de bus ──
        # Positivo: fuente → S1 → R_lim → cap → SCR → PFN → antena
        draw_wire(surf, [n("fuente_top"), n("s1_in")], wire_color, 2)
        draw_wire(surf, [n("r_lim_out"),
                         (n("cap_top")[0], n("r_lim_out")[1]),
                         n("cap_top")], wire_color, 2)
        draw_wire(surf, [n("cap_top"),
                         (n("scr_in")[0], n("cap_top")[1])], pulse_wire, 2)
        draw_wire(surf, [n("scr_out"), n("pfn_in")], pulse_wire, 2)
        draw_wire(surf, [n("pfn_out"), n("antena")], pulse_wire, 2)
        # Negativo (GND)
        draw_wire(surf, [n("fuente_bot"), n("gnd_right")], DIM, 2)
        draw_wire(surf, [(n("cap_bot")[0], n("gnd_right")[1]), n("cap_bot")], DIM, 2)
        draw_wire(surf, [n("antena"), n("gnd_right")], DIM, 2)

        # ── Componentes ──
        self._draw_source(surf, n("fuente_top"), n("fuente_bot"), phys.v_cap, font_xs)
        self._draw_switch(surf, n("s1_in"), n("s1_out"), phys.charging, "S1", font_xs)
        self._draw_resistor(surf, n("r_lim_in"), n("r_lim_out"), "R_lim\n10kΩ", font_xs, wire_color)
        self._draw_capacitor_bank(surf, n("cap_top"), n("cap_bot"), phys.nivel, font_xs)
        self._draw_scr(surf, n("scr_in"), n("scr_out"), phys.pulse_active, font_xs)
        self._draw_pfn(surf, n("pfn_in"), n("pfn_out"), phys.pulse_active, font_xs)
        self._draw_antenna(surf, n("antena"), phys.pulse_active, font_xs)

        # Interlock warning
        if not phys.armed:
            draw_text(surf, "⚠ NO ARMADO", r.centerx, r.bottom - 16, font_xs, WARN, "midbottom")

    def _draw_source(self, surf, top, bot, v, font):
        cx = (top[0] + bot[0]) // 2
        cy = (top[1] + bot[1]) // 2
        pygame.draw.rect(surf, PANEL_BORDER, (cx - 18, cy - 28, 36, 56), border_radius=4)
        pygame.draw.rect(surf, lerp_color((40, 40, 60), SAFE, v / V_FUENTE),
                         (cx - 16, cy - 26, 32, 52), border_radius=3)
        draw_text(surf, "PSU", cx, cy, font, WHITE, "center")
        draw_text(surf, f"{v/1000:.1f}kV", cx, cy + 14, font, ACCENT, "center")

    def _draw_switch(self, surf, a, b, closed, label, font):
        mx = (a[0] + b[0]) // 2
        my = a[1]
        color = SAFE if closed else WARN
        if closed:
            pygame.draw.line(surf, color, a, b, 3)
        else:
            pygame.draw.line(surf, color, a, (mx, my - 10), 3)
        pygame.draw.circle(surf, color, a, 4)
        pygame.draw.circle(surf, color, b, 4)
        draw_text(surf, label, mx, my - 18, font, color, "center")

    def _draw_resistor(self, surf, a, b, label, font, color):
        cx = (a[0] + b[0]) // 2
        cy = a[1]
        w, h = 30, 12
        pygame.draw.rect(surf, color, (cx - w // 2, cy - h // 2, w, h), 2, border_radius=2)
        pygame.draw.line(surf, color, a, (cx - w // 2, cy), 2)
        pygame.draw.line(surf, color, (cx + w // 2, cy), b, 2)

    def _draw_capacitor_bank(self, surf, top, bot, nivel, font):
        cx = top[0]
        cy = (top[1] + bot[1]) // 2
        h  = bot[1] - top[1]
        w  = 14
        gap = 6
        # Cuerpo del condensador (doble placa)
        for dx in (-gap, gap):
            pygame.draw.line(surf, WHITE, (cx + dx, cy - h // 3), (cx + dx, cy + h // 3), 3)
        pygame.draw.line(surf, ACCENT, (cx, top[1]), (cx, cy - gap), 2)
        pygame.draw.line(surf, ACCENT, (cx, cy + gap), (cx, bot[1]), 2)
        # Barra de carga
        fill_h = int((h // 3 * 2) * nivel)
        bar_y  = cy + h // 3 - fill_h
        color  = lerp_color((60, 60, 80), DANGER, nivel)
        pygame.draw.rect(surf, color, (cx + gap + 2, bar_y, 10, fill_h))
        draw_text(surf, f"{nivel*100:.0f}%", cx + 22, cy, font, color, "midleft")
        draw_text(surf, "0.6µF", cx, bot[1] + 8, font, DIM, "midtop")

    def _draw_scr(self, surf, a, b, active, font):
        cx = (a[0] + b[0]) // 2
        cy = a[1]
        color = DANGER if active else DIM
        pts = [(cx - 8, cy - 10), (cx + 8, cy), (cx - 8, cy + 10)]
        pygame.draw.polygon(surf, color, pts, 2)
        pygame.draw.line(surf, color, (cx + 8, cy - 10), (cx + 8, cy + 10), 2)
        pygame.draw.line(surf, color, a, (cx - 8, cy), 2)
        pygame.draw.line(surf, color, (cx + 8, cy), b, 2)
        draw_text(surf, "SCR", cx, cy - 18, font, color, "center")

    def _draw_pfn(self, surf, a, b, active, font):
        cx = (a[0] + b[0]) // 2
        cy = a[1]
        w, h = 50, 22
        color = WARN if active else DIM
        pygame.draw.rect(surf, color, (cx - w // 2, cy - h // 2, w, h), 2, border_radius=4)
        draw_text(surf, "PFN", cx, cy - 1, font, color, "center")
        draw_text(surf, "50Ω", cx, cy + 8, font, color, "center")
        pygame.draw.line(surf, color, a, (cx - w // 2, cy), 2)
        pygame.draw.line(surf, color, (cx + w // 2, cy), b, 2)

    def _draw_antenna(self, surf, pos, active, font):
        x, y = pos
        color = DANGER if active else DIM
        for i, angle in enumerate([-30, 0, 30]):
            r_ang = math.radians(angle - 90)
            length = 18 + i * 5
            ex = int(x + math.cos(r_ang) * length)
            ey = int(y + math.sin(r_ang) * length)
            pygame.draw.line(surf, color, (x, y), (ex, ey), 2 - (i > 0))
        if active:
            # ondas de radio animadas
            t  = time.time() * 8
            for k in range(1, 4):
                alpha = max(0, 1 - k * 0.3 - (t % 1) * 0.3)
                radius = int(k * 12 + (t % 1) * 8)
                col    = lerp_color(BG, DANGER, alpha)
                pygame.draw.circle(surf, col, (x, y), radius, 1)
        draw_text(surf, "ANT", x, y + 26, font, color, "midtop")

# ─────────────────────────────────────────────────────────
#  PANEL DE ESTADO / MÉTRICAS
# ─────────────────────────────────────────────────────────
def draw_status_panel(surf, rect, phys: PhysicsEngine, font_md, font_sm, font_xs):
    draw_panel(surf, rect, "PARÁMETROS DEL SISTEMA", font_sm)

    rows = [
        ("Tensión banco",   f"{phys.v_cap:>8.1f} V",   lerp_color(DIM, DANGER, phys.nivel)),
        ("Tensión pulso",   f"{phys.v_cap/2:>7.1f} V",  ACCENT),
        ("Energía almac.",  f"{phys.energia*1000:>6.2f} mJ", WARN),
        ("τ carga (RC)",    f"{TAU_CARGA*1000:>7.2f} ms", DIM),
        ("τ pulso (PFN)",   f"{TAU_PULSO*1e9:>7.1f} ns", DIM),
        ("Z caracterísc.",  f"{Z_PFN:>8.0f} Ω",         DIM),
        ("Pulsos disparad", f"{phys.pulse_count:>9}",     WHITE),
        ("E. descargada",   f"{phys.total_energy_discharged:.3f} J", WARN),
    ]

    y = rect.y + 32
    for label, value, color in rows:
        draw_text(surf, label, rect.x + 14,        y, font_xs, DIM)
        draw_text(surf, value, rect.right - 14,    y, font_xs, color, "topright")
        y += 22
        pygame.draw.line(surf, PANEL_BORDER, (rect.x + 10, y - 5), (rect.right - 10, y - 5))

    # Barra de carga vertical
    bar_rect = pygame.Rect(rect.right - 28, rect.y + 32, 14, rect.height - 50)
    pygame.draw.rect(surf, PANEL_BORDER, bar_rect, 1, border_radius=3)
    fill = int(bar_rect.height * phys.nivel)
    if fill > 0:
        fill_color = lerp_color((30, 80, 50), DANGER, phys.nivel)
        pygame.draw.rect(surf, fill_color,
                         (bar_rect.x + 1, bar_rect.bottom - fill, 12, fill),
                         border_radius=2)
    draw_text(surf, "V", bar_rect.centerx, bar_rect.y - 10, font_xs, DIM, "center")

# ─────────────────────────────────────────────────────────
#  PANEL DE CONTROLES
# ─────────────────────────────────────────────────────────
def draw_controls(surf, rect, phys: PhysicsEngine, font_sm, font_xs):
    draw_panel(surf, rect, "CONTROLES", font_sm)
    controls = [
        ("[S]", "Carga ON/OFF",  SAFE  if phys.charging else DIM),
        ("[A]", "Armar sistema", DANGER if phys.armed    else DIM),
        ("[ESPACIO]", "DISPARAR SCR", DANGER if phys.can_fire() else PANEL_BORDER),
        ("[P]", "Purgar (seguro)", WARN  if phys.purging  else DIM),
        ("[R]", "Reset total",    DIM),
        ("[ESC]", "Salir",        DIM),
    ]
    y = rect.y + 28
    for key, desc, color in controls:
        draw_text(surf, key,  rect.x + 14,       y, font_xs, color)
        draw_text(surf, desc, rect.x + 100,       y, font_xs, WHITE if color != PANEL_BORDER else DIM)
        y += 22

    # Indicadores LED
    y += 8
    indicators = [
        ("CARGA",    phys.charging,     SAFE),
        ("ARMADO",   phys.armed,        DANGER),
        ("PULSO",    phys.pulse_active, WARN),
        ("PURGANDO", phys.purging,      ACCENT),
    ]
    x0 = rect.x + 14
    for label, active, color in indicators:
        col = color if active else (40, 45, 55)
        pygame.draw.circle(surf, col, (x0 + 6, y + 7), 6)
        pygame.draw.circle(surf, WHITE if active else DIM, (x0 + 6, y + 7), 6, 1)
        draw_text(surf, label, x0 + 16, y, font_xs, col if active else DIM)
        x0 += 90

# ─────────────────────────────────────────────────────────
#  LOG DE EVENTOS
# ─────────────────────────────────────────────────────────
class EventLog:
    def __init__(self, maxlines=8):
        self.lines: deque = deque(maxlen=maxlines)
        self.times: deque = deque(maxlen=maxlines)

    def log(self, msg, color=WHITE):
        ts = time.strftime("%H:%M:%S")
        self.lines.append((f"[{ts}] {msg}", color))

    def draw(self, surf, rect, font_xs):
        draw_panel(surf, rect)
        draw_text(surf, "LOG DE EVENTOS", rect.x + 10, rect.y + 6, font_xs, DIM)
        y = rect.y + 22
        for msg, color in list(self.lines):
            draw_text(surf, msg, rect.x + 8, y, font_xs, color)
            y += 16

# ─────────────────────────────────────────────────────────
#  APLICACIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Simulador EMP — PFN 5kV / 0.6µF / 50Ω")
    clock  = pygame.time.Clock()

    # Fuentes
    try:
        font_title = pygame.font.SysFont("Consolas",      20, bold=True)
        font_md    = pygame.font.SysFont("Consolas",      16, bold=True)
        font_sm    = pygame.font.SysFont("Consolas",      13, bold=True)
        font_xs    = pygame.font.SysFont("Consolas",      11)
    except Exception:
        font_title = pygame.font.SysFont(None, 20, bold=True)
        font_md    = pygame.font.SysFont(None, 16, bold=True)
        font_sm    = pygame.font.SysFont(None, 13, bold=True)
        font_xs    = pygame.font.SysFont(None, 11)

    # Subsistemas
    phys       = PhysicsEngine()
    particles  = ParticleSystem()
    log        = EventLog()

    # Regiones de la UI
    PAD = 10
    circuit_rect = pygame.Rect(PAD,          60,           780, 320)
    osc_rect     = pygame.Rect(PAD,          390,          780, 230)
    status_rect  = pygame.Rect(800,          60,           470, 240)
    ctrl_rect    = pygame.Rect(800,          310,          470, 200)
    log_rect     = pygame.Rect(800,          520,          470, 140)
    charge_rect  = pygame.Rect(PAD,          630,          780, 130)

    osc = Oscilloscope(osc_rect)
    osc.add_trace("pulso",  DANGER, maxlen=780)
    osc.add_trace("vcap",   ACCENT, maxlen=780)

    circuit = CircuitDiagram(circuit_rect)

    log.log("Sistema inicializado. Listo.", SAFE)
    log.log(f"C={C_TOTAL*1e6:.1f}µF  Vmax={V_FUENTE/1000:.0f}kV  Z={Z_PFN:.0f}Ω", DIM)

    # Trayecto de carga (para partículas)
    def charge_path():
        n = circuit._n
        return [n("fuente_top"), n("s1_out"), n("r_lim_out"),
                (n("cap_top")[0], n("r_lim_out")[1]), n("cap_top")]

    def discharge_path():
        n = circuit._n
        return [n("cap_top"), n("scr_out"), n("pfn_out"), n("antena")]

    fired_last_frame = False
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── Eventos ──────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_s:
                    if not phys.purging and not phys.pulse_active:
                        phys.charging = not phys.charging
                        log.log("Carga " + ("ACTIVADA" if phys.charging else "DESACTIVADA"),
                                SAFE if phys.charging else WARN)

                elif event.key == pygame.K_a:
                    phys.armed = not phys.armed
                    log.log("Sistema " + ("ARMADO ⚠" if phys.armed else "DESARMADO"),
                            DANGER if phys.armed else SAFE)

                elif event.key == pygame.K_SPACE:
                    if phys.can_fire():
                        ok = phys.fire()
                        if ok:
                            log.log(f"DISPARO SCR → Pulso {phys.v_cap/2:.0f}V / {TAU_PULSO*1e9:.0f}ns", DANGER)
                            # burst de partículas en la antena
                            ax, ay = circuit._n("antena")
                            particles.emit_burst(ax, ay, n=100, color=DANGER)
                    else:
                        log.log("DISPARO BLOQUEADO (interlock / voltaje bajo)", WARN)

                elif event.key == pygame.K_p:
                    if phys.v_cap > 1:
                        phys.activate_purge()
                        log.log(f"Purga iniciada desde {phys.v_cap:.0f} V", WARN)
                    else:
                        log.log("Banco ya descargado.", SAFE)

                elif event.key == pygame.K_r:
                    phys.reset()
                    particles.particles.clear()
                    log.log("RESET completo.", ACCENT)

        # ── Física ───────────────────────────────────────
        phys.step(SIM_SCALE)

        # ── Partículas ───────────────────────────────────
        if phys.charging and phys.v_cap < V_FUENTE * 0.999:
            intensity = 0.4 + phys.nivel * 0.5
            particles.emit_charge_flow(charge_path(), intensity, ACCENT)

        if phys.pulse_active:
            particles.emit_charge_flow(discharge_path(), 0.9, DANGER)

        particles.update()

        # Osciloscopio
        pulse_v = list(phys.pulse_history)[-1] if phys.pulse_history else 0
        vcap_v  = phys.v_cap
        osc.push("pulso", pulse_v)
        osc.push("vcap",  vcap_v)

        # ── Dibujo ───────────────────────────────────────
        screen.fill(BG)

        # Fondo de grid global
        for gx in range(0, W, 40):
            pygame.draw.line(screen, GRID, (gx, 0), (gx, H))
        for gy in range(0, H, 40):
            pygame.draw.line(screen, GRID, (0, gy), (W, gy))

        # Título
        draw_text(screen,
                  "■ SIMULADOR EMP  |  PFN 5 kV / 0.6 µF / 50 Ω  |  Banco 6×0.1µF",
                  PAD + 4, 14, font_title, ACCENT)
        draw_text(screen,
                  f"t_sim={phys.sim_time:.2f}s   FPS={clock.get_fps():.0f}",
                  W - PAD, 14, font_xs, DIM, "topright")

        # Esquema del circuito
        circuit.draw(screen, phys, font_sm, font_xs)

        # Osciloscopio
        osc.draw(screen, font_sm)

        # Gráfica de carga (charge_rect)
        draw_panel(screen, charge_rect, "HISTORIAL DE CARGA  (V banco)", font_sm)
        if len(phys.charge_history) >= 2:
            inner = charge_rect.inflate(-24, -30).move(0, 12)
            pts   = list(phys.charge_history)
            pxs   = [inner.x + int(i / (len(pts)-1) * inner.width) for i in range(len(pts))]
            pys   = [inner.bottom - int(v / V_FUENTE * inner.height) for v in pts]
            points = list(zip(pxs, pys))
            if len(points) >= 2:
                pygame.draw.lines(screen, ACCENT, False, points, 2)
            # Línea de 80%
            y80 = inner.bottom - int(0.8 * inner.height)
            pygame.draw.line(screen, WARN, (inner.x, y80), (inner.right, y80), 1)
            draw_text(screen, "80%", inner.right + 4, y80 - 6, font_xs, WARN)

        # Estado
        draw_status_panel(screen, status_rect, phys, font_md, font_sm, font_xs)

        # Controles
        draw_controls(screen, ctrl_rect, phys, font_sm, font_xs)

        # Log
        log.draw(screen, log_rect, font_xs)

        # Partículas (encima de todo)
        particles.draw(screen)

        # Flash de pantalla al disparar
        if phys.pulse_active and phys.pulse_t < SIM_SCALE * 3:
            flash = pygame.Surface((W, H), pygame.SRCALPHA)
            flash.fill((220, 40, 60, 40))
            screen.blit(flash, (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
