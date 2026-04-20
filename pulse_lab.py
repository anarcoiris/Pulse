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
from ui.editor       import CircuitGraph, SimulationRunner, EditorCanvas
from ui.toolbar      import ToolbarPanel
from ui.properties   import PropertiesPanel
from ui.oscilloscope import OscilloscopePanel
from ui.editor import CircuitGraph, Wire
from knowledge.semantic_reviewer import SemanticAIAgent


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_preset(name: str) -> CircuitGraph:
    """Carga un preset por nombre ('emp_pfn' | 'basic_rc' | 'rlc')."""
    if name == 'basic_rc':
        from presets.basic_rc import load
    elif name == 'rlc':
        from presets.rlc import load
    elif name == 'mcu':
        from presets.mcu_uart import load
    else:
        from presets.emp_pfn import load
    return load()


def _export_pdf(graph: CircuitGraph, out_dir: str = os.path.join('docs', 'latex_fix')) -> str:
    """
    Genera PDF y PNG usando circuit_generator.py.
    Devuelve el path del PDF generado.
    """
    import matplotlib
    matplotlib.use('Agg')
    from circuit_generator import generate_from_simulator
    sim = graph.to_simulator()
    pdf_path, _ = generate_from_simulator(sim, output_dir=out_dir,
                                          basename='circuit_custom')
    return pdf_path


def _export_kicad_netlist(graph: CircuitGraph, out_dir: str = 'output') -> dict:
    """Genera netlist KiCad + script SKiDL + BOM desde el circuito actual."""
    from bridge.kicad_bridge import KiCadBridge
    bridge = KiCadBridge()
    return bridge.generate_netlist(graph, output_dir=out_dir, project_name='pulselab_design')


