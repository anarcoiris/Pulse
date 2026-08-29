"""
freerouting_bridge.py
=====================
FreeRouting Integration Bridge for PulseLab EDA Platform.

Provides:
- Specctra DSN export from KiCad PCB (`kicad-cli pcb export dsn`).
- Headless execution runner for FreeRouting auto-router engine (`freerouting.jar` or `freerouting` binary).
- Specctra SES import and trace back-annotation into KiCad PCB (`kicad-cli pcb import ses`).
"""
import os
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class FreeRoutingResult:
    success: bool
    dsn_path: Path
    ses_path: Optional[Path] = None
    output_pcb_path: Optional[Path] = None
    message: str = ""
    exit_code: int = 0

class FreeRoutingBridge:
    def __init__(self, freerouting_jar_path: Optional[str] = None):
        """
        Initializes FreeRouting Bridge. Detects 'freerouting.exe' in AppData/Local,
        PATH, or custom JAR/executable path.
        """
        self.jar_path = freerouting_jar_path or os.environ.get("FREEROUTING_JAR", "") or os.environ.get("FREEROUTING_EXE", "")
        self.exe_path = self._discover_freerouting()

    def _discover_freerouting(self) -> Optional[Path]:
        # 1. Custom specified path
        if self.jar_path:
            p = Path(self.jar_path).resolve()
            if p.exists():
                return p

        # 2. Check AppData Local on Windows
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = []
        if local_app_data:
            candidates.append(Path(local_app_data) / "freerouting" / "freerouting.exe")
        candidates.extend([
            Path.home() / "AppData" / "Local" / "freerouting" / "freerouting.exe",
            Path.home() / ".local" / "bin" / "freerouting",
            Path("/usr/local/bin/freerouting"),
            Path("/usr/bin/freerouting")
        ])

        for c in candidates:
            if c.exists():
                return c

        # 3. Check system PATH
        which_fr = shutil.which("freerouting") or shutil.which("freerouting.exe")
        if which_fr:
            return Path(which_fr)

        return None

    def _get_kicad_python(self) -> Optional[Path]:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local_app_data) / "Programs" / "KiCad" / "10.0" / "bin" / "python.exe",
            Path("C:/Program Files/KiCad/10.0/bin/python.exe"),
            Path("C:/Program Files/KiCad/9.0/bin/python.exe"),
            Path("C:/Program Files/KiCad/8.0/bin/python.exe"),
            Path.home() / "AppData" / "Local" / "Programs" / "KiCad" / "10.0" / "bin" / "python.exe"
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def export_dsn(self, pcb_path: Path, dsn_path: Optional[Path] = None) -> Path:
        """
        Exports a KiCad PCB file to Specctra DSN format using pcbnew API.
        """
        pcb_path = Path(pcb_path).resolve()
        if not pcb_path.exists():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_path}")

        if dsn_path is None:
            dsn_path = pcb_path.with_suffix(".dsn")
        else:
            dsn_path = Path(dsn_path).resolve()

        # 1. Try KiCad Python pcbnew native export
        k_py = self._get_kicad_python()
        if k_py:
            cmd = [str(k_py), "-c", f"import pcbnew; b = pcbnew.LoadBoard(r'{pcb_path}'); pcbnew.ExportSpecctraDSN(b, r'{dsn_path}')"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if dsn_path.exists():
                return dsn_path

        # 2. Fallback to direct import if running under KiCad Python
        try:
            import pcbnew
            b = pcbnew.LoadBoard(str(pcb_path))
            if pcbnew.ExportSpecctraDSN(b, str(dsn_path)) and dsn_path.exists():
                return dsn_path
        except Exception:
            pass

        raise RuntimeError(f"Specctra DSN export failed for {pcb_path}")

    def run_freerouting(self, dsn_path: Path, output_ses_path: Optional[Path] = None, timeout_sec: int = 120, max_passes: int = 15, threads: int = 1) -> FreeRoutingResult:
        """
        Runs FreeRouting auto-router engine on input DSN file with single-threaded route optimization.
        """
        dsn_path = Path(dsn_path).resolve()
        if not dsn_path.exists():
            return FreeRoutingResult(
                success=False,
                dsn_path=dsn_path,
                message=f"DSN file not found: {dsn_path}",
                exit_code=1
            )

        if output_ses_path is None:
            output_ses_path = dsn_path.with_suffix(".ses")
        else:
            output_ses_path = Path(output_ses_path).resolve()

        # Check for executable or java / jar execution
        exe = self._discover_freerouting()
        java_cmd = shutil.which("java")

        if exe and exe.suffix.lower() == ".exe":
            cmd = [str(exe), "-de", str(dsn_path), "-do", str(output_ses_path), "-mt", str(threads), "-mp", str(max_passes)]
        elif exe and exe.suffix.lower() == ".jar" and java_cmd:
            cmd = [java_cmd, "-jar", str(exe), "-de", str(dsn_path), "-do", str(output_ses_path), "-mt", str(threads), "-mp", str(max_passes)]
        elif exe and not exe.suffix: # linux/macos binary
            cmd = [str(exe), "-de", str(dsn_path), "-do", str(output_ses_path), "-mt", str(threads), "-mp", str(max_passes)]
        elif self.jar_path and Path(self.jar_path).exists() and java_cmd:
            cmd = [java_cmd, "-jar", self.jar_path, "-de", str(dsn_path), "-do", str(output_ses_path), "-mt", str(threads), "-mp", str(max_passes)]
        else:
            return FreeRoutingResult(
                success=False,
                dsn_path=dsn_path,
                message="FreeRouting engine binary/JAR not found in system environment",
                exit_code=127
            )

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
            success = res.returncode == 0 and output_ses_path.exists()
            return FreeRoutingResult(
                success=success,
                dsn_path=dsn_path,
                ses_path=output_ses_path if output_ses_path.exists() else None,
                message=res.stdout + "\n" + res.stderr,
                exit_code=res.returncode
            )
        except Exception as e:
            return FreeRoutingResult(
                success=False,
                dsn_path=dsn_path,
                message=f"FreeRouting execution error: {str(e)}",
                exit_code=1
            )

    def import_ses(self, pcb_path: Path, ses_path: Path, output_pcb_path: Optional[Path] = None) -> Path:
        """
        Imports routed Specctra SES session file back into KiCad PCB using pcbnew API.
        """
        pcb_path = Path(pcb_path).resolve()
        ses_path = Path(ses_path).resolve()
        if not pcb_path.exists():
            raise FileNotFoundError(f"Base PCB file not found: {pcb_path}")
        if not ses_path.exists():
            raise FileNotFoundError(f"SES file not found: {ses_path}")

        if output_pcb_path is None:
            output_pcb_path = pcb_path.with_name(pcb_path.stem + "_routed.kicad_pcb")
        else:
            output_pcb_path = Path(output_pcb_path).resolve()

        # 1. Try KiCad Python pcbnew native import
        k_py = self._get_kicad_python()
        if k_py:
            cmd = [str(k_py), "-c", f"import pcbnew; b = pcbnew.LoadBoard(r'{pcb_path}'); pcbnew.ImportSpecctraSES(b, r'{ses_path}'); b.Save(r'{output_pcb_path}')"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if output_pcb_path.exists():
                return output_pcb_path

        # 2. Fallback to direct import if running under KiCad Python
        try:
            import pcbnew
            b = pcbnew.LoadBoard(str(pcb_path))
            pcbnew.ImportSpecctraSES(b, str(ses_path))
            b.Save(str(output_pcb_path))
            if output_pcb_path.exists():
                return output_pcb_path
        except Exception:
            pass

        raise RuntimeError(f"Specctra SES import failed for {ses_path}")

