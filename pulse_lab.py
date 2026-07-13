"""
pulse_lab.py
============
PulseLab — Editor de Circuitos y Simulador MNA Unificado.

Novedades en esta version:
  - Undo/Redo: Ctrl+Z / Ctrl+Y (historial de 50 pasos)
  - Zoom centrado en raton: rueda del raton sobre el canvas
  - Pan: boton central del raton arrastrado sobre el canvas
  - Herramienta WIRE: dibuja cables, fusiona nodos al conectar terminales
  - Particulas de corriente: muestran sentido de la corriente en vivo

Reemplaza emp_simulator.py y ai_studio_code.py con una aplicacion unica
que integra:
    - Editor de circuitos interactivo con cuadricula
    - Motor MNA (circuit_engine.py) para simulacion fisica rigurosa
    - Osciloscopio virtual multi-canal
    - Generacion de esquemas PDF (circuit_generator.py)
    - Guardado/carga de circuitos en formato JSON
    - Presets: EMP PFN 5kV, RC simple

Controles globales:
    [S]        Activar/desactivar simulacion (modo SELECT activo)
    [ESC]      Volver a herramienta SELECT
    [R]        Rotar orientacion de colocacion (H/V)
    [DEL]      Borrar componente seleccionado
    [← →]      Ciclar canal del osciloscopio
    [Ctrl+S]   Guardar JSON
    [Ctrl+O]   Cargar JSON
    [Ctrl+E]   Exportar PDF

Uso:
    python pulse_lab.py
    python pulse_lab.py --preset rc      # carga RC simple al inicio
"""

import sys
import os
import json
import argparse
import math
import time
import threading
import subprocess
from pathlib import Path

import pygame
import json as _json  # used for undo/redo snapshots

# ─── Inicializar pygame ANTES de importar theme ──────────────────────────────
pygame.init()

from ui.theme import (
    W, H, FPS,
    TOOLBAR_W, PROPS_W, TITLE_H, STATUS_H, OSC_H,
    CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H, OSC_Y, STATUS_Y,
    BG, GRID_COL, ACCENT, ACCENT2, WARN, DANGER, SAFE, DIM, WHITE,
    PANEL_BG, PANEL_BORDER,
    get_fonts, draw_text, draw_panel,
)
from ui.editor       import CircuitGraph, SimulationRunner, EditorCanvas, Wire
from ui.toolbar      import ToolbarPanel
from ui.properties   import PropertiesPanel
from ui.oscilloscope import OscilloscopePanel
from ui.modals       import ForgeResultModal, AIGeneratorModal, AIReviewModal
from knowledge.semantic_reviewer import SemanticAIAgent


# ─── Helpers (Imported from Forge API) ───────────────────────────────────────
from bridge.forge_api import (
    load_preset as _load_preset,
    export_pdf as _export_pdf,
    export_kicad_netlist as _export_kicad_netlist,
    generate_pcb as _generate_pcb,
    export_gerbers as _export_gerbers,
    save_json as _save_json,
    load_json as _load_json
)


# ─── Application ─────────────────────────────────────────────────────────────