def _generate_pcb(graph: CircuitGraph, out_dir: str = 'output') -> dict:
    """Genera un .kicad_pcb con los componentes del circuito actual."""
    from bridge.pcb_layout import PCBLayout

    comps = graph.components
    n = len(comps)
    # Auto-size board based on component count
    cols = max(2, int(n ** 0.5) + 1)
    w = max(30, cols * 15)
    h = max(20, (n // cols + 2) * 12)

    pcb = PCBLayout(board_width=w, board_height=h,
                    corner_radius=1.5, project_name='PulseLab Design')

    # Place components in a grid
    row, col = 0, 0
    margin_x, margin_y = 8.0, 8.0
    spacing_x, spacing_y = 12.0, 10.0

    for c in comps:
        x = margin_x + col * spacing_x
        y = margin_y + row * spacing_y
        etype = c.etype
        ref   = c.uid
        val   = f"{c.value:.6g}" if isinstance(c.value, float) else str(c.value)

        if etype in ('R',):
            pcb.add_resistor(ref, val, x, y, net1=c.n1, net2=c.n2)
        elif etype in ('C',):
            pcb.add_capacitor(ref, val, x, y, net1=c.n1, net2=c.n2)
        elif etype in ('L',):
            pcb.add_inductor(ref, val, x, y, net1=c.n1, net2=c.n2)
        elif etype in ('V',):
            pcb.add_pin_header(ref, 2, x, y, value=f"{val}V")
        elif etype in ('IC', 'MCU'):
            pkg = "SOP16"
            if "ESP" in val.upper() or "NODE" in val.upper(): pkg = "ESP12"
            if "CH340" in val.upper() or "SOP8" in val.upper(): pkg = "SOP8"
            pcb.add_ic(ref, val, x, y, pins=getattr(c, 'pins', {}), pkg_type=pkg)
        else:
            pcb.add_pin_header(ref, 2, x, y, value=etype)

        col += 1
        if col >= cols:
            col = 0
            row += 1

    if n >= 4:
        pcb.add_mounting_holes_corners(margin=3.0)

    pcb.add_text('PulseLab Forge', pcb.board.center_x,
                 pcb.board.origin_y + pcb.board.height_mm + 2, size=0.8)

    # Añadir plano de masa si existe el nodo GND
    if "GND" in graph.all_nodes:
        pcb.add_copper_pour("GND", margin=1.0)
        
    # Ejecutar nuestro A* auto-router 2D/2L
    pcb.autoroute(width=0.25, grid_size=0.25)

    # Exportar Schematic (.kicad_sch)
    from bridge.schematic_generator import SchematicGenerator
    sch_path = Path(out_dir) / 'pulselab_pcb' / 'board.kicad_sch'
    sch_gen = SchematicGenerator(graph)
    sch_gen.save(str(sch_path))

    # Exportar PCB y KiCad Pro
    out_path = Path(out_dir) / 'pulselab_pcb' / 'board.kicad_pcb'
    pcb.save(out_path)
    
    return {'path': str(out_path), 'stats': pcb.stats(), 'pcb': pcb, 'sch_path': str(sch_path)}


def _export_gerbers(pcb_path: str = None) -> dict:
    """Exporta Gerbers + Drill desde un .kicad_pcb."""
    from bridge.kicad_bridge import KiCadBridge
    from bridge.gerber_export import generate_all_manufacturing_files
    from pathlib import Path

    bridge = KiCadBridge()
    if not bridge.available:
        return {'error': 'KiCad no encontrado'}

    if pcb_path is None:
        pcb_path = 'output/pulselab_pcb/board.kicad_pcb'
    pcb = Path(pcb_path)
    if not pcb.exists():
        return {'error': f'PCB no encontrado: {pcb_path}. Genera primero con FORGE > Generar PCB.'}

    return generate_all_manufacturing_files(bridge._cli, pcb, pcb.parent / 'manufacturing')


def _save_json(graph: CircuitGraph, path: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(graph.to_json(), f, indent=2)


def _load_json(path: str) -> CircuitGraph:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return CircuitGraph.from_json(data)


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
        self._ai_popup       = None
        self._forge_popup    = None

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
        """Guarda estado actual del grafo en la pila de deshacer."""
        state = _json.dumps(self.graph.to_json())
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
        # --- FORGE Result Popup ---
        if self._forge_popup and self._forge_popup.get("visible"):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._ai_popup and self._ai_popup.get("visible"):
                    pass # AI popup has precedence if both somehow open
                elif self._forge_popup["close_rect"].collidepoint(event.pos):
                    self._forge_popup["visible"] = False
                elif self._forge_popup.get("dir_rect") and self._forge_popup["dir_rect"].collidepoint(event.pos):
                    # Abrir carpeta del proyecto (Explorer)
                    os.startfile(os.path.abspath(self._forge_popup["output_dir"]))
            return

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
                elif event.key == pygame.K_0: self.canvas.reset_view(); self._status('Zoom reseteado.', DIM)
                elif event.key == pygame.K_d:
                    # Ctrl+D is handled in canvas.handle_event → 'placed' action below
                    pass
                return
            # F key: canvas handles fit_to_screen internally (K_f in editor.py)
            # Just update status message here
            if event.key == pygame.K_f:
                self.canvas.fit_to_screen()
                self._status(f'Fit to screen  zoom={self.canvas.zoom:.2f}x', DIM)

        # --- Properties panel (captures keyboard when text fields active) ---
        action = self.props.handle_event(event, self.graph, self.runner)
        if action == 'delete':
            self._selected_comp      = None
            self.canvas.selected_uid = None
            self.osc.set_nodes(self.graph.all_nodes)
            self._status('Componente eliminado.', WARN)
            return
        if action == 'apply':
            self._status('Cambios aplicados.', SAFE)
            return

        # --- Toolbar ---
        tb_action = self.toolbar.handle_event(event, self.runner, self.runner.dt_label)
        if tb_action:
            self._handle_toolbar(tb_action)
            return

        # --- Oscilloscope ---
        self.osc.handle_event(event, self.graph.all_nodes)

        # --- Canvas ---
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
                self.osc.set_nodes(self.graph.all_nodes)
            elif act == 'deselected':
                self._selected_comp = None
                self.props.load_component(None)
            elif act == 'placed':
                self._snapshot()
                self._selected_comp = comp
                self.props.load_component(comp)
                self.osc.set_nodes(self.graph.all_nodes)
                if comp:
                    self._status(f'Colocado: {comp.uid} ({comp.grid_c},{comp.grid_r})', ACCENT)
            elif act == 'deleted':
                self._snapshot()
                self._selected_comp = None
                self.osc.set_nodes(self.graph.all_nodes)
                self._status('Eliminado.', WARN)

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

        # ── Forge (KiCad / PCB / Gerbers) ────────────────────
        if action == 'FORGE_EXPORT_KICAD':
            self._action_forge_export_kicad()
            return
        if action == 'FORGE_GEN_PCB':
            self._action_forge_gen_pcb()
            return
        if action == 'FORGE_ENCLOSURE':
            self._action_forge_enclosure()
            return
        if action == 'FORGE_REVIEW':
            self._action_forge_review()
            return
        if action == 'FORGE_GERBERS':
            self._action_forge_gerbers()
            return
        if action == 'FORGE_KICAD_STATUS':
            self._action_forge_kicad_status()
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

    # ── Forge Actions ─────────────────────────────────────────

    def _action_forge_export_kicad(self) -> None:
        try:
            result = _export_kicad_netlist(self.graph)
            if 'error' in result:
                self._status(f'Forge: {result["error"]}', DANGER)
            else:
                num_files = sum(1 for k in ['netlist', 'skidl_script', 'bom_csv'] if k in result)
                self._status(f'KiCad: {num_files} archivos → output/', (0, 200, 180))
        except Exception as e:
            self._status(f'Forge error: {e}', DANGER)

    def _action_forge_gen_pcb(self) -> None:
        try:
            n = len(self.graph.components)
            if n == 0:
                self._status('Sin componentes. Dibuja un circuito primero.', WARN)
                return
            
            # 1. Generación de Proyectos (PCB + SCH + Netlist)
            result = _generate_pcb(self.graph)
            if 'error' in result:
                self._status(f'PCB error: {result["error"]}', DANGER)
                return

            stats = result.get('stats', {})
            pcb_path = result['path']
            
            # 2. Renderizado 3D (Async)
            from bridge.render_engine import RenderEngine3D
            renderer = RenderEngine3D()
            renderer_callback = None
            
            # 3. Síntesis de Firmware (si hay MCUs)
            fw_info = None
            has_mcu = any(c.etype in ('IC', 'MCU') for c in self.graph.components)
            if has_mcu:
                from knowledge.firmware_synthesizer import FirmwareSynthesizer
                synth = FirmwareSynthesizer()
                fw_path = Path(pcb_path).parent / 'main.py'
                fw_res = synth.generate_firmware(self.graph, str(fw_path))
                if 'path' in fw_res:
                    fw_info = str(fw_path)

            # Preparar Popup de Resultados
            self._forge_popup = {
                "visible": True,
                "output_dir": str(Path(pcb_path).parent),
                "pcb": pcb_path,
                "sch": result.get('sch_path', ""),
                "fw": fw_info,
                "stats": stats,
                "render_status": "Renderizando...",
                "close_rect": pygame.Rect(0,0,1,1),
                "dir_rect": pygame.Rect(0,0,1,1)
            }

            if renderer.available:
                def on_render_done(res):
                    if self._forge_popup:
                        if "path" in res:
                            self._forge_popup["render_status"] = "Render 3D: " + str(Path(res['path']).name)
                        else:
                            self._forge_popup["render_status"] = "Render fallido."
                
                renderer.export_gltf_async(pcb_path, callback=on_render_done)
            else:
                self._forge_popup["render_status"] = "No render (KiCad CLI missing)"

            self._status(f'Hardware + Software Generados!', SAFE)

        except Exception as e:
            self._status(f'PCB error: {e}', DANGER)

    def _action_forge_enclosure(self) -> None:
        try:
            res = _generate_pcb(self.graph)
            if 'error' in res:
                self._status(f'PCB error: {res["error"]}', DANGER)
                return
            pcb = res.get('pcb')
            out_p = Path('output/pulselab_pcb/enclosures')
            eng_res = pcb.export_enclosure(out_p)
            self._status(f'Caja 3D: {eng_res["scad_file"]}', (150, 100, 255))
        except Exception as e:
            self._status(f'Enclosure error: {e}', DANGER)

    def _action_forge_review(self) -> None:
        self._ai_popup = {
            "visible": True, "loading": True, "issues": [],
            "close_rect": pygame.Rect(0,0,1,1), "fix_rect": None
        }

        # 1. Chequeo Geométrico Sencillo de KiCad y LLM check concurrente
        def run_ai():
            try:
                res_pcb = _generate_pcb(self.graph)
                geom_errs = 0
                if 'pcb' in res_pcb:
                    from knowledge.layout_reviewer import LayoutReviewer
                    lr = LayoutReviewer(res_pcb['pcb'])
                    audit = lr.audit()
                    geom_errs = len(audit["critical_issues"])
                
                agent = SemanticAIAgent()
                res = agent.analyze_circuit(self.graph)
                
                if self._ai_popup:
                    self._ai_popup["loading"] = False
                    if "error" in res:
                        self._ai_popup["issues"] = [{"msg": res["error"], "severity": "critical"}]
                    else:
                        ai_issues = res.get("issues", [])
                        if geom_errs > 0:
                            ai_issues.append({"msg": f"El Diseño PCB falló la verificación de clearance/bounds con {geom_errs} fallos críticos estructurales.", "severity": "critical", "proposal": "Mover componentes."})
                        self._ai_popup["issues"] = ai_issues

                    self._status('Revisión AI/DRC completada.', SAFE)

            except Exception as e:
                if self._ai_popup:
                    self._ai_popup["loading"] = False
                    self._ai_popup["issues"] = [{"msg": str(e), "severity": "critical"}]

        threading.Thread(target=run_ai, daemon=True).start()

    def _action_forge_gerbers(self) -> None:
        try:
            result = _export_gerbers()
            if 'error' in result:
                self._status(f'Gerber: {result["error"]}', DANGER)
            else:
                summary = result.get('summary', 'OK')
                self._status(f'Gerbers: {summary}', (220, 160, 40))
        except Exception as e:
            self._status(f'Gerber error: {e}', DANGER)

    def _action_forge_kicad_status(self) -> None:
        try:
            from bridge.kicad_bridge import KiCadBridge
            bridge = KiCadBridge()
            st = bridge.status()
            if st['available']:
                self._status(
                    f'KiCad {st["version"]} ✓ — {st.get("cli_path","?")}',
                    (0, 200, 180)
                )
            else:
                self._status('KiCad no encontrado. Instala KiCad 8+', DANGER)
        except Exception as e:
            self._status(f'KiCad status error: {e}', DANGER)

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

        # AI Popup
        if self._ai_popup and self._ai_popup.get("visible"):
            self._draw_ai_popup(surf)

        # Forge Popup
        if self._forge_popup and self._forge_popup.get("visible"):
            self._draw_forge_popup(surf)

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
                  W - PROPS_W - 10, 24, self.fonts['xs'], tcol, 'topright')

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

    def _draw_ai_popup(self, surf: pygame.Surface) -> None:
        # Dim background
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surf.blit(dim, (0, 0))

        # Panel
        pw, ph = 600, 400
        px, py = (W - pw) // 2, (H - ph) // 2
        p_rect = pygame.Rect(px, py, pw, ph)
        draw_panel(surf, p_rect, border_col=(60, 200, 255))
        
        # Header
        draw_text(surf, "✦ Asistente AI (Revisión Semántica y DRC)", px + 20, py + 15, self.fonts['bold'], WHITE)
        
        # Content
        y = py + 60
        if self._ai_popup["loading"]:
            draw_text(surf, "Evaluando netlist local y reglas KiCad... (Espere)", px + pw//2, py + ph//2, self.fonts['sm'], ACCENT, 'center')
        else:
            issues = self._ai_popup["issues"]
            if not issues:
                draw_text(surf, "¡Circuito 100% impecable! No se detectaron problemas.", px + 20, y, self.fonts['sm'], SAFE)
            else:
                draw_text(surf, f"Se detectaron {len(issues)} problemas semánticos/físicos:", px + 20, y, self.fonts['sm'], WARN)
                y += 30
                can_auto_fix = False
                for idx, iss in enumerate(issues[:4]): # Max 4 issues on box
                    sev_col = DANGER if iss.get("severity") == "critical" else (220,160,40)
                    texto = f"[{idx+1}] {iss.get('msg', '')}"
                    if "'0'" in texto and "'GND'" in texto:
                        can_auto_fix = True
                    draw_text(surf, texto, px + 30, y, self.fonts['xs'], sev_col)
                    y += 20
                    prop = iss.get("proposal", "")
                    if prop:
                        draw_text(surf, f"➜ {prop}", px + 50, y, self.fonts['xs'], DIM)
                        y += 25
                    else:
                        y += 10
                
                # Botones de Acción
                y = py + ph - 60
                
                # Fix button si detectamos un mismatch de 0 con GND
                if can_auto_fix:
                    btn_fw, btn_fh = 220, 35
                    self._ai_popup["fix_rect"] = pygame.Rect(px + 20, y, btn_fw, btn_fh)
                    pygame.draw.rect(surf, (0, 80, 50), self._ai_popup["fix_rect"], border_radius=5)
                    pygame.draw.rect(surf, SAFE, self._ai_popup["fix_rect"], 1, border_radius=5)
                    draw_text(surf, "🛠 Merge '0' → 'GND'", px + 20 + btn_fw//2, y + btn_fh//2, self.fonts['sm'], SAFE, 'center')

        # Close Button
        btn_w, btn_h = 100, 35
        self._ai_popup["close_rect"] = pygame.Rect(px + pw - btn_w - 20, py + ph - btn_h - 20, btn_w, btn_h)
        pygame.draw.rect(surf, PANEL_BG, self._ai_popup["close_rect"], border_radius=5)
        pygame.draw.rect(surf, ACCENT, self._ai_popup["close_rect"], 1, border_radius=5)
        draw_text(surf, "Cerrar", px + pw - 20 - btn_w//2, py + ph - 20 - btn_h//2, self.fonts['sm'], WHITE, 'center')

    def _draw_forge_popup(self, surf: pygame.Surface) -> None:
        # Dim background
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surf.blit(dim, (0, 0))

        # Panel
        pw, ph = 700, 480
        px, py = (W - pw) // 2, (H - ph) // 2
        p_rect = pygame.Rect(px, py, pw, ph)
        draw_panel(surf, p_rect, border_col=ACCENT)
        
        # Header
        draw_text(surf, "🚀 PulseLab Forge: Proyecto Finalizado", px + 30, py + 20, self.fonts['bold'], ACCENT)
        
        y = py + 80
        info = self._forge_popup
        stats = info.get("stats", {})
        
        # Files List
        items = [
            ("PROYECTO", Path(info.get("pcb", "")).name.replace(".kicad_pcb", ".kicad_pro"), SAFE),
            ("ESQUEMA",  Path(info.get("sch", "")).name, SAFE),
            ("PLACA",    Path(info.get("pcb", "")).name, SAFE),
            ("RENDER 3D", info.get("render_status", ""), ACCENT2),
        ]
        if info.get("fw"):
            items.append(("FIRMWARE", Path(info["fw"]).name, WARN))
        
        for icon, text, col in items:
            draw_text(surf, icon, px + 40, y, self.fonts['bold'], DIM)
            draw_text(surf, text, px + 220, y, self.fonts['md'], col)
            y += 35
            
        y += 20
        # Board stats
        draw_text(surf, "Métricas del Layout:", px + 40, y, self.fonts['bold'], WHITE)
        y += 25
        stats_txt = f"Tamaño: {stats.get('board_mm', '?')}  |  Componentes: {stats.get('footprints', 0)}  |  Nets: {stats.get('nets', 0)}"
        draw_text(surf, stats_txt, px + 50, y, self.fonts['xs'], DIM)
        
        # Bottom Buttons
        btn_y = py + ph - 65
        
        # Open Project Folder
        bw, bh = 220, 40
        self._forge_popup["dir_rect"] = pygame.Rect(px + 40, btn_y, bw, bh)
        pygame.draw.rect(surf, (20, 30, 50), self._forge_popup["dir_rect"], border_radius=5)
        pygame.draw.rect(surf, ACCENT2, self._forge_popup["dir_rect"], 1, border_radius=5)
        draw_text(surf, "ABRIR CARPETA PROYECTO", px + 40 + bw//2, btn_y + bh//2, self.fonts['sm'], ACCENT2, 'center')
        
        # Close Button
        self._forge_popup["close_rect"] = pygame.Rect(px + pw - 140, btn_y, 100, bh)
        pygame.draw.rect(surf, PANEL_BG, self._forge_popup["close_rect"], border_radius=5)
        pygame.draw.rect(surf, ACCENT, self._forge_popup["close_rect"], 1, border_radius=5)
        draw_text(surf, "Cerrar", px + pw - 140 + 50, btn_y + bh//2, self.fonts['sm'], WHITE, 'center')


# ─── Entry point ──────────────────────────────────────────────────────────────

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
