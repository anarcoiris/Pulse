"""
bridge/kicad_bridge.py
======================
Puente entre PulseLab y KiCad 8+.

Detecta KiCad automáticamente y envuelve:
  - kicad-cli (CLI oficial de KiCad 8)
  - Generación de netlists via core.netlist
  - Opciones de placement básico via pcbnew (si disponible)
"""

from __future__ import annotations
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui.editor import CircuitGraph


# ─── Rutas de KiCad ──────────────────────────────────────────────────────────

def find_kicad_cli() -> Optional[Path]:
    """Localiza el ejecutable kicad-cli en el sistema."""
    # 1. En PATH del sistema (Opción más robusta y preferida)
    found = shutil.which("kicad-cli")
    if found:
        return Path(found)

    # 2. Rutas conocidas por plataforma
    import platform
    system = platform.system()
    
    candidates = []
    if system == "Windows":
        candidates = [
            r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
            r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
            r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
            r"D:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
            r"D:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
        ]
    elif system == "Darwin": # macOS
        candidates = ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"]
    elif system == "Linux":
        candidates = [
            "/usr/bin/kicad-cli",
            "/usr/local/bin/kicad-cli",
            "/snap/bin/kicad-cli",
            "/opt/kicad/bin/kicad-cli",
        ]

    for p in candidates:
        cli = Path(p)
        if cli.exists():
            return cli
            
    return None


def find_kicad_symbol_dir() -> Optional[Path]:
    """Localiza el directorio de símbolos de KiCad."""
    # Variable de entorno (configuración de usuario)
    env = os.environ.get("KICAD_SYMBOL_DIR")
    if env and Path(env).exists():
        return Path(env)

    import platform
    system = platform.system()
    
    if system == "Windows":
        for base in [r"C:\Program Files\KiCad\8.0", r"D:\Program Files\KiCad\8.0",
                     r"C:\Program Files\KiCad\10.0", r"C:\Program Files\KiCad"]:
            p = Path(base) / "share" / "kicad" / "symbols"
            if p.exists(): return p
    elif system == "Darwin":
        p = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
        if p.exists(): return p
    else: # Linux
        for p in [Path("/usr/share/kicad/symbols"), Path("/usr/local/share/kicad/symbols")]:
            if p.exists(): return p
    return None


def find_kicad_footprint_dir() -> Optional[Path]:
    """Localiza el directorio de footprints de KiCad."""
    env = os.environ.get("KICAD_FOOTPRINT_DIR")
    if env and Path(env).exists():
        return Path(env)

    import platform
    system = platform.system()
    
    if system == "Windows":
        for base in [r"C:\Program Files\KiCad\8.0", r"D:\Program Files\KiCad\8.0",
                     r"C:\Program Files\KiCad\10.0", r"C:\Program Files\KiCad"]:
            p = Path(base) / "share" / "kicad" / "footprints"
            if p.exists(): return p
    elif system == "Darwin":
        p = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
        if p.exists(): return p
    else: # Linux
        for p in [Path("/usr/share/kicad/footprints"), Path("/usr/local/share/kicad/footprints")]:
            if p.exists(): return p
    return None


def get_kicad_footprint(lib: str, name: str) -> Optional[str]:
    """
    Lee un footprint de la biblioteca estándar de KiCad.
    
    Args:
        lib:  Nombre de la librería, e.g. 'Package_QFP'
        name: Nombre del footprint, e.g. 'LQFP-48_7x7mm_P0.5mm'
    
    Returns:
        Contenido del archivo .kicad_mod como string o None.
    """
    fp_dir = find_kicad_footprint_dir()
    if not fp_dir:
        return None
        
    fp_path = fp_dir / f"{lib}.pretty" / f"{name}.kicad_mod"
    if not fp_path.exists():
        return None
        
    return fp_path.read_text(encoding='utf-8')


# ─── KiCadBridge ─────────────────────────────────────────────────────────────