class PulseLabApp:
    """
    Aplicacion principal. Ciclo de vida:
        __init__()  → inicializa subsistemas
        run()       → bucle principal pygame
    """

    DEFAULT_SAVE_PATH = 'circuit_save.json'

    def __init__(self, preset: str = 'emp_pfn'):
        # --- Window ---
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption('PulseLab — Editor de Circuitos y Simulador MNA')
        self.clock  = pygame.time.Clock()
        self.fonts  = get_fonts()

        # --- Layout rects ---
        canvas_rect = pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)

        # --- Subsystems ---
        self.graph   = _load_preset(preset)
        self.runner  = SimulationRunner()
        self.canvas  = EditorCanvas(canvas_rect, self.graph)
        self.toolbar = ToolbarPanel()
        self.props   = PropertiesPanel()
        self.osc     = OscilloscopePanel()
        
        from ui.properties import TextInput
        self.search_bar = TextInput(pygame.Rect(W - PROPS_W - 210, 36, 200, 24), '')
        self.search_active = False

        # --- State ---
        self._selected_comp  = None
        self._status_msg     = (f'PulseLab v2. Preset: {preset}.  '
                                '[R] rotar  [DEL] borrar  '
                                '[Rueda] zoom  [Boton-central] pan  '
                                '[Ctrl+Z/Y] deshacer/rehacer')
        self._status_col     = ACCENT
        self._status_timer   = 5.0
        self._flash_alpha    = 0
        self._last_save_path = self.DEFAULT_SAVE_PATH
        
        # Modals
        self.forge_modal = ForgeResultModal()
        self.ai_gen_modal = AIGeneratorModal()
        self.ai_review_modal = AIReviewModal()

        # Forge orchestration controller
        from ui.forge_controller import ForgeController
        self.forge = ForgeController(
            graph_fn=lambda: self.graph,
            status_fn=self._status,
            forge_modal=self.forge_modal,
            ai_review_modal=self.ai_review_modal,
            ai_gen_modal=self.ai_gen_modal,
            snapshot_fn=self._snapshot,
            reload_fn=self._reload_graph,
        )

        # --- Undo / Redo ---
        self._undo_stack: list = []   # list of JSON strings
        self._redo_stack: list = []
        self._MAX_HISTORY = 50

        # Initialize oscilloscope with current nodes
        self.osc.set_nodes(self.graph.all_nodes)

    # ── Main loop ─────────────────────────────────────────────

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self._handle_event(event)

            self._update(dt)
            self._draw()

        pygame.quit()

    # ── Undo / Redo ───────────────────────────────────────────

    def _snapshot(self) -> None:
        """Guarda estado actual del grafo en la pila de deshacer si hubo cambios."""
        state = _json.dumps(self.graph.to_json())
        if self._undo_stack and self._undo_stack[-1] == state:
            return  # No registrar cambios vacíos
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._MAX_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self) -> None:
        if not self._undo_stack:
            self._status('Nada que deshacer.', WARN)
            return
        current = _json.dumps(self.graph.to_json())
        prev    = self._undo_stack.pop()
        self._redo_stack.append(current)
        self.graph = CircuitGraph.from_json(_json.loads(prev))
        self._reload_graph()
        self._status(f'Deshacer.  ({len(self._undo_stack)} pasos restantes)', ACCENT)

    def _redo(self) -> None:
        if not self._redo_stack:
            self._status('Nada que rehacer.', WARN)
            return
        current    = _json.dumps(self.graph.to_json())
        next_state = self._redo_stack.pop()
        self._undo_stack.append(current)
        self.graph = CircuitGraph.from_json(_json.loads(next_state))
        self._reload_graph()
        self._status(f'Rehacer.  ({len(self._redo_stack)} pasos hacia adelante)', ACCENT)

    # ── Event handling ────────────────────────────────────────

    def _handle_event(self, event: pygame.event.Event) -> None:
        # Modals intercept events first
        if self.ai_gen_modal.handle_event(event): return
        if self.ai_review_modal.handle_event(event): return
        if self.forge_modal.handle_event(event): return

        # --- Global keyboard shortcuts ---
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            if event.key == pygame.K_ESCAPE:
                self.canvas.active_tool  = 'SELECT'
                self.canvas.selected_uid = None
                self._selected_comp      = None
                self.props.load_component(None)
                return
            if mods & pygame.KMOD_CTRL:
                if   event.key == pygame.K_s: self._action_save_json()
                elif event.key == pygame.K_o: self._action_load_json()
                elif event.key == pygame.K_e: self._action_export_pdf()
                elif event.key == pygame.K_z: self._undo()
                elif event.key == pygame.K_y: self._redo()
                elif event.key == pygame.K_f:
                    self.search_bar.active = True
                    self.search_active = True
                elif event.key == pygame.K_0: self.canvas.reset_view(); self._status('Zoom reseteado.', DIM)
                elif event.key == pygame.K_d:
                    # Ctrl+D is handled in canvas.handle_event → 'placed' action below
                    pass
                return
            # F key: canvas handles fit_to_screen internally (K_f in editor.py)
            # Just update status message here
            # F key (without Ctrl): canvas handles fit_to_screen
            if event.key == pygame.K_f and not (mods & pygame.KMOD_CTRL):
                self.canvas.fit_to_screen()
                self._status(f'Fit to screen  zoom={self.canvas.zoom:.2f}x', DIM)

        # --- Properties panel ---
        # Before handling event, we might need a snapshot if the panel mutates
        # Since PropertiesPanel currently mutates directly, we'd need a change-detector.
        # Temp fix: snapshot before calling handle_event if it's a mouse click or enter
        if event.type == pygame.MOUSEBUTTONDOWN or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
            # Optimización: solo snapshot si el puntero está sobre el panel o escribiendo
            self._snapshot()

        action = self.props.handle_event(event, self.graph, self.runner)
        if action == 'delete':
            # Snapshot already taken above
            self._selected_comp      = None
            self.canvas.selected_uid = None
            self.osc.set_nodes(self.graph.all_nodes)
            self._status('Componente eliminado.', WARN)
            return
        if action == 'apply':
            self._status('Cambios aplicados.', SAFE)
            return

        # --- Toolbar ---
        # Toolbar actions (SELECT, R, C...) don't mutate graph yet, no snapshot needed
        tb_action = self.toolbar.handle_event(event, self.runner, self.runner.dt_label)
        if tb_action:
            self._handle_toolbar(tb_action)
            return

        # --- Oscilloscope ---
        self.osc.handle_event(event, self.graph.all_nodes)

        # --- Canvas ---
        # IMPORTANTE: Tomar snapshot ANTES de mutaciones en el canvas
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.canvas.active_tool != 'SELECT':
                self._snapshot()

        result = self.canvas.handle_event(event, self.runner)
        if result:
            act  = result['action']
            comp = result.get('comp')
            if act == 'selected':
                self._selected_comp = comp
                self.props.load_component(comp)
            elif act == 'wire_selected':
                self._selected_comp = None
                self.props.load_component(None)
            elif act in ('wire_placed', 'wire_point'):
                if act == 'wire_placed': self._snapshot() # Snapshot logic after completion too
                self.osc.set_nodes(self.graph.all_nodes)
            elif act == 'deselected':
                self._selected_comp = None
                self.props.load_component(None)
            elif act == 'placed':
                # Snapshot ya tomado antes o tomado al finalizar
                self._selected_comp = comp
                self.props.load_component(comp)
                self.osc.set_nodes(self.graph.all_nodes)
                if comp:
                    self._status(f'Colocado: {comp.uid} ({comp.grid_c},{comp.grid_r})', ACCENT)
            elif act == 'deleted':
                # Snapshot ya tomado en el trigger
                self._selected_comp = None
                self.osc.set_nodes(self.graph.all_nodes)
                self._status('Eliminado.', WARN)

        # --- Search Bar ---
        if self.search_bar.handle_event(event):
            self.canvas.search_term = self.search_bar.text
            return

    def _handle_toolbar(self, action: str) -> None:
        """Procesa acciones del toolbar."""

        # ── Component placement tools ────────────────────────
        if action in ('SELECT', 'R', 'C', 'L', 'V', 'S', 'GND', 'WIRE'):
            self.canvas.active_tool = action
            msg = f'Herramienta: {action}'
            if action == 'WIRE':
                msg += '  |  Clic=punto  Clic-der=finalizar  ESC=cancelar'
            else:
                msg += '  |  [R] rotar'
            self._status(msg, DIM)
            return

        # ── Presets ──────────────────────────────────────────
        if action == 'PRESET_emp_pfn':
            self._snapshot()
            self.graph = _load_preset('emp_pfn')
            self._reload_graph()
            self._status('Preset cargado: EMP PFN 5kV', ACCENT)
            return
        if action == 'PRESET_basic_rc':
            self._snapshot()
            self.graph = _load_preset('basic_rc')
            self._reload_graph()
            self._status('Preset cargado: RC Simple', ACCENT)
            return
        if action == 'PRESET_rlc':
            self._snapshot()
            self.graph = _load_preset('rlc')
            self._reload_graph()
            self._status('Preset cargado: RLC Serie', ACCENT)
            return

        # ── Simulation controls ──────────────────────────────
        if action == 'SIM_START':
            ok = self.runner.load(self.graph)
            self.osc.set_nodes(self.graph.all_nodes)
            if ok:
                self._status('Simulacion iniciada.', SAFE)
            else:
                self._status(f'ERROR: {self.runner.error_msg}', DANGER)
            return
        if action == 'SIM_PAUSE':
            self.runner.pause()
            state = 'pausada' if self.runner.is_paused else 'reanudada'
            self._status(f'Simulacion {state}.', WARN)
            return
        if action == 'SIM_RESET':
            self.runner.reset()
            self._status('Estado de simulacion reiniciado.', ACCENT)
            return
        if action == 'CYCLE_DT':
            self.runner.cycle_dt()
            self._status(f'dt = {self.runner.dt_label}', DIM)
            return

        # ── IO ───────────────────────────────────────────────
        if action == 'SAVE_JSON':
            self._action_save_json()
            return
        if action == 'LOAD_JSON':
            self._snapshot()
            self._action_load_json()
            return
        if action == 'EXPORT_PDF':
            self._action_export_pdf()
            return
        if action == 'CLEAR':
            self._snapshot()
            self.graph.clear()
            self._reload_graph()
            self._status('Canvas limpiado.  Ctrl+Z para deshacer.', WARN)
            return

        # ── Forge (KiCad / PCB / Gerbers) — delegated to ForgeController ──
        if action == 'FORGE_EXPORT_KICAD':
            self.forge.export_kicad()
            return
        if action == 'FORGE_GEN_PCB':
            self.forge.gen_pcb()
            return
        if action == 'FORGE_ENCLOSURE':
            self.forge.gen_enclosure()
            return
        if action == 'FORGE_REVIEW':
            self.forge.review_ai()
            return
        if action == 'FORGE_GERBERS':
            self.forge.export_gerbers()
            return
        if action == 'FORGE_KICAD_STATUS':
            self.forge.kicad_status()
            return
        if action == 'FORGE_GEN_AI':
            self.forge.gen_ai()
            return
            
        # ── System ───────────────────────────────────────────
        if action == 'SYS_LAUNCH_MCP':
            self._action_sys_launch_mcp()
            return
        if action == 'SYS_LAUNCH_OLLAMA':
            self._action_sys_launch_ollama()
            return
        if action == 'SYS_UPDATE_DEPS':
            self._action_sys_update_deps()
            return

    def _action_save_json(self) -> None:
        try:
            _save_json(self.graph, self._last_save_path)
            self._status(f'Guardado: {self._last_save_path}', SAFE)
        except Exception as e:
            self._status(f'Error guardando: {e}', DANGER)

    def _action_load_json(self) -> None:
        try:
            self.graph = _load_json(self._last_save_path)
            self._reload_graph()
            self._status(f'Cargado: {self._last_save_path}', SAFE)
        except Exception as e:
            self._status(f'Error cargando: {e}', DANGER)

    def _action_export_pdf(self) -> None:
        try:
            path = _export_pdf(self.graph)
            self._status(f'PDF exportado: {path}', ACCENT2)
        except Exception as e:
            self._status(f'Error exportando: {e}', DANGER)

    # ── Forge Actions — delegated to ForgeController (ui/forge_controller.py) ──
    #    All _action_forge_* methods have been extracted to ForgeController.


    def _reload_graph(self) -> None:
        """Actualiza canvas, props y osc tras cambiar self.graph."""
        self.canvas.graph        = self.graph
        self.canvas.selected_uid = None
        self._selected_comp      = None
        self.props.load_component(None)
        self.osc.set_nodes(self.graph.all_nodes)
        if self.runner.is_running:
            self.runner.load(self.graph)

    def _status(self, msg: str, col: tuple = WHITE, duration: float = 4.0) -> None:
        self._status_msg   = msg
        self._status_col   = col
        self._status_timer = duration

    # ── Update ─────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        self.runner.step()
        self.props.update(dt)
        self.search_bar.update(dt)
        # Update current particles
        self.canvas.particles.update(dt, self.graph, self.runner)
        if self._flash_alpha > 0:
            self._flash_alpha = max(0, self._flash_alpha - 8)
        if self._status_timer > 0:
            self._status_timer -= dt

    # ── Drawing ────────────────────────────────────────────────

    def _draw(self) -> None:
        surf = self.screen
        surf.fill(BG)

        # Title bar
        self._draw_title(surf)

        # Canvas
        self.canvas.draw(surf, self.fonts, self.runner)

        # Toolbar
        self.toolbar.draw(surf, self.fonts,
                          self.canvas.active_tool,
                          self.runner,
                          self.runner.dt_label)

        # Properties panel
        self.props.draw(surf, self.fonts, self._selected_comp, self.runner)

        # Oscilloscope
        self.osc.draw(surf, self.fonts, self.runner)

        # Status bar
        self._draw_status(surf)

        # Flash overlay (e.g., after firing)
        if self._flash_alpha > 0:
            flash = pygame.Surface((W, H), pygame.SRCALPHA)
            flash.fill((220, 40, 60, self._flash_alpha))
            surf.blit(flash, (0, 0))

        # Modals
        self.ai_review_modal.draw(surf, self.fonts)
        self.forge_modal.draw(surf, self.fonts)
        self.ai_gen_modal.draw(surf, self.fonts)

        pygame.display.flip()

    def _draw_title(self, surf: pygame.Surface) -> None:
        title_r = pygame.Rect(0, 0, W, TITLE_H)
        draw_panel(surf, title_r, border_col=(28, 35, 52))

        draw_text(surf,
                  '■  PulseLab Forge  |  Editor + Simulador + PCB',
                  TOOLBAR_W + 6, 14, self.fonts['title'], ACCENT)

        # Right side: tool + sim info
        tool = self.canvas.active_tool
        orient = self.canvas.place_orient
        fps  = self.clock.get_fps()
        n    = len(self.graph.components)
        undo_info = f'U:{len(self._undo_stack)} R:{len(self._redo_stack)}'
        info = (f't={self.runner.sim_time*1000:7.3f}ms  '
                f'dt={self.runner.dt_label}  '
                f'n={n}  '
                f'zoom={self.canvas.zoom:.1f}x  '
                f'{undo_info}  '
                f'fps={fps:.0f}')
        draw_text(surf, info, W - PROPS_W - 10, 8, self.fonts['xs'], DIM, 'topright')

        # Active tool badge
        tcol = ACCENT if tool == 'SELECT' else WARN
        draw_text(surf, f'Herramienta: {tool} [{orient}]',
                  W - PROPS_W - 220, 24, self.fonts['xs'], tcol, 'topright')

        # Search bar drawing
        self.search_bar.draw(surf, self.fonts['xs'])
        if not self.search_bar.text and not self.search_bar.active:
            draw_text(surf, 'Buscar (Ctrl+F)...', self.search_bar.rect.x + 5, 
                      self.search_bar.rect.centery, self.fonts['xs'], (60, 80, 100), 'midleft')

    def _draw_status(self, surf: pygame.Surface) -> None:
        sr = pygame.Rect(0, STATUS_Y, W, STATUS_H)
        pygame.draw.rect(surf, (8, 10, 16), sr)
        pygame.draw.rect(surf, PANEL_BORDER, sr, 1)

        msg = self._status_msg if self._status_timer > 0 else 'PulseLab — listo.'
        col = self._status_col if self._status_timer > 0 else DIM

        draw_text(surf, msg, 10, sr.y + 7, self.fonts['xs'], col)

        # Shortcuts reminder
        draw_text(surf,
                  '[Rueda] zoom  [Btn-central] pan  [Ctrl+0] reset  '
                  '[Ctrl+Z/Y] undo/redo  [Ctrl+S/O] save/load  [WIRE] cable',
                  W - 10, sr.y + 7, self.fonts['xs'], (40, 50, 70), 'topright')

    # --- (End of drawing methods) ---


