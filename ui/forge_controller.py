"""
ui/forge_controller.py
======================
Orquesta todas las acciones del subsistema Forge (PCB, review AI,
firmware synthesis, enclosure, Gerbers) que antes vivían como
métodos ``_action_forge_*`` dentro de ``PulseLabApp``.

Desacopla la orquestación de la clase principal de la aplicación,
reduciendo la complejidad de ``pulse_lab.py`` y facilitando el testing
de cada flujo de Forge de forma independiente.
"""

from __future__ import annotations
import json
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple, TYPE_CHECKING

from core.logger import logger

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph
    from ui.modals import ForgeResultModal, AIGeneratorModal, AIReviewModal


# Helpers que se importan de forge_api al usarlos
# (se mantienen lazy para no cargar bridge/ en import time)


class ForgeController:
    """
    Controlador que encapsula las acciones Forge del menú principal.

    Parameters
    ----------
    graph_fn : callable
        Función que devuelve el ``CircuitGraph`` actual (lambda: self.graph).
    status_fn : callable(msg, color)
        Callback para mostrar mensajes de estado en la barra inferior.
    forge_modal : ForgeResultModal
        Modal de resultado PCB.
    ai_review_modal : AIReviewModal
        Modal de revisión AI.
    ai_gen_modal : AIGeneratorModal
        Modal de generación AI.
    snapshot_fn : callable
        Función para hacer snapshot del estado (undo).
    reload_fn : callable
        Función para recargar el grafo en la UI.
    """

    def __init__(
        self,
        graph_fn: Callable[[], "CircuitGraph"],
        status_fn: Callable[[str, Tuple], None],
        forge_modal: "ForgeResultModal",
        ai_review_modal: "AIReviewModal",
        ai_gen_modal: "AIGeneratorModal",
        snapshot_fn: Callable,
        reload_fn: Callable,
    ):
        self._graph = graph_fn
        self._status = status_fn
        self.forge_modal = forge_modal
        self.ai_review_modal = ai_review_modal
        self.ai_gen_modal = ai_gen_modal
        self._snapshot = snapshot_fn
        self._reload_graph = reload_fn

    @property
    def graph(self) -> "CircuitGraph":
        return self._graph()

    # ── Export KiCad Netlist ────────────────────────────────────

    def export_kicad(self) -> None:
        """Exporta netlist KiCad + SKiDL + BOM."""
        try:
            from bridge.forge_api import export_kicad_netlist
            result = export_kicad_netlist(self.graph)
            if 'error' in result:
                self._status(f'Forge: {result["error"]}', (220, 50, 50))
            else:
                num_files = sum(1 for k in ['netlist', 'skidl_script', 'bom_csv'] if k in result)
                self._status(f'KiCad: {num_files} archivos → output/', (0, 200, 180))
        except Exception as e:
            self._status(f'Forge error: {e}', (220, 50, 50))

    # ── Generate PCB + Firmware ────────────────────────────────

    def gen_pcb(self) -> None:
        """Genera PCB (.kicad_pcb), esquemático (.kicad_sch), firmware y render 3D."""
        try:
            from bridge.forge_api import generate_pcb as _generate_pcb

            n = len(self.graph.components)
            if n == 0:
                self._status('Sin componentes. Dibuja un circuito primero.', (220, 180, 40))
                return

            # 1. Generación de Proyectos (PCB + SCH + Netlist)
            result = _generate_pcb(self.graph)
            if 'error' in result:
                self._status(f'PCB error: {result["error"]}', (220, 50, 50))
                return

            stats = result.get('stats', {})
            pcb_path = result['path']

            # 2. Renderizado 3D (Async)
            from bridge.render_engine import RenderEngine3D
            renderer = RenderEngine3D()

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

            self.forge_modal.show_result(
                output_dir=str(Path(pcb_path).parent),
                pcb=pcb_path,
                sch=result.get('sch_path', ""),
                fw=fw_info,
                stats=stats,
            )

            if renderer.available:
                def on_render_done(res):
                    self.forge_modal.set_render_status(res)
                renderer.export_gltf_async(pcb_path, callback=on_render_done)
            else:
                self.forge_modal.render_status = "No render (KiCad CLI missing)"

            self._status('Hardware + Software Generados!', (60, 200, 60))

            try:
                from knowledge.design_experience import record_design_outcome
                mcu = next(
                    (str(c.value) for c in self.graph.components if c.etype == "MCU"),
                    "",
                )
                record_design_outcome(
                    board_id=Path(pcb_path).parent.name,
                    mcu=mcu,
                    gerber_path=str(Path(pcb_path).parent / "manufacturing"),
                    passed=True,
                    lessons=[
                        f"Generated {stats.get('footprints', n)} footprints via Forge GUI",
                    ],
                    component_count=stats.get("footprints", n),
                )
                logger.info("forge_controller", f"design experience registrada para {Path(pcb_path).parent.name}")
            except Exception as e:
                logger.error("forge_controller", f"record_design_outcome() fallo en gen_pcb(): {e}")

        except Exception as e:
            self._status(f'PCB error: {e}', (220, 50, 50))

    # ── Enclosure ──────────────────────────────────────────────

    def gen_enclosure(self) -> None:
        """Genera caja 3D (OpenSCAD) a partir del PCB."""
        try:
            from bridge.forge_api import generate_pcb as _generate_pcb
            res = _generate_pcb(self.graph)
            if 'error' in res:
                self._status(f'PCB error: {res["error"]}', (220, 50, 50))
                return
            pcb = res.get('pcb')
            out_p = Path('output/pulselab_pcb/enclosures')
            eng_res = pcb.export_enclosure(out_p)
            self._status(f'Caja 3D: {eng_res["scad_file"]}', (150, 100, 255))
        except Exception as e:
            self._status(f'Enclosure error: {e}', (220, 50, 50))

    # ── AI Review ──────────────────────────────────────────────

    def review_ai(self) -> None:
        """Lanza revisión semántica AI del circuito actual."""
        def merge_gnd_fix():
            self._snapshot()
            self.graph.merge_nodes("GND", "0")
            self._reload_graph()
            self._status("Arreglo aplicado: '0' -> 'GND' unificados.", (60, 200, 60))

        self.ai_review_modal.show_review(merge_gnd_fix)

        def task():
            try:
                from knowledge.semantic_reviewer import SemanticReviewer
                circuit_json = json.dumps(self.graph.to_json())
                reviewer = SemanticReviewer()
                rev = reviewer.review_netlist(circuit_json)
                self.ai_review_modal.issues = rev.get("issues", [])
            except Exception as e:
                self.ai_review_modal.issues = [{"msg": f"Crash en IA: {str(e)}", "severity": "critical"}]
            finally:
                self.ai_review_modal.loading = False

        threading.Thread(target=task, daemon=True).start()

    # ── Gerbers ────────────────────────────────────────────────

    def export_gerbers(self) -> None:
        """Exporta Gerbers + Drill desde el último PCB generado."""
        try:
            from bridge.forge_api import export_gerbers as _export_gerbers
            result = _export_gerbers()
            if 'error' in result:
                self._status(f'Gerber: {result["error"]}', (220, 50, 50))
            else:
                summary = result.get('summary', 'OK')
                self._status(f'Gerbers: {summary}', (220, 160, 40))
        except Exception as e:
            self._status(f'Gerber error: {e}', (220, 50, 50))

    # ── KiCad Status ───────────────────────────────────────────

    def kicad_status(self) -> None:
        """Muestra el estado de la instalación de KiCad."""
        try:
            from bridge.kicad_bridge import KiCadBridge
            bridge = KiCadBridge()
            st = bridge.status()
            if st['available']:
                self._status(
                    f'KiCad {st["version"]} ✓ — {st.get("cli_path","?")}',
                    (0, 200, 180),
                )
            else:
                self._status('KiCad no encontrado. Instala KiCad 8+', (220, 50, 50))
        except Exception as e:
            self._status(f'KiCad status error: {e}', (220, 50, 50))

    # ── AI Circuit Generator ──────────────────────────────────

    def gen_ai(self) -> None:
        """Muestra el prompt de generación de circuito AI."""
        self.ai_gen_modal.show_prompt(self._run_ai_generator)

    def _run_ai_generator(self, prompt: str) -> None:
        """Ejecuta la generación AI en un hilo secundario."""
        self.ai_gen_modal.loading = True
        self.ai_gen_modal.error = ""

        def task():
            try:
                from knowledge.circuit_synthesizer import CircuitSynthesizer
                from core.circuit_graph import CircuitGraph
                synth = CircuitSynthesizer()
                res = synth.generate_circuit_json(prompt)

                if "error" in res:
                    self.ai_gen_modal.error = res["error"]
                else:
                    comps = res.get("components", [])
                    if not comps:
                        self.ai_gen_modal.error = "El modelo no devolvió componentes."
                    else:
                        new_graph = CircuitGraph.from_component_dicts(comps)
                        self._snapshot()

                        # Fusionar en lugar de reemplazar (Orquestación Modular)
                        self.graph.merge(new_graph, offset=(5, 5))
                        self._reload_graph()

                        # Registrar para entrenamiento de la red neuronal
                        from knowledge.layout_ai import layout_engine
                        layout_engine.record_design(self.graph, {"source": "IA_Generator", "prompt": prompt})

                        self.ai_gen_modal.hide()
                        self._status(f'Circuito generado ({len(comps)} componentes).', (60, 200, 60))
            except Exception as e:
                self.ai_gen_modal.error = f"Crash: {str(e)}"
            finally:
                self.ai_gen_modal.loading = False

        threading.Thread(target=task, daemon=True).start()
