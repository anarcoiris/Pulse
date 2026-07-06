"""
ui/properties.py
================
Panel derecho: editor de propiedades del componente seleccionado.
Incluye un TextInput simple para editar valores y nombres de nodos.
"""

import pygame
from ui.theme import (
    PROPS_W, CANVAS_Y, CANVAS_H, W, H, STATUS_H,
    ACCENT, WARN, DANGER, SAFE, DIM, WHITE,
    PANEL_BG, PANEL_BORDER, COMP_COLORS, SELECT_COL,
    draw_text, draw_panel,
)
from ui.editor import PlacedComponent, CircuitGraph, SimulationRunner


# ─── TextInput ─────────────────────────────────────────────────────────────────

class TextInput:
    """
    Campo de texto editable simple.
    Maneja eventos de teclado cuando esta activo (self.active = True).
    """

    def __init__(self, rect: pygame.Rect, initial: str = '', max_len: int = 500):
        self.rect    = rect
        self.text    = str(initial)
        self.active  = False
        self.max_len = max_len
        self._cursor_t   = 0.0
        self._cursor_vis = True

    def handle_event(self, event) -> bool:
        """Returns True if event was consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            return self.active

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                self.active = False
            elif len(self.text) < self.max_len:
                self.text += event.unicode
            return True

        return False

    def update(self, dt: float) -> None:
        self._cursor_t += dt
        if self._cursor_t > 0.5:
            self._cursor_vis = not self._cursor_vis
            self._cursor_t   = 0.0

    def draw(self, surf: pygame.Surface, font) -> None:
        bg  = (30, 42, 65) if self.active else (20, 27, 42)
        brd = ACCENT       if self.active else PANEL_BORDER
        pygame.draw.rect(surf, bg,  self.rect, border_radius=3)
        pygame.draw.rect(surf, brd, self.rect, 1, border_radius=3)
        label = self.text + ('|' if self.active and self._cursor_vis else '')
        img   = font.render(label, True, WHITE)
        
        # Clipping horizontal if text is too long
        tw, th = img.get_size()
        tx = self.rect.x + 5
        if tw > self.rect.w - 10:
            # Shift to the left so the end of text is visible
            tx = self.rect.x + (self.rect.w - 5 - tw)
        
        # Use a subsurface or clip rect for better look
        old_clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-4, -4))
        surf.blit(img, (tx, self.rect.y + (self.rect.h - th) // 2))
        surf.set_clip(old_clip)

    @property
    def float_val(self) -> float:
        try:
            return float(self.text)
        except ValueError:
            return 0.0

    @property
    def str_val(self) -> str:
        return self.text.strip()


# ─── PropertiesPanel ──────────────────────────────────────────────────────────

class PropertiesPanel:
    """
    Panel derecho que muestra y permite editar las propiedades del componente
    actualmente seleccionado en el canvas.

    Para cada campo editable se crea un TextInput. Los cambios se aplican
    al hacer clic en [Aplicar] o al seleccionar otro componente.
    """

    PAD = 8
    ROW = 28
    INP_H = 22

    def __init__(self):
        rx = W - PROPS_W
        ry = CANVAS_Y
        self.rect = pygame.Rect(rx, ry, PROPS_W, CANVAS_H)
        self._uid: str = ''
        self._inputs: dict = {}    # label → TextInput
        self._apply_rect   = pygame.Rect(0, 0, 0, 0)
        self._delete_rect  = pygame.Rect(0, 0, 0, 0)
        self._apply_hover  = False
        self._delete_hover = False

    def load_component(self, comp: PlacedComponent | None) -> None:
        """Carga los campos del componente seleccionado."""
        self._inputs.clear()
        if comp is None:
            self._uid = ''
            return
        self._uid = comp.uid
        iw = self.rect.width - self.PAD * 2 - 60
        ix = self.rect.x + 60
        iy = self.rect.y + 70

        def field(label: str, value: str) -> TextInput:
            nonlocal iy
            inp = TextInput(pygame.Rect(ix, iy, iw, self.INP_H), str(value))
            self._inputs[label] = inp
            iy += self.ROW
            return inp

        field('n1',   comp.n1)
        field('n2',   comp.n2)
        field('valor', self._fmt_value(comp))
        field('label', comp.label)

        if comp.etype == 'S':
            field('R_on',  comp.R_on)
            field('R_off', comp.R_off)

        # Add footprint selector info for ALL components
        default_fp = comp.footprint_id or ''
        if not default_fp and comp.etype == 'S':
            default_fp = 'tactile_switch_6x6'
        
        self._inputs['footprint'] = TextInput(pygame.Rect(ix, iy, iw, self.INP_H), default_fp)
        iy += self.ROW

        iy += 4
        bw  = (self.rect.width - self.PAD * 3) // 2
        self._apply_rect  = pygame.Rect(self.rect.x + self.PAD,       iy, bw, 26)
        self._delete_rect = pygame.Rect(self.rect.x + self.PAD + bw + self.PAD, iy, bw, 26)

    def _fmt_value(self, comp: PlacedComponent) -> str:
        if isinstance(comp.value, str):
            return comp.value
        if comp.etype in ('C', 'L'):
            return f"{comp.value:.6g}"
        return f"{comp.value:.4g}"

    def apply_changes(self, graph: CircuitGraph,
                      runner: SimulationRunner) -> PlacedComponent | None:
        """Aplica los valores editados. Devuelve el componente actualizado."""
        comp = graph.get(self._uid)
        if comp is None:
            return None
        if 'n1'    in self._inputs: comp.n1    = self._inputs['n1'].str_val or comp.n1
        if 'n2'    in self._inputs: comp.n2    = self._inputs['n2'].str_val or comp.n2
        if 'label' in self._inputs: comp.label = self._inputs['label'].str_val or comp.label
        if 'valor' in self._inputs:
            if isinstance(comp.value, str):
                comp.value = self._inputs['valor'].str_val
            else:
                v = self._inputs['valor'].float_val
                if v != 0 or comp.etype in ('S', 'GND'): comp.value = v
        if 'R_on'  in self._inputs: comp.R_on  = max(1e-6, self._inputs['R_on'].float_val)
        if 'R_off' in self._inputs: comp.R_off = max(1.0,  self._inputs['R_off'].float_val)
        if 'footprint' in self._inputs: comp.footprint_id = self._inputs['footprint'].str_val
        # Reload simulator to reflect topology changes
        runner.load(graph)
        return comp

    # ── Events ──────────────────────────────────────────────────

    def handle_event(self, event, graph: CircuitGraph,
                     runner: SimulationRunner) -> str | None:
        """Returns 'apply' | 'delete' | None."""
        for inp in self._inputs.values():
            inp.handle_event(event)

        if event.type == pygame.MOUSEMOTION:
            self._apply_hover  = self._apply_rect.collidepoint(event.pos)
            self._delete_hover = self._delete_rect.collidepoint(event.pos)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._apply_rect.collidepoint(event.pos) and self._uid:
                self.apply_changes(graph, runner)
                return 'apply'
            if self._delete_rect.collidepoint(event.pos) and self._uid:
                graph.remove(self._uid)
                runner.load(graph)
                self.load_component(None)
                return 'delete'
        return None

    def update(self, dt: float) -> None:
        for inp in self._inputs.values():
            inp.update(dt)

    # ── Drawing ──────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, fonts: dict,
             comp: PlacedComponent | None, runner: SimulationRunner) -> None:
        draw_panel(surf, self.rect, 'PROPIEDADES', fonts['sm'])

        if comp is None:
            draw_text(surf, 'Ninguno seleccionado.',
                      self.rect.centerx, self.rect.y + 60,
                      fonts['xs'], DIM, 'midtop')
            self._draw_hint(surf, fonts)
            return

        col = COMP_COLORS.get(comp.etype, WHITE)

        # Component header
        hdr_r = pygame.Rect(self.rect.x + self.PAD, self.rect.y + 26,
                            self.rect.w - self.PAD * 2, 30)
        pygame.draw.rect(surf, tuple(min(255, c//4) for c in col), hdr_r, border_radius=4)
        pygame.draw.rect(surf, col, hdr_r, 1, border_radius=4)
        draw_text(surf, f'{comp.etype}  {comp.uid}',
                  hdr_r.centerx, hdr_r.centery, fonts['bold'], col, 'center')

        # Field labels
        iy = self.rect.y + 70
        labels = ['n1', 'n2', 'valor', 'label']
        if comp.etype == 'S':
            labels += ['R_on', 'R_off']
        labels.append('footprint')
        hints = {
            'n1':    'Nodo +',
            'n2':    'Nodo -',
            'valor': 'Valor',
            'label': 'Etiqueta',
            'R_on':  'R_on (Ω)',
            'R_off': 'R_off (Ω)',
            'footprint': 'Huella PCB',
        }
        for lbl in labels:
            draw_text(surf, hints.get(lbl, lbl), self.rect.x + self.PAD + 4, iy + 4,
                      fonts['xs'], DIM)
            if lbl in self._inputs:
                self._inputs[lbl].draw(surf, fonts['xs'])
            iy += self.ROW

        # Switch state indicator
        if comp.etype == 'S':
            iy += 4
            scol = SAFE if comp.is_closed else WARN
            slabel = '● CERRADO' if comp.is_closed else '○ ABIERTO'
            draw_text(surf, slabel, self.rect.centerx, iy, fonts['bold'], scol, 'midtop')
            iy += 20

        # Apply / Delete buttons
        if self._apply_rect.w > 0:
            acol = ACCENT if self._apply_hover else PANEL_BORDER
            dcol = DANGER if self._delete_hover else PANEL_BORDER
            abg  = (0, 40, 30) if self._apply_hover else PANEL_BG
            dbg  = (40, 10, 15) if self._delete_hover else PANEL_BG

            pygame.draw.rect(surf, abg, self._apply_rect, border_radius=4)
            pygame.draw.rect(surf, acol, self._apply_rect, 1, border_radius=4)
            draw_text(surf, '✔ Aplicar', self._apply_rect.centerx, self._apply_rect.centery,
                      fonts['sm'], ACCENT if self._apply_hover else DIM, 'center')

            pygame.draw.rect(surf, dbg, self._delete_rect, border_radius=4)
            pygame.draw.rect(surf, dcol, self._delete_rect, 1, border_radius=4)
            draw_text(surf, '✖ Eliminar', self._delete_rect.centerx, self._delete_rect.centery,
                      fonts['sm'], DANGER if self._delete_hover else DIM, 'center')

        # Live metrics for selected node
        self._draw_metrics(surf, fonts, comp, runner)

    def _draw_metrics(self, surf, fonts, comp: PlacedComponent,
                      runner: SimulationRunner) -> None:
        if not runner.is_running:
            return
        y = self.rect.y + self.rect.h - 140
        draw_text(surf, '─ MEDICION EN VIVO', self.rect.x + self.PAD, y,
                  fonts['xs'], (55, 70, 95))
        y += 16
        v1 = runner.get_voltage(comp.n1)
        v2 = runner.get_voltage(comp.n2)
        vd = v1 - v2
        rows = [
            (f'{comp.n1}:', f'{v1:+.1f} V'),
            (f'{comp.n2}:', f'{v2:+.1f} V'),
            ('V_diff:',     f'{vd:+.1f} V'),
        ]
        for label, val in rows:
            draw_text(surf, label, self.rect.x + self.PAD + 4, y, fonts['xs'], DIM)
            draw_text(surf, val, self.rect.right - self.PAD - 4, y, fonts['xs'], ACCENT, 'topright')
            y += 18

        t = runner.sim_time
        draw_text(surf, f't_sim: {t*1000:.3f} ms', self.rect.x + self.PAD, y + 6,
                  fonts['xs'], DIM)

    def _draw_hint(self, surf, fonts) -> None:
        hints = [
            'Clic → seleccionar',
            '[R] → rotar componente',
            '[DEL] → borrar',
            'Clic en ⚡ → toggle',
        ]
        y = self.rect.y + 100
        for h in hints:
            draw_text(surf, h, self.rect.centerx, y, fonts['xs'], (45, 55, 75), 'midtop')
            y += 18