# ─── Entry point ──────────────────────────────────────────────────────────────

    # ── System Actions ─────────────────────────────────────────

    def _action_sys_launch_mcp(self) -> None:
        try:
            # On Windows, creationflags=subprocess.CREATE_NEW_CONSOLE opens a new window
            cmd = [sys.executable, "mcp_server/server.py"]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            self._status("MCP Server lanzado en nueva consola.", SAFE)
        except Exception as e:
            self._status(f"Error lanzando MCP: {e}", DANGER)

    def _action_sys_launch_ollama(self) -> None:
        try:
            # Intentar arrancar el contenedor existente
            subprocess.Popen(["docker", "start", "symmetry_ollama"])
            self._status("Intentando arrancar contenedor symmetry_ollama...", ACCENT)
        except Exception as e:
            self._status(f"Error Docker: {e}", DANGER)

    def _action_sys_update_deps(self) -> None:
        def task():
            try:
                self._status("Actualizando dependencias (pip)...", DIM)
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
                self._status("Dependencias actualizadas correctamente.", SAFE)
            except Exception as e:
                self._status(f"Error pip: {e}", DANGER)
        
        threading.Thread(target=task, daemon=True).start()

def main():
    parser = argparse.ArgumentParser(description='PulseLab — Circuit Editor & MNA Simulator')
    parser.add_argument('--preset', default='emp_pfn',
                        choices=['emp_pfn', 'basic_rc', 'rlc', 'mcu'],
                        help='Preset inicial (default: emp_pfn)')
    args = parser.parse_args()

    app = PulseLabApp(preset=args.preset)
    app.run()


if __name__ == '__main__':
    main()
