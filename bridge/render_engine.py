"""
bridge/render_engine.py
=======================
Motor de renderizado y exportación 3D para PulseLab Forge.
Envuelve KiCad CLI para generar copias tridimensionales del PCB
completamente llenas de modelos volumétricos de la placa final (.gltf / .step).
"""

import subprocess
import threading
from pathlib import Path
from bridge.kicad_bridge import find_kicad_cli

class RenderEngine3D:
    def __init__(self):
        self.cli_path = find_kicad_cli()
        self.available = self.cli_path is not None

    def export_gltf(self, pcb_path: str, output_path: str = None) -> dict:
        """
        Exporta de forma síncrona el PCB físico a formato WebGL GLTF
        con todos los materiales cocinados.
        """
        if not self.available:
            return {"error": "KiCad CLI no instalado. No se puede renderizar 3D."}

        pcb = Path(pcb_path)
        if not pcb.exists():
            return {"error": f"Archivo PCB {pcb_path} no listado."}

        if output_path is None:
            out = pcb.parent / (pcb.stem + ".gltf")
        else:
            out = Path(output_path)

        cmd = [
            str(self.cli_path), "pcb", "export", "gltf",
            "--subst-models",     # Intercambia variantes STEP a WRL/GLTF si existen
            "-o", str(out),
            str(pcb)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and out.exists():
                return {"status": "ok", "path": str(out), "size_bytes": out.stat().st_size}
            else:
                return {"error": f"Exit code {result.returncode}: {result.stderr}"}
        except subprocess.TimeoutExpired:
            return {"error": "Tiempo límite de Renderizado 3D excedido."}
        except Exception as e:
            return {"error": str(e)}

    def export_gltf_async(self, pcb_path: str, output_path: str = None, callback=None):
        """Dispara en un thread paralelo."""
        def task():
            res = self.export_gltf(pcb_path, output_path)
            if callback:
                callback(res)
        threading.Thread(target=task, daemon=True).start()
