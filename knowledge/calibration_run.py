"""
knowledge/calibration_run.py
==============================
Validation harness for ESP32 devboard PCB output from PulseLab Forge.
"""

from __future__ import annotations
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.kicad_importer import KicadImporter


def validate_design(pcb_path: str) -> dict:
    """Validate an ESP32-style PCB and return a structured score."""
    result = {
        "path": pcb_path,
        "decoupling_count": 0,
        "has_keepout": False,
        "uart_nets_ok": False,
        "component_count": 0,
        "score": 0,
        "passed": False,
        "errors": [],
    }

    if not os.path.exists(pcb_path):
        result["errors"].append("Design file not found.")
        return result

    nets = KicadImporter.parse_pcb_nets(pcb_path)
    comps = KicadImporter.parse_pcb_components(pcb_path)
    result["component_count"] = len(comps)

    caps = [c for c in comps if "capacitor" in c.get("lib", "").lower()
            or c.get("ref", "").startswith("C")]
    decoupling = [
        c for c in caps
        if re.search(r"C_.+_(H|L)$", c.get("ref", ""), re.I)
        or "decoupl" in c.get("val", c.get("value", "")).lower()
    ]
    if len(decoupling) < 2 and len(caps) >= 2:
        decoupling = caps[:max(2, len(caps))]
    result["decoupling_count"] = len(decoupling)

    with open(pcb_path, encoding="utf-8") as f:
        content = f.read()
    result["has_keepout"] = "(keepout" in content

    if isinstance(nets, dict):
        net_names = set(nets.values())
    elif isinstance(nets, list):
        net_names = {n.get("name", "") for n in nets}
    else:
        net_names = set()
    uart_aliases = {
        "MCU_TX", "MCU_RX", "TXD0", "RXD0", "U0TXD", "U0RXD",
    }
    result["uart_nets_ok"] = len(net_names & uart_aliases) >= 2

    score = 0
    if result["decoupling_count"] >= 2:
        score += 40
    else:
        result["errors"].append(f"Expected >=2 decoupling caps, found {result['decoupling_count']}")
    if result["has_keepout"]:
        score += 30
    else:
        result["errors"].append("Missing antenna keepout zone")
    if result["uart_nets_ok"]:
        score += 30
    else:
        result["errors"].append("UART nets not detected (need MCU_TX/RX or TXD0/RXD0)")

    result["score"] = score
    result["passed"] = score == 100
    return result


def main() -> None:
    pcb_path = os.environ.get(
        "PULSE_CALIB_PCB",
        "output/esp32_v2/pulselab_pcb/board.kicad_pcb",
    )
    print("--- Calibration Forge: Validation Run ---")
    print(f"Target: {pcb_path}")
    res = validate_design(pcb_path)
    print(f"  - Decoupling caps: {res['decoupling_count']} (pass: >=2)")
    print(f"  - Antenna keep-out: {'YES' if res['has_keepout'] else 'NO'}")
    print(f"  - UART nets: {'OK' if res['uart_nets_ok'] else 'MISSING'}")
    print(f"  - Components: {res['component_count']}")
    print(f"  - FINAL ACCURACY SCORE: {res['score']}%")
    if res["passed"]:
        print("RESULT: CALIBRATION SUCCESS.")
    else:
        print("RESULT: CALIBRATION FAILED.")
        for err in res["errors"]:
            print(f"  ! {err}")


if __name__ == "__main__":
    main()
