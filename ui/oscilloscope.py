"""
ui/oscilloscope.py
==================
Panel de osciloscopio virtual multi-canal.

Muestra el historial de voltaje de hasta 4 nodos en tiempo real.
El usuario selecciona que nodos observar mediante teclado (← →) o clic.
"""

import math
from collections import deque

import pygame

from ui.theme import (
    W, OSC_Y, OSC_H, STATUS_Y,
    BG, GRID_COL, ACCENT, ACCENT2, WARN, DANGER, SAFE, DIM, WHITE,
    PANEL_BG, PANEL_BORDER,
    draw_text, draw_panel, lerp_color,
)
from ui.editor import SimulationRunner


# ─── Config ───────────────────────────────────────────────────────────────────

TRACE_COLORS = [
    (  0, 220, 160),   # cyan-green
    (255, 160,  30),   # amber
    (220,  40,  60),   # red
    (  0, 160, 255),   # blue
]

MAX_CHANNELS = 4


class OscilloscopePanel:
    """
    Panel de osciloscopio que muestra voltaje vs tiempo para nodos seleccionados.

    Controles:
        ← / →      Ciclar el nodo del canal 1
        Clic en nodo-badge  Seleccionar canal
    """

    PAD     = 8
    CTRL_W  = 180    # ancho panel de controles izquierdo

    def __init__(self):
        self.rect = pygame.Rect(0, OSC_Y, W, OSC_H)
        self._channels: list = []     # lista de node_names observados
        self._all_nodes: list = []    # todos los nodos disponibles
        self._ch_idx  : int  = 0      # nodo del canal 1 en _all_nodes
        self._hover_ch: int  = -1
        self._btn_rects: list = []    # rects de los channel-selector badges

    # ── Public API ────────────────────────────────────────────

    def set_nodes(self, node_names: list) -> None:
        """Actualiza la lista de nodos disponibles (llamar tras cambiar el circuito)."""
        self._all_nodes = list(node_names)
        # Keep valid channels
        self._channels = [n for n in self._channels if n in self._all_nodes]
        if not self._channels and self._all_nodes:
            self._channels = [self._all_nodes[0]]
        self._ch_idx = (self._all_nodes.index(self._channels[0])
                        if self._channels and self._all_nodes else 0)

    def handle_event(self, event, nodes: list) -> None:
        self.set_nodes(nodes)

        if event.type == pygame.MOUSEMOTION:
            self._hover_ch = -1
            for i, r in enumerate(self._btn_rects):
                if r.collidepoint(event.pos):
                    self._hover_ch = i
                    break

        if event.type == pygame.KEYDOWN:
            if not self._all_nodes:
                return
            n = len(self._all_nodes)
            if event.key == pygame.K_LEFT:
                self._ch_idx = (self._ch_idx - 1) % n
                if self._channels:
                    self._channels[0] = self._all_nodes[self._ch_idx]
                else:
                    self._channels.append(self._all_nodes[self._ch_idx])
            elif event.key == pygame.K_RIGHT:
                self._ch_idx = (self._ch_idx + 1) % n
                if self._channels:
                    self._channels[0] = self._all_nodes[self._ch_idx]
                else:
                    self._channels.append(self._all_nodes[self._ch_idx])

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self._btn_rects):
                if r.collidepoint(event.pos) and i < len(self._all_nodes):
                    node = self._all_nodes[i % len(self._all_nodes)]
                    if node in self._channels:
                        self._channels.remove(node)
                    elif len(self._channels) < MAX_CHANNELS:
                        self._channels.append(node)

    # ── Drawing ───────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, fonts: dict, runner: SimulationRunner) -> None:
        r = self.rect
        draw_panel(surf, r, 'OSCILOSCOPIO', fonts['sm'])

        # Control strip (left)
        ctrl_r = pygame.Rect(r.x + self.PAD, r.y + 22,
                             self.CTRL_W, r.h - 28)
        self._draw_controls(surf, fonts, ctrl_r, runner)

        # Waveform area (right of controls)
        wave_r = pygame.Rect(r.x + self.CTRL_W + self.PAD * 2, r.y + 18,
                             r.w - self.CTRL_W - self.PAD * 3, r.h - 26)
        self._draw_waveforms(surf, fonts, wave_r, runner)

    def _draw_controls(self, surf, fonts, r: pygame.Rect,
                       runner: SimulationRunner) -> None:
        """Panel izquierdo: estado de simulacion + node-selector badges."""
        # Sim status
        if runner.is_running:
            color  = SAFE  if not runner.is_paused else WARN
            status = 'SIMULANDO' if not runner.is_paused else 'PAUSADO'
        else:
            color, status = DIM, 'DETENIDO'

        pygame.draw.circle(surf, color, (r.x + 8, r.y + 8), 6)
        draw_text(surf, status, r.x + 18, r.y + 2, fonts['xs'], color)

        t_ms = runner.sim_time * 1000
        draw_text(surf, f't = {t_ms:7.3f} ms', r.x, r.y + 18, fonts['xs'], DIM)
        draw_text(surf, f'dt= {runner.dt_label} ', r.x, r.y + 32, fonts['xs'], DIM)

        # Node badges
        self._btn_rects.clear()
        y  = r.y + 54
        draw_text(surf, '─ Nodos disponibles', r.x, y - 2, fonts['xs'], (50, 65, 90))
        y += 14
        for i, node in enumerate(self._all_nodes[:MAX_CHANNELS * 2]):
            col     = TRACE_COLORS[i % len(TRACE_COLORS)]
            active  = node in self._channels
            btn_r   = pygame.Rect(r.x, y, r.w - 4, 20)
            self._btn_rects.append(btn_r)
            bg = tuple(min(255, c // 4) for c in col) if active else PANEL_BG
            pygame.draw.rect(surf, bg, btn_r, border_radius=3)
            pygame.draw.rect(surf, col if active else PANEL_BORDER, btn_r, 1, border_radius=3)
            dot_col = col if active else DIM
            pygame.draw.circle(surf, dot_col, (btn_r.x + 8, btn_r.centery), 4)
            draw_text(surf, node, btn_r.x + 18, btn_r.y + 4, fonts['xs'], WHITE if active else DIM)
            if runner.is_running:
                v = runner.get_voltage(node)
                draw_text(surf, f'{v:+.0f}V', btn_r.right - 4, btn_r.y + 4,
                          fonts['xs'], col if active else DIM, 'topright')
            y += 22

        # Hint
        draw_text(surf, '← → ciclar canal', r.x, r.bottom - 14, fonts['xs'], (45, 58, 80))

    def _draw_waveforms(self, surf, fonts, r: pygame.Rect,
                        runner: SimulationRunner) -> None:
        """Area de formas de onda con cuadricula y auto-escala."""
        pygame.draw.rect(surf, (6, 8, 14), r, border_radius=4)
        pygame.draw.rect(surf, PANEL_BORDER, r, 1, border_radius=4)

        # Grid
        nx, ny = 10, 4
        for i in range(1, nx):
            x = r.x + int(i * r.w / nx)
            pygame.draw.line(surf, GRID_COL, (x, r.y), (x, r.bottom))
        for j in range(1, ny):
            y = r.y + int(j * r.h / ny)
            pygame.draw.line(surf, GRID_COL, (r.x, y), (r.right, y))

        # Zero line
        zero_y = r.centery
        pygame.draw.line(surf, (35, 45, 65), (r.x, zero_y), (r.right, zero_y), 1)

        if not runner.is_running or not self._channels:
            draw_text(surf, 'No hay simulacion activa. Pulse ▶ Simular.',
                      r.centerx, r.centery, fonts['sm'], (40, 50, 70), 'center')
            return

        # Draw each channel
        for ch_i, node_name in enumerate(self._channels):
            history = runner.history.get(node_name)
            if not history or len(history) < 2:
                continue
            pts   = list(history)
            n     = len(pts)
            mx_v  = max(abs(v) for v in pts) or 1.0
            color = TRACE_COLORS[ch_i % len(TRACE_COLORS)]

            pixels = []
            for i, v in enumerate(pts):
                px = r.x + int(i / (n - 1) * (r.w - 1))
                py = r.centery - int((v / mx_v) * (r.h // 2 - 4))
                py = max(r.y + 2, min(r.bottom - 2, py))
                pixels.append((px, py))

            if len(pixels) >= 2:
                pygame.draw.lines(surf, color, False, pixels, 2)

            # Channel label and current value
            cur_v = pts[-1]
            lx    = r.right - 4
            ly    = r.y + 4 + ch_i * 16
            pygame.draw.circle(surf, color, (lx - 60, ly + 5), 4)
            draw_text(surf, f'{node_name}: {cur_v:+.1f} V', lx - 52, ly, fonts['xs'], color)

            # Scale legend
            scale_v = mx_v / 1000
            draw_text(surf, f'↕ {scale_v:.2f} kV/div',
                      r.x + 4, r.bottom - 14, fonts['xs'], DIM)