class KiCadBridge:
    """
    Interfaz Python para KiCad 8+.

    Wraps kicad-cli via subprocess y gestiona el flujo:
        CircuitGraph → netlist → (kicad_pcb) → Gerber/Drill/BOM

    Uso::

        bridge = KiCadBridge()
        if bridge.available:
            result = bridge.export_all(graph, output_dir="output/mydesign")
    """

    def __init__(self, kicad_cli_path: Optional[Path] = None):
        self._cli  = kicad_cli_path or find_kicad_cli()
        self._sym  = find_kicad_symbol_dir()
        self._fp   = find_kicad_footprint_dir()

    # ── Status ────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._cli is not None and self._cli.exists()

    @property
    def version(self) -> str:
        if not self.available:
            return "KiCad no encontrado"
        try:
            r = subprocess.run([str(self._cli), "--version"],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip() or r.stderr.strip()
        except Exception as e:
            return f"Error: {e}"

    def status(self) -> dict:
        return {
            "available": self.available,
            "cli_path": str(self._cli) if self._cli else None,
            "version": self.version if self.available else None,
            "symbol_dir": str(self._sym) if self._sym else None,
            "footprint_dir": str(self._fp) if self._fp else None,
        }

    # ── Netlist generation ────────────────────────────────────────

    def generate_netlist(self, graph: "CircuitGraph",
                         output_dir: Path,
                         project_name: str = "design") -> dict:
        """
        Genera netlist KiCad y script SKiDL desde CircuitGraph.

        Returns:
            dict con paths de los archivos generados.
        """
        from core.netlist import NetlistGenerator
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ng = NetlistGenerator(graph)

        net_path   = output_dir / f"{project_name}.net"
        skidl_path = output_dir / f"{project_name}_skidl.py"
        bom_path   = output_dir / f"{project_name}_bom.csv"

        ng.save_kicad_netlist(net_path)
        ng.save_skidl_script(skidl_path)
        ng.save_bom_csv(bom_path)

        return {
            "netlist": str(net_path),
            "skidl_script": str(skidl_path),
            "bom_csv": str(bom_path),
            "components": len(graph.components),
            "nets": len(graph.all_nodes),
        }

    # ── Gerber export ─────────────────────────────────────────────

    def export_gerbers(self, pcb_path: Path,
                       output_dir: Optional[Path] = None,
                       layers: Optional[list[str]] = None) -> dict:
        """
        Genera archivos Gerber desde un .kicad_pcb usando kicad-cli.

        Args:
            pcb_path:   Ruta al archivo .kicad_pcb.
            output_dir: Directorio de salida (default: mismo dir que pcb).
            layers:     Lista de capas a exportar. None = todas las estándar.

        Returns:
            dict con status y lista de archivos generados.
        """
        from bridge.gerber_export import export_gerbers as _export
        return _export(self._cli, Path(pcb_path), output_dir, layers)

    def export_drill(self, pcb_path: Path,
                     output_dir: Optional[Path] = None) -> dict:
        """Genera archivo Excellon drill desde .kicad_pcb."""
        from bridge.gerber_export import export_drill as _drill
        return _drill(self._cli, Path(pcb_path), output_dir)

    def export_position(self, pcb_path: Path,
                        output_dir: Optional[Path] = None) -> dict:
        """Genera archivo de posición de componentes (pick & place)."""
        from bridge.gerber_export import export_position as _pos
        return _pos(self._cli, Path(pcb_path), output_dir)

    def run_drc(self, pcb_path: Path,
                output_dir: Optional[Path] = None) -> dict:
        """
        Ejecuta DRC (Design Rule Check) sobre el PCB.
        Requiere KiCad 8+.

        Returns:
            dict con violations y warnings.
        """
        if not self.available:
            return {"error": "KiCad no disponible", "violations": [], "warnings": []}

        out = Path(output_dir) if output_dir else Path(pcb_path).parent
        out.mkdir(parents=True, exist_ok=True)
        report = out / "drc_report.json"

        try:
            result = subprocess.run(
                [str(self._cli), "pcb", "drc",
                 "--output", str(report),
                 "--format", "json",
                 str(pcb_path)],
                capture_output=True, text=True, timeout=60,
            )
            if report.exists():
                data = json.loads(report.read_text(encoding="utf-8"))
                return {
                    "status": "ok",
                    "violations": data.get("violations", []),
                    "warnings": data.get("warnings", []),
                    "report": str(report),
                }
            return {
                "status": "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "violations": [],
                "warnings": [],
            }
        except Exception as e:
            return {"error": str(e), "violations": [], "warnings": []}

    # ── Full pipeline ─────────────────────────────────────────────

    def export_all(self, graph: "CircuitGraph",
                   output_dir: str = "output",
                   project_name: str = "design",
                   skip_drc: bool = False) -> dict:
        """
        Pipeline completo: CircuitGraph → netlist + BOM.
        Si hay un .kicad_pcb en output_dir, también genera Gerbers (previo DRC).

        Returns:
            dict con todos los archivos generados.
        """
        out = Path(output_dir)
        result = self.generate_netlist(graph, out, project_name)

        pcb_path = out / f"{project_name}.kicad_pcb"
        if pcb_path.exists() and self.available:
            # 1. Ejecutar DRC obligatorio antes de exportar fabricación
            if not skip_drc:
                drc = self.run_drc(pcb_path, out / "reports")
                result["drc_report"] = drc
                if drc.get("violations") and len(drc["violations"]) > 0:
                    result["error"] = f"DRC detectó {len(drc['violations'])} violaciones críticas. Exportación abortada."
                    return result

            # 2. Si DRC OK, exportar archivos de fabricación
            gerber_dir = out / "gerbers"
            result["gerbers"]  = self.export_gerbers(pcb_path, gerber_dir)
            result["drill"]    = self.export_drill(pcb_path, gerber_dir)
            result["position"] = self.export_position(pcb_path, gerber_dir)
        else:
            result["note"] = (
                f"PCB no encontrado en {pcb_path}. "
                "Abre el .net en KiCad PCBNEW, realiza el layout, "
                "guarda como .kicad_pcb, luego llama export_all() de nuevo."
            )

        return result


# ─── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bridge = KiCadBridge()
    s = bridge.status()
    print("=== KiCad Bridge Status ===")
    for k, v in s.items():
        print(f"  {k:20s}: {v}")
