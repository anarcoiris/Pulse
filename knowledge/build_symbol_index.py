"""
knowledge/build_symbol_index.py
================================
Construye ``knowledge/data/symbols_index.json`` indexando un subconjunto
priorizado de librerías ``.kicad_sym`` desde una instalación real de KiCad
(no vendorizamos nada: se lee directamente la instalación local del usuario).

Uso:
    python -m knowledge.build_symbol_index [--symbol-dir PATH] [--out PATH]

Resolución del directorio fuente (en orden):
  1. ``--symbol-dir`` explícito (override manual).
  2. Variable de entorno ``KICAD_SYMBOL_DIR``.
  3. ``bridge.kicad_bridge.find_kicad_symbol_dir()`` (detecta instalaciones en
     ``Program Files`` y en instalaciones de usuario bajo
     ``%LOCALAPPDATA%\\Programs\\KiCad\\<version>``).
  4. Si ninguno resuelve: error claro explicando cómo configurar
     ``KICAD_SYMBOL_DIR`` manualmente.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.kicad_symbol_parser import KiCadSymbolParser

# Librerías .kicad_sym consideradas de interés para electrónica de hobby/IoT/
# prototipado. La instalación completa de KiCad trae ~220 librerías; la
# mayoría son irrelevantes para este proyecto (familias MCU industriales poco
# usadas, conectores de nicho, RF militar/aeroespacial, etc.). Esta lista se
# puede ampliar en sesiones futuras sin tocar el parser ni el resto del
# pipeline — sólo hay que añadir el nombre de archivo (sin extensión) aquí.
PRIORITY_LIBRARIES = [
    "RF_Module",
    "RF_WiFi",
    "RF_Bluetooth",
    "RF_NFC",
    "MCU_Espressif",
    "MCU_ST_STM32F1",
    "MCU_RaspberryPi",
    "MCU_Microchip_ATmega",
    "Interface_USB",
    "Regulator_Linear",
    "Regulator_Switching",
    "Driver_Motor",
    "Timer",
    "Amplifier_Operational",
    "Connector_Generic",
    "Sensor_Magnetic",
    "Sensor_Voltage",
    "Sensor_Motion",
    "Sensor_Temperature",
    "Sensor_Touch",
    "Sensor_Optical",
    "Sensor_Proximity",
    "Sensor_Pressure",
    "Sensor_Audio",
    "Sensor_Current",
    "Sensor_Gas",
    "Sensor_Humidity",
    "Sensor_Energy",
    "Sensor_Distance",
]

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "symbols_index.json"


def resolve_symbol_dir(explicit: str = None) -> Path:
    """Resuelve el directorio de símbolos KiCad siguiendo el orden de
    precedencia documentado en el docstring del módulo. Lanza SystemExit con
    un mensaje accionable si no se puede resolver ninguna ruta."""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        raise SystemExit(f"--symbol-dir no existe: {explicit}")

    env = os.environ.get("KICAD_SYMBOL_DIR")
    if env and Path(env).exists():
        return Path(env)

    from bridge.kicad_bridge import find_kicad_symbol_dir
    found = find_kicad_symbol_dir()
    if found:
        return found

    raise SystemExit(
        "No se pudo localizar el directorio de simbolos de KiCad.\n"
        "Opciones:\n"
        "  1. Instalar KiCad 8.0/9.0/10.0 en una ruta estandar (Program Files "
        "o AppData/Local/Programs en Windows; /usr/share/kicad en Linux; "
        "/Applications/KiCad en macOS).\n"
        "  2. Definir la variable de entorno KICAD_SYMBOL_DIR apuntando al "
        "directorio 'symbols' de tu instalacion (ej. "
        "'C:\\...\\KiCad\\10.0\\share\\kicad\\symbols').\n"
        "  3. Pasar --symbol-dir explicitamente a este script."
    )


def build_index(symbol_dir: Path, libraries=None) -> dict:
    """Parsea las librerías priorizadas encontradas en `symbol_dir` y arma la
    estructura completa que se persiste en symbols_index.json."""
    libraries = list(PRIORITY_LIBRARIES) if libraries is None else list(libraries)
    parser = KiCadSymbolParser()

    all_files = sorted(symbol_dir.glob("*.kicad_sym"))
    wanted = set(libraries)
    to_parse = [f for f in all_files if f.stem in wanted]
    skipped = sorted(f.stem for f in all_files if f.stem not in wanted)
    missing = sorted(wanted - {f.stem for f in all_files})

    symbols = []
    errors = []
    libraries_indexed = []
    for f in to_parse:
        print(f"  Parseando {f.name} ...", flush=True)
        try:
            parsed = parser.parse_library(str(f))
            symbols.extend(parsed)
            libraries_indexed.append(f.stem)
            print(f"    -> {len(parsed)} simbolos")
        except Exception as exc:  # noqa: BLE001 - una libreria con error no debe tumbar el resto
            errors.append({"library": f.stem, "error": str(exc)})
            print(f"    !! ERROR: {exc}")

    return {
        "symbols": symbols,
        "stats": {
            "parsed_symbols": len(symbols),
            "libraries_indexed": libraries_indexed,
            "libraries_skipped": skipped,
            "libraries_missing": missing,
            "errors": errors,
            "source_dir": str(symbol_dir),
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol-dir", default=None, help="Directorio de simbolos KiCad (override manual)")
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Ruta de salida para symbols_index.json")
    args = ap.parse_args()

    print("Construyendo symbols_index.json ...")
    symbol_dir = resolve_symbol_dir(args.symbol_dir)
    print(f"Directorio de simbolos KiCad resuelto: {symbol_dir}")
    print(f"Librerias prioritarias a indexar: {len(PRIORITY_LIBRARIES)}")

    index = build_index(symbol_dir)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = index["stats"]
    print(f"\nOK: {stats['parsed_symbols']} simbolos indexados desde {len(stats['libraries_indexed'])} librerias.")
    if stats["libraries_missing"]:
        print(f"AVISO: librerias prioritarias no encontradas en la instalacion: {stats['libraries_missing']}")
    if stats["errors"]:
        print(f"AVISO: {len(stats['errors'])} librerias con errores de parseo: "
              f"{[e['library'] for e in stats['errors']]}")
    print(f"Guardado en: {out_path}")


if __name__ == "__main__":
    main()
