"""
bridge/gerber_export.py
=======================
Wrapper de subprocess sobre kicad-cli para exportar archivos de fabricación.

kicad-cli referencia: https://docs.kicad.org/8.0/en/cli/cli.html
"""

from __future__ import annotations
import subprocess
import glob
from pathlib import Path
from typing import Optional

# Capas estándar para un PCB de 2 capas
DEFAULT_LAYERS = [
    "F.Cu", "B.Cu",
    "F.Mask", "B.Mask",
    "F.SilkS", "B.SilkS",
    "F.Paste", "B.Paste",
    "Edge.Cuts",
    "F.Fab", "B.Fab",
]


def _run_kicad_cli(exe: Path, args: list[str], timeout: int = 60) -> dict:
    """Ejecuta kicad-cli y devuelve resultado estructurado."""
    if exe is None or not exe.exists():
        return {
            "success": False,
            "error": f"kicad-cli no encontrado: {exe}",
            "stdout": "", "stderr": "",
        }
    try:
        cmd = [str(exe)] + args
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "success": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout", "stdout": "", "stderr": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": ""}


def run_drc(cli: Optional[Path], pcb_path: Path, output_dir: Optional[Path] = None) -> dict:
    """
    Ejecuta el DRC (Design Rule Check) de KiCad.
    Retorna resultado con violaciones y severidad.
    """
    pcb_path = Path(pcb_path)
    output_dir = Path(output_dir) if output_dir else pcb_path.parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / f"{pcb_path.stem}_drc.json"

    result = _run_kicad_cli(cli, [
        "pcb", "drc",
        "--output", str(report_file),
        "--format", "json",
        "--severity-all",
        str(pcb_path),
    ])

    # Parsear el reporte si existe
    if report_file.exists():
        import json
        try:
            with open(report_file, "r") as f:
                data = json.load(f)
            violations = data.get("violations", [])
            errors = [v for v in violations if v.get("severity") == "error"]
            warnings = [v for v in violations if v.get("severity") == "warning"]
            result["error_count"] = len(errors)
            result["warning_count"] = len(warnings)
            result["report_file"] = str(report_file)
            if errors:
                result["success"] = False
                result["error"] = f"Se detectaron {len(errors)} errores de diseño."
        except Exception as e:
            result["error"] = f"Error parseando DRC: {e}"
    
    return result


def export_gerbers(
    cli: Optional[Path],
    pcb_path: Path,
    output_dir: Optional[Path] = None,
    layers: Optional[list[str]] = None,
) -> dict:
    """
    Exporta archivos Gerber (RS-274X) desde un .kicad_pcb.

    Comando: kicad-cli pcb export gerbers [options] <file.kicad_pcb>

    Returns:
        dict con success, files generados, stderr si hay error.
    """
    pcb_path  = Path(pcb_path)
    output_dir = Path(output_dir) if output_dir else pcb_path.parent / "gerbers"
    output_dir.mkdir(parents=True, exist_ok=True)

    layer_arg = ",".join(layers if layers else DEFAULT_LAYERS)

    result = _run_kicad_cli(cli, [
        "pcb", "export", "gerbers",
        "--output", str(output_dir) + "/",
        "--layers", layer_arg,
        "--no-protel-ext",          # Extensiones estándar .gbr
        "--subtract-soldermask",    # Soldermask subtract copper
        str(pcb_path),
    ])

    # Listar archivos generados
    files = sorted(str(f) for f in output_dir.glob("*.gbr"))
    result["files"] = files
    result["count"] = len(files)
    result["output_dir"] = str(output_dir)

    return result


