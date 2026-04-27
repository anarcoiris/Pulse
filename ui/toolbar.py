"""
ui/toolbar.py
=============
Panel lateral izquierdo con secciones desplegables (acordeon / tree view).

Cada seccion tiene:
    - Header clicable con icono ▼/▶ que muestra/oculta sus elementos
    - Lista de botones tipo-badge con icono + etiqueta
    - Estado de colapso persistente por sesion

Corrige el bug de overflow del layout original donde algunos botones
del grupo ARCHIVO quedaban fuera de pantalla.
"""

import pygame
from dataclasses import dataclass, field
from typing import List, Optional

from ui.theme import (
    TOOLBAR_W, TITLE_H, STATUS_H, H, CANVAS_Y,
    ACCENT, ACCENT2, WARN, DANGER, SAFE, DIM, WHITE,
    PANEL_BG, PANEL_BORDER, COMP_COLORS,
    draw_text, draw_panel,
)

# ─── Item definitions ──────────────────────────────────────────────────────────

WIRE_COL = (100, 140, 200)

# (action_key, icon_char, label, color)
TOOLS: list = [
    ('SELECT', '>',  'Seleccionar',   WHITE),
    ('R',      'R',  'Resistencia',   COMP_COLORS['R']),
    ('C',      'C',  'Condensador',   COMP_COLORS['C']),
    ('L',      'L',  'Inductor',      COMP_COLORS['L']),
    ('V',      'V',  'Fuente V',      COMP_COLORS['V']),
    ('S',      'S',  'Switch/SCR',    COMP_COLORS['S']),
    ('GND',    'T',  'Tierra (GND)',  COMP_COLORS['GND']),
    ('WIRE',   '~',  'Cable',         WIRE_COL),
]

PRESETS: list = [
    ('PRESET_emp_pfn', '*', 'EMP PFN 5kV',  ACCENT2),
    ('PRESET_basic_rc','*', 'RC Simple',    ACCENT2),
    ('PRESET_rlc',     '*', 'RLC Serie',    ACCENT2),
]

SIM_ACTIONS: list = [
    ('SIM_START',  '>', 'Simular',    SAFE),
    ('SIM_PAUSE',  '|', 'Pausa',      ACCENT),
    ('SIM_RESET',  '.', 'Reset sim',  WARN),
    ('CYCLE_DT',   '~', 'dt: ---',    DIM),
]

IO_ACTIONS: list = [
    ('SAVE_JSON',  ':', 'Guardar JSON', DIM),
    ('LOAD_JSON',  '!', 'Cargar JSON',  DIM),
    ('EXPORT_PDF', '#', 'Exportar PDF', DIM),
    ('CLEAR',      'X', 'Limpiar todo', DANGER),
]

FORGE_COL = (0, 200, 180)   # teal
FORGE_ACTIONS: list = [
    ('FORGE_GEN_AI',       'A', 'Generador IA',    FORGE_COL),
    ('FORGE_EXPORT_KICAD', 'K', 'Export KiCad',    FORGE_COL),
    ('FORGE_GEN_PCB',      'P', 'Generar PCB',     FORGE_COL),
    ('FORGE_ENCLOSURE',    '3', 'Caja 3D (SCAD)',  (150, 100, 255)),
    ('FORGE_REVIEW',       'D', 'IA DRC Review',   (255, 60, 100)),
    ('FORGE_GERBERS',      'G', 'Export Gerbers',   (220, 160, 40)),
    ('FORGE_KICAD_STATUS', 'i', 'KiCad Status',    DIM),
]

SYSTEM_ACTIONS: list = [
    ('SYS_LAUNCH_MCP',    'M', 'Lanzar MCP Server', (100, 200, 100)),
    ('SYS_LAUNCH_OLLAMA', 'O', 'Lanzar Ollama',     (100, 150, 255)),
    ('SYS_UPDATE_DEPS',   'U', 'Actualizar Deps',   DIM),
]


# ─── Internal data classes ────────────────────────────────────────────────────

@dataclass
class _Item:
    key:   str
    icon:  str
    label: str
    color: tuple
    rect:  pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    hover: bool = False


@dataclass
class _Section:
    title:     str
    color:     tuple
    items:     List[_Item]
    collapsed: bool = False
    hdr_rect:  pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    hdr_hover: bool = False


def _make_items(raw: list) -> List[_Item]:
    return [_Item(key=k, icon=ic, label=lb, color=col)
            for k, ic, lb, col in raw]


