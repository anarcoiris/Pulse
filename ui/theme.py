"""
ui/theme.py
===========
PulseLab design system.

Centraliza toda la paleta visual (colores, layout, fuentes) eliminando
la duplicación entre emp_simulator.py y ai_studio_code.py.
"""

import pygame
from typing import Tuple

# ─── Window ───────────────────────────────────────────────────────────────────
W, H  = 1400, 900
FPS   = 60

# ─── Panel layout ─────────────────────────────────────────────────────────────
TOOLBAR_W = 200     # Left toolbar width
PROPS_W   = 230     # Right properties panel width
TITLE_H   = 50      # Top title bar
STATUS_H  = 28      # Bottom status bar
OSC_H     = 220     # Oscilloscope at bottom

# Derived
CANVAS_X = TOOLBAR_W
CANVAS_Y = TITLE_H
CANVAS_W = W - TOOLBAR_W - PROPS_W          # 970
CANVAS_H = H - TITLE_H - STATUS_H - OSC_H  # 602
OSC_Y    = CANVAS_Y + CANVAS_H              # 652
STATUS_Y = OSC_Y + OSC_H                    # 872

GRID_SIZE = 40   # pixels per grid cell

# Grid dimensions
GRID_COLS = CANVAS_W // GRID_SIZE   # 24
GRID_ROWS = CANVAS_H // GRID_SIZE   # 15

# ─── Color palette ─────────────────────────────────────────────────────────────
BG           = ( 10,  12,  18)
GRID_COL     = ( 20,  25,  36)
ACCENT       = (  0, 220, 160)
ACCENT2      = (  0, 160, 255)
WARN         = (255, 160,  30)
DANGER       = (220,  40,  60)
SAFE         = ( 50, 200, 100)
DIM          = ( 75,  85, 105)
WHITE        = (230, 235, 245)
PANEL_BG     = ( 14,  17,  26)
PANEL_BORDER = ( 38,  50,  70)
SELECT_COL   = (255, 215,   0)   # gold for selection highlight
WIRE_COL     = ( 55,  85, 130)
WIRE_GND     = ( 45,  65, 100)

# Component colors by element type
COMP_COLORS: dict = {
    'R':   (255, 200,  80),
    'C':   ( 80, 200, 255),
    'L':   (200, 120, 255),
    'V':   ( 80, 255, 120),
    'S':   (255, 130,  70),
    'GND': ( 80, 100, 120),
}

# ─── Font cache ────────────────────────────────────────────────────────────────
_fonts: dict = {}


def get_fonts() -> dict:
    """Return (and cache) the font set. Must be called after pygame.init()."""
    if not _fonts:
        fam = "Consolas"
        try:
            _fonts['title'] = pygame.font.SysFont(fam, 20, bold=True)
            _fonts['bold']  = pygame.font.SysFont(fam, 14, bold=True)
            _fonts['md']    = pygame.font.SysFont(fam, 13)
            _fonts['sm']    = pygame.font.SysFont(fam, 11)
            _fonts['xs']    = pygame.font.SysFont(fam, 10)
        except Exception:
            for k in ('title', 'bold', 'md', 'sm', 'xs'):
                _fonts[k] = pygame.font.SysFont(None, 14)
    return _fonts


# ─── Drawing primitives ────────────────────────────────────────────────────────

def draw_text(surf, text: str, x: int, y: int, font,
              color: tuple = WHITE, anchor: str = "topleft",
              bg: tuple = None) -> None:
    img = font.render(str(text), True, color, bg)
    rect = img.get_rect(**{anchor: (x, y)})
    surf.blit(img, rect)


def draw_panel(surf, rect: pygame.Rect, title: str = "",
               font=None, border_col: tuple = PANEL_BORDER) -> None:
    pygame.draw.rect(surf, PANEL_BG, rect, border_radius=6)
    pygame.draw.rect(surf, border_col, rect, 1, border_radius=6)
    if title and font:
        draw_text(surf, title, rect.x + 10, rect.y + 8, font, DIM)


def lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """Linear interpolation between two colors. t is clamped to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return tuple(max(0, min(255, int(a + (b - a) * t))) for a, b in zip(c1, c2))


def glow_rect(surf, rect: pygame.Rect, color: tuple, radius: int = 6) -> None:
    """Draw a rounded rect with subtle inner glow."""
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    inner = rect.inflate(-4, -4)
    gl = tuple(min(255, int(c * 1.3)) for c in color)
    pygame.draw.rect(surf, gl, inner, 1, border_radius=radius - 2)
