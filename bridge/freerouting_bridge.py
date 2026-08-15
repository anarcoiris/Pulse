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
        Initializes FreeRouting Bridge. If freerouting_jar_path is not specified,
        attempts to find 'freerouting' in PATH or default locations.
        """
        self.jar_path = freerouting_jar_path or os.environ.get("FREEROUTING_JAR", "")

    def export_dsn(self, pcb_path: Path, dsn_path: Optional[Path] = None) -> Path:
        """
        Exports a KiCad PCB file to Specctra DSN format using kicad-cli.
        """
        pcb_path = Path(pcb_path).resolve()
        if not pcb_path.exists():
            raise FileNotFoundError(f"KiCad PCB file not found: {pcb_path}")

        if dsn_path is None:
            dsn_path = pcb_path.with_suffix(".dsn")
        else:
            dsn_path = Path(dsn_path).resolve()

        # Command: kicad-cli pcb export dsn <input.kicad_pcb> -o <output.dsn>
        cmd = ["kicad-cli", "pcb", "export", "dsn", str(pcb_path), "-o", str(dsn_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0 and not dsn_path.exists():
            raise RuntimeError(f"kicad-cli DSN export failed (code {res.returncode}): {res.stderr}")

        return dsn_path

    def run_freerouting(self, dsn_path: Path, output_ses_path: Optional[Path] = None, timeout_sec: int = 120) -> FreeRoutingResult:
        """
        Runs FreeRouting auto-router engine on input DSN file.
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

        # Check for java / jar execution
        java_cmd = shutil.which("java")
        if self.jar_path and Path(self.jar_path).exists() and java_cmd:
            cmd = [java_cmd, "-jar", self.jar_path, "-de", str(dsn_path), "-out", str(output_ses_path)]
        elif shutil.which("freerouting"):
            cmd = ["freerouting", "-de", str(dsn_path), "-out", str(output_ses_path)]
        else:
            # If FreeRouting engine binary is not installed locally, return status indicating missing runner
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
        Imports routed Specctra SES session file back into KiCad PCB using kicad-cli.
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

        # Command: kicad-cli pcb import ses <input.kicad_pcb> --input-ses <input.ses> -o <output.kicad_pcb>
        cmd = ["kicad-cli", "pcb", "import", "ses", str(pcb_path), "--input-ses", str(ses_path), "-o", str(output_pcb_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0 and not output_pcb_path.exists():
            raise RuntimeError(f"kicad-cli SES import failed (code {res.returncode}): {res.stderr}")

        return output_pcb_path
