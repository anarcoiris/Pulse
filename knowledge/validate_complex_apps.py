"""
knowledge/validate_complex_apps.py
===================================
Suite de validación — each run writes to a timestamped folder (never overwrites prior runs).
All LLM I/O logged under knowledge/data/llm_sessions/sessions/{session_id}/.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from knowledge.circuit_synthesizer import CircuitSynthesizer
from knowledge.llm_backends import list_backends
from knowledge.llm_session_log import new_session_id
from knowledge.llm_client import get_llm_client

OUT_DIR = Path("knowledge/data/validation_complex")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_CASES = [
    {
        "name": "esp32_sensors",
        "description": "ESP32 Devboard + Sensores",
        "prompt": (
            "Diseña un circuito basado en un microcontrolador ESP32. "
            "Conecta una pantalla OLED SSD1306 al bus I2C (pines SDA, SCL). "
            "Conecta también un sensor ambiental BME280 al mismo bus I2C. "
            "Asegúrate de incluir resistencias pull-up en las líneas I2C y "
            "condensadores de desacoplo para la alimentación del ESP32."
        ),
    },
    {
        "name": "esp32_steppers",
        "description": "ESP32 + Controladores Stepper",
        "prompt": (
            "Diseña un circuito con un ESP32 que controle dos motores paso a paso NEMA17 "
            "utilizando dos drivers A4988. "
            "Conecta los pines STEP y DIR de los A4988 a pines GPIO del ESP32. "
            "Los drivers deben estar alimentados por una fuente externa de 12V para los motores (VMOT), "
            "e incluir condensadores electrolíticos grandes (ej: 100uF) cerca del pin VMOT. "
            "El ESP32 y la lógica de los A4988 (VDD) deben estar a 3.3V."
        ),
    },
    {
        "name": "esp32_rf_nfc",
        "description": "ESP32 + NFC + 433 MHz RF",
        "prompt": (
            "Diseña un sistema IoT con un ESP32. "
            "Conecta un lector NFC PN532 a través de I2C. "
            "Conecta un transceptor de radio 433 MHz CC1101 a través del bus SPI "
            "(MISO, MOSI, SCK, CS). "
            "Incluye alimentación de 3.3V para todos los módulos y condensadores de bypass."
        ),
    },
    {
        "name": "esp32_usb_devkit",
        "description": "ESP32-WROOM-32 USB Devboard",
        "prompt": (
            "Diseña una placa estilo devkit con ESP32-WROOM-32, alimentación 5V USB "
            "regulada a 3.3V con AMS1117, puente USB-UART CH340G con pares USB_D+ y USB_D-, "
            "pull-up EN 10k, condensadores de desacople, y headers GPIO. "
            "UART: CH340 TXD a RX del ESP32 (GPIO3), CH340 RXD a TX del ESP32 (GPIO1)."
        ),
    },
    {
        "name": "pulselab_zero",
        "description": "Proyecto Final: PulseLab Zero (Clon Flipper Zero)",
        "prompt": (
            "Diseña un dispositivo estilo Flipper Zero llamado PulseLab Zero. "
            "Debe tener un microcontrolador ESP32-S3 como núcleo, "
            "una pantalla OLED SSD1306 por I2C, un módulo NFC PN532 por SPI, "
            "un transceptor sub-GHz CC1101 por SPI, "
            "un D-Pad de 5 botones direccionales conectados a GPIOs con resistencias pull-up, "
            "y un conector de expansión de 8 pines (GPIOs libres, 3.3V y GND). "
            "Incluye condensadores de desacoplo para el ESP32."
        ),
    },
]


def main():
    parser = argparse.ArgumentParser(description="PulseLab complex circuit validation")
    parser.add_argument("--case", help="Run single test by name (e.g. esp32_sensors)")
    parser.add_argument("--backend", default="auto", help="LLM backend: auto|primary|atomic")
    parser.add_argument("--session", help="Reuse session id (default: new run session)")
    args = parser.parse_args()

    run_session = args.session or new_session_id("validate")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_DIR / "runs" / f"{ts}_{run_session}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("Iniciando Suite de Validacion de Aplicaciones Complejas")
    print(f"Run session: {run_session}")
    print(f"Run dir:     {run_dir}")

    backends = list_backends()
    primary = backends.get("primary", {})
    if not primary.get("available") and not backends.get("atomic", {}).get("available"):
        print("ERROR: No LLM backend available.")
        print(json.dumps(backends, indent=2))
        return

    print(f"OK: Backends: primary={primary.get('available')} atomic={backends.get('atomic', {}).get('available')}")
    synth = CircuitSynthesizer(backend=args.backend)

    cases = TEST_CASES
    if args.case:
        cases = [c for c in TEST_CASES if c["name"] == args.case]
        if not cases:
            print(f"ERROR: Unknown case '{args.case}'")
            return

    run_manifest = {
        "run_session": run_session,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "backend_pref": args.backend,
        "backends": backends,
        "results": [],
    }

    for case in cases:
        name = case["name"]
        print(f"\n-----------------------------------------------------")
        print(f"Test: {case['description']}")
        print(f"-----------------------------------------------------")

        print("Generando circuito...", flush=True)
        t0 = time.time()
        result = synth.generate_circuit_json(
            case["prompt"],
            session_id=run_session,
            meta={"test": name, "description": case["description"], "run_dir": str(run_dir)},
        )
        elapsed = time.time() - t0
        print(f"  ({elapsed:.0f}s)", flush=True)

        entry = {"name": name, "elapsed_s": round(elapsed, 1), "session_id": run_session}

        if "error" in result:
            print(f"ERROR en generacion: {result['error']}")
            entry["error"] = result["error"]
            run_manifest["results"].append(entry)
            continue

        components = result.get("components", [])
        print(f"OK: Generacion exitosa. {len(components)} componentes.")
        print(f"  backend: {result.get('backend', '?')}")
        if result.get("session_dir"):
            print(f"  llm logs: {result['session_dir']}", flush=True)

        out_file = run_dir / f"{name}.json"
        output_data = {
            "run_session": run_session,
            "test_case": case["description"],
            "prompt": case["prompt"],
            "backend": result.get("backend"),
            "llm_session_dir": result.get("session_dir"),
            "circuit": components,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Guardado en: {out_file}")

        etypes = {}
        for comp in components:
            t = comp.get("etype", "UNKNOWN")
            etypes[t] = etypes.get(t, 0) + 1
        print(f"Resumen: {etypes}")

        entry.update(
            {
                "ok": True,
                "components": len(components),
                "backend": result.get("backend"),
                "output_file": str(out_file),
                "llm_session_dir": result.get("session_dir"),
            }
        )
        run_manifest["results"].append(entry)

    run_manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRun manifest: {manifest_path}")


if __name__ == "__main__":
    main()