def export_drill(
    cli: Optional[Path],
    pcb_path: Path,
    output_dir: Optional[Path] = None,
    fmt: str = "excellon",
) -> dict:
    """
    Exporta archivo de taladros (Excellon) desde .kicad_pcb.

    Comando: kicad-cli pcb export drill [options] <file.kicad_pcb>
    """
    pcb_path  = Path(pcb_path)
    output_dir = Path(output_dir) if output_dir else pcb_path.parent / "gerbers"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = _run_kicad_cli(cli, [
        "pcb", "export", "drill",
        "--output", str(output_dir) + "/",
        "--format", fmt,           # "excellon" o "gerber"
        "--excellon-units", "mm",
        "--excellon-zeros-format", "suppressleading",
        str(pcb_path),
    ])

    files = sorted(str(f) for f in output_dir.glob("*.drl"))
    files += sorted(str(f) for f in output_dir.glob("*-NPTH.drl"))
    result["files"] = list(set(files))
    result["output_dir"] = str(output_dir)
    return result


def export_position(
    cli: Optional[Path],
    pcb_path: Path,
    output_dir: Optional[Path] = None,
    side: str = "both",
) -> dict:
    """
    Exporta archivo de posición de componentes (pick & place / centroid).

    Comando: kicad-cli pcb export pos [options] <file.kicad_pcb>
    """
    pcb_path  = Path(pcb_path)
    output_dir = Path(output_dir) if output_dir else pcb_path.parent / "gerbers"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file  = output_dir / f"{pcb_path.stem}_cpl.csv"

    result = _run_kicad_cli(cli, [
        "pcb", "export", "pos",
        "--output", str(out_file),
        "--format", "csv",
        "--units", "mm",
        "--side", side,     # "front", "back", "both"
        str(pcb_path),
    ])

    result["file"] = str(out_file) if out_file.exists() else None
    return result


def export_svg(
    cli: Optional[Path],
    pcb_path: Path,
    output_dir: Optional[Path] = None,
    layers: Optional[list[str]] = None,
) -> dict:
    """
    Exporta SVG del PCB para preview / documentación.
    """
    pcb_path  = Path(pcb_path)
    output_dir = Path(output_dir) if output_dir else pcb_path.parent / "preview"
    output_dir.mkdir(parents=True, exist_ok=True)
    layer_arg = ",".join(layers or ["F.Cu", "B.Cu", "Edge.Cuts", "F.SilkS"])

    result = _run_kicad_cli(cli, [
        "pcb", "export", "svg",
        "--output", str(output_dir) + "/",
        "--layers", layer_arg,
        str(pcb_path),
    ])

    files = sorted(str(f) for f in output_dir.glob("*.svg"))
    result["files"] = files
    result["output_dir"] = str(output_dir)
    return result


def generate_all_manufacturing_files(
    cli: Optional[Path],
    pcb_path: Path,
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Genera todos los archivos necesarios para fabricación:
      - Gerbers (todas las capas)
      - Excellon drill
      - CPL / Position file

    Este es el flujo completo listo para enviar a JLCPCB / PCBWay / etc.

    Returns:
        dict con status de cada paso y todos los archivos generados.
    """
    pcb_path  = Path(pcb_path)
    out = Path(output_dir) if output_dir else pcb_path.parent / "manufacturing"
    out.mkdir(parents=True, exist_ok=True)

    results = {
        "pcb_source": str(pcb_path),
        "output_dir": str(out),
    }

    # P1: DRC obligatorio primero
    results["drc"] = run_drc(cli, pcb_path, out / "reports")
    if not results["drc"].get("success", False):
        results["success"] = False
        results["summary"] = f"❌ Error de Diseño (DRC): {results['drc'].get('error_count', 0)} errores."
        return results

    results["gerbers"]  = export_gerbers(cli, pcb_path, out / "gerbers")
    results["drill"]    = export_drill(cli, pcb_path, out / "gerbers")
    results["position"] = export_position(cli, pcb_path, out)
    results["preview"]  = export_svg(cli, pcb_path, out / "preview")

    # Resumen
    all_ok = all(v.get("success", False) for v in [
        results["gerbers"], results["drill"]
    ])
    results["success"] = all_ok
    results["summary"] = (
        f"{'✅' if all_ok else '❌'} "
        f"{results['gerbers'].get('count', 0)} Gerbers + "
        f"{len(results['drill'].get('files', []))} drill files"
    )

    return results