# ─── ToolbarPanel ─────────────────────────────────────────────────────────────

class ToolbarPanel:
    """
    Panel izquierdo con secciones acordeon.

    Secciones:
        COMPONENTES  — herramientas de colocacion (SELECT R C L V S GND WIRE)
        PRESETS      — circuitos predefinidos
        SIMULACION   — controles de la simulacion MNA
        ARCHIVO      — guardar/cargar JSON, exportar PDF

    El estado de colapso de cada seccion persiste mientras la aplicacion
    esta en ejecucion.
    """

    BTN_H  = 28     # altura de cada boton
    HDR_H  = 24     # altura del header de seccion
    BTN_GAP = 2     # separacion vertical entre botones
    PAD    = 5      # padding interior del panel
    SCROLL_SPEED = 20

    def __init__(self):
        self.rect = pygame.Rect(0, TITLE_H, TOOLBAR_W, H - TITLE_H - STATUS_H)
        self._sections: List[_Section] = [
            _Section('COMPONENTES', ACCENT,    _make_items(TOOLS),          collapsed=False),
            _Section('PRESETS',     ACCENT2,   _make_items(PRESETS),        collapsed=False),
            _Section('SIMULACION',  SAFE,      _make_items(SIM_ACTIONS),    collapsed=False),
            _Section('FORGE',       FORGE_COL, _make_items(FORGE_ACTIONS),  collapsed=True),
            _Section('SISTEMA',     (180, 180, 180), _make_items(SYSTEM_ACTIONS), collapsed=True),
            _Section('ARCHIVO',     WARN,      _make_items(IO_ACTIONS),     collapsed=True),
        ]
        self._scroll_y: int = 0   # vertical scroll offset (px)
        self._total_h:  int = 0   # total content height (updated by _layout)

    # ── Internal layout ───────────────────────────────────────────────────────

    def _layout(self) -> None:
        """
        Recomputes all rects for headers and item buttons.
        Must be called before draw() and handle_event().
        """
        bw = self.rect.w - self.PAD * 2
        y  = self.rect.y + self.PAD - self._scroll_y

        for sec in self._sections:
            # Section header
            sec.hdr_rect = pygame.Rect(self.PAD, y, bw, self.HDR_H)
            y += self.HDR_H + self.BTN_GAP

            # Items (only if expanded)
            if not sec.collapsed:
                for item in sec.items:
                    item.rect = pygame.Rect(
                        self.PAD + 6, y,
                        bw - 6, self.BTN_H
                    )
                    y += self.BTN_H + self.BTN_GAP

            y += 4  # inter-section gap

        self._total_h = y - self.rect.y + self._scroll_y

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event, runner=None, dt_label: str = '') -> Optional[str]:
        """
        Returns the key of the pressed item, or None.
        Runner and dt_label are used to dynamically update button labels.
        """
        self._layout()

        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll_y = max(0, min(
                    self._total_h - self.rect.h,
                    self._scroll_y - event.y * self.SCROLL_SPEED
                ))
                return None

        if event.type == pygame.MOUSEMOTION:
            pos = event.pos
            for sec in self._sections:
                sec.hdr_hover = sec.hdr_rect.collidepoint(pos)
                if not sec.collapsed:
                    for item in sec.items:
                        item.hover = item.rect.collidepoint(pos)
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if not self.rect.collidepoint(pos):
                return None
            # Section headers
            for sec in self._sections:
                if sec.hdr_rect.collidepoint(pos):
                    sec.collapsed = not sec.collapsed
                    return None
            # Item buttons
            for sec in self._sections:
                if sec.collapsed:
                    continue
                for item in sec.items:
                    if item.rect.collidepoint(pos):
                        return item.key

        return None

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, fonts: dict,
             active_tool: str, runner, dt_label: str = '') -> None:
        """Render the full toolbar panel."""
        # Update dynamic labels before layout
        for sec in self._sections:
            for item in sec.items:
                if item.key == 'CYCLE_DT':
                    item.label = f'dt: {dt_label}'
                if item.key == 'SIM_START':
                    if runner and runner.is_running and not runner.is_paused:
                        item.label = 'Simulando...'
                    else:
                        item.label = 'Simular'

        self._layout()

        # Panel background
        draw_panel(surf, self.rect)

        # Clip rendering to panel bounds
        clip_rect = self.rect.inflate(-2, -2)
        old_clip  = surf.get_clip()
        surf.set_clip(clip_rect)

        for sec in self._sections:
            # ── Section header ──────────────────────────────
            arrow = '▼' if not sec.collapsed else '▶'
            hbg   = tuple(min(255, c // 5) for c in sec.color)
            if sec.hdr_hover:
                hbg = tuple(min(255, c // 3) for c in sec.color)
            pygame.draw.rect(surf, hbg, sec.hdr_rect, border_radius=4)
            pygame.draw.rect(surf, sec.color, sec.hdr_rect, 1, border_radius=4)
            draw_text(surf, arrow, sec.hdr_rect.x + 6, sec.hdr_rect.centery,
                      fonts['xs'], sec.color, 'midleft')
            draw_text(surf, sec.title,
                      sec.hdr_rect.x + 20, sec.hdr_rect.centery,
                      fonts['bold'], WHITE, 'midleft')

            # ── Item buttons (when expanded) ─────────────────
            if sec.collapsed:
                continue

            for item in sec.items:
                is_active = (item.key == active_tool)
                # Background
                if is_active:
                    ibg = tuple(min(255, c // 3) for c in item.color)
                elif item.hover:
                    ibg = tuple(min(255, c // 5) for c in item.color)
                else:
                    ibg = PANEL_BG
                brd = item.color if (is_active or item.hover) else PANEL_BORDER

                pygame.draw.rect(surf, ibg, item.rect, border_radius=3)
                pygame.draw.rect(surf, brd, item.rect, 1, border_radius=3)

                # Icon dot
                dot_col = item.color
                pygame.draw.circle(surf, dot_col,
                                   (item.rect.x + 12, item.rect.centery), 4)
                # Label
                txt_col = item.color if (is_active or item.hover) else DIM
                draw_text(surf, item.label,
                          item.rect.x + 22, item.rect.centery,
                          fonts['xs'], txt_col, 'midleft')

        # Restore clipping
        surf.set_clip(old_clip)

        # ── Simulation status badge ────────────────────────────
        if runner and runner.is_running:
            col    = SAFE if not runner.is_paused else WARN
            label  = 'SIM' if not runner.is_paused else 'PAUSA'
            bx, by = self.rect.right - 48, self.rect.y + 4
            pygame.draw.circle(surf, col, (bx, by + 7), 5)
            draw_text(surf, label, bx + 8, by + 2, fonts['xs'], col)

        # ── Error flash ────────────────────────────────────────
        if runner and runner.error_msg:
            er = pygame.Rect(self.PAD, self.rect.bottom - 46,
                             self.rect.w - self.PAD * 2, 40)
            pygame.draw.rect(surf, (35, 8, 12), er, border_radius=4)
            pygame.draw.rect(surf, DANGER, er, 1, border_radius=4)
            draw_text(surf, 'ERR', er.x + 5, er.y + 4, fonts['xs'], DANGER)
            msg = (runner.error_msg[:24] + '…'
                   if len(runner.error_msg) > 24 else runner.error_msg)
            draw_text(surf, msg, er.x + 5, er.y + 18, fonts['xs'], WHITE)

        # ── Wire-drawing tip ───────────────────────────────────
        if active_tool == 'WIRE':
            tip_r = pygame.Rect(self.PAD, self.rect.bottom - 50,
                                self.rect.w - self.PAD * 2, 44)
            pygame.draw.rect(surf, (15, 22, 38), tip_r, border_radius=4)
            pygame.draw.rect(surf, WIRE_COL, tip_r, 1, border_radius=4)
            for i, line in enumerate(['Clic: inicio/punto', 'Clic der: finalizar', 'ESC: cancelar']):
                draw_text(surf, line, tip_r.x + 5, tip_r.y + 4 + i * 13,
                          fonts['xs'], WIRE_COL)

        # ── Scroll indicator ───────────────────────────────────
        if self._total_h > self.rect.h:
            bar_h   = max(20, int(self.rect.h ** 2 / self._total_h))
            bar_y   = self.rect.y + int(
                self._scroll_y / self._total_h * self.rect.h)
            bar_r   = pygame.Rect(self.rect.right - 5, bar_y, 4, bar_h)
            pygame.draw.rect(surf, (50, 65, 90), bar_r, border_radius=2)

        # ── Keyboard shortcuts reminder ────────────────────────
        draw_text(surf, '[R] rotar  [DEL] borrar',
                  self.rect.x + 4, self.rect.bottom - 14,
                  fonts['xs'], (35, 45, 65))
