"""
Export completo de fabricación para las 3 placas de ejemplo.
Genera: Gerbers + Drill + Position (CPL) + SVG preview para cada una.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.kicad_bridge import KiCadBridge
from bridge.gerber_export import generate_all_manufacturing_files


def main():
    bridge = KiCadBridge()
    print(f"KiCad: {bridge.version} @ {bridge._cli}\n")

    if not bridge.available:
        print("ERROR: KiCad no disponible")
        return

    boards = [
        ("01_voltage_divider", "Divisor de Tension"),
        ("02_555_led_driver",  "555 LED Driver"),
        ("03_esp8266_node",    "ESP8266 Sensor Node"),
    ]

    for folder, name in boards:
        pcb = Path(f"output/{folder}/board.kicad_pcb")
        if not pcb.exists():
            print(f"[SKIP] {name}: {pcb} no existe")
            continue

        print(f"{'='*60}")
        print(f"  {name}")
        print(f"  PCB: {pcb}")
        print(f"{'='*60}")

        mfg_dir = pcb.parent / "manufacturing"
        result = generate_all_manufacturing_files(bridge._cli, pcb, mfg_dir)

        print(f"  Status: {'OK' if result['success'] else 'ERROR'}")
        print(f"  {result['summary']}")

        # Gerbers
        gerbers = result.get("gerbers", {})
        if gerbers.get("files"):
            print(f"  Gerbers ({len(gerbers['files'])}):")
            for f in gerbers["files"]:
                print(f"    {Path(f).name}")

        # Drill
        drill = result.get("drill", {})
        if drill.get("files"):
            print(f"  Drill ({len(drill['files'])}):")
            for f in drill["files"]:
                print(f"    {Path(f).name}")

        # Position
        pos = result.get("position", {})
        if pos.get("file"):
            print(f"  Position: {Path(pos['file']).name}")

        # SVG preview
        preview = result.get("preview", {})
        if preview.get("files"):
            print(f"  SVG previews ({len(preview['files'])}):")
            for f in preview["files"]:
                print(f"    {Path(f).name}")

        if gerbers.get("stderr"):
            print(f"  [WARN] {gerbers['stderr'][:150]}")
        print()

    print("Done! All manufacturing files in output/*/manufacturing/")


if __name__ == "__main__":
    main()
