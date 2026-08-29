"""
scripts/build_and_verify_unified_pipeline.py
============================================
Unified Pipeline Execution & Multi-Dataset Verification.

Demonstrates the Single Source of Truth architecture:
JSON -> CircuitGraph -> PCBBuilder (AutoPlacementEngine + Bounding Box + KiCad .kicad_sch + .kicad_pcb + FreeRouting DSN)
"""
import sys
import os
import json
from pathlib import Path

# Force UTF-8 encoding for stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.circuit_graph import CircuitGraph
from bridge.pcb_builder import PCBBuilder
from bridge.freerouting_bridge import FreeRoutingBridge
import subprocess

def run_unified_pipeline_test(json_rel_path: str, output_subdir: str, project_name: str, skip_routing: bool = True):
    print(f"\n=======================================================")
    print(f"[*] RUNNING UNIFIED PIPELINE: {project_name}")
    print(f"   Input SSOT: {json_rel_path}")
    print(f"   Output Dir: output/{output_subdir}")
    print(f"=======================================================")

    full_json_path = ROOT_DIR / json_rel_path
    if not full_json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {full_json_path}")

    with open(full_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    circuit = data.get("circuit", [])
    net_classes = data.get("net_classes", {})
    board_w = data.get("board_width_mm")
    board_h = data.get("board_height_mm")

    print(f"[*] Loaded {len(circuit)} components from JSON SSOT.")

    # 1. Convert to CircuitGraph
    graph = CircuitGraph.from_component_dicts(circuit)
    print(f"[*] Built CircuitGraph successfully with {len(graph.components)} components and {len(graph.all_nodes)} nodes.")

    # 2. Build via PCBBuilder with AutoPlacementEngine & Dynamic Bounds
    builder = PCBBuilder.from_circuit_graph(
        graph,
        out_dir=str(ROOT_DIR / "output"),
        project_name=project_name,
        board_width=board_w,
        board_height=board_h,
        net_classes=net_classes,
        skip_routing=skip_routing
    )

    result = builder.save(sub_dir=output_subdir)
    pcb_path = Path(result["path"])
    sch_path = Path(result["sch_path"])
    dsn_path = Path(result.get("dsn_path", ""))

    print(f"[+] KiCad PCB generated: {pcb_path}")
    print(f"[+] KiCad SCH generated: {sch_path}")
    if dsn_path.exists():
        print(f"[+] FreeRouting DSN exported: {dsn_path} ({dsn_path.stat().st_size} bytes)")
    else:
        print(f"[-] DSN export note: {result.get('dsn_error', 'Not generated')}")

    print(f"[*] PCB Stats: {result.get('stats')}")

    # 3. Electrical Audit with kicad-cli DRC
    try:
        drc_report_path = pcb_path.parent / "drc_report.json"
        cmd = ["kicad-cli", "pcb", "drc", "--output", str(drc_report_path), "--format", "json", str(pcb_path)]
        drc_run = subprocess.run(cmd, capture_output=True, text=True)
        if drc_report_path.exists():
            with open(drc_report_path, "r", encoding="utf-8") as df:
                drc_data = json.load(df)
            unconnected = len(drc_data.get("unconnected_items", []))
            violations = len(drc_data.get("violations", []))
            print(f"[DRC] Unconnected items (unrouted nets awaiting FreeRouting): {unconnected}")
            print(f"[DRC] Total layout clearance/design rule violations: {violations}")
    except Exception as e:
        print(f"[DRC] Note: {e}")

    return result

def main():
    test_cases = [
        # 1. Target Flipper Killer V4.3
        {
            "json": "knowledge/data/flipper_killer_v4_3.json",
            "subdir": "flipper_killer_production_v4_3",
            "name": "Flipper_Killer_MKII_v4_3"
        },
        # 2. ESP32 Radar Node (Recent)
        {
            "json": "knowledge/data/esp32_ld2450_tft_radar.json",
            "subdir": "test_radar_production",
            "name": "ESP32_LD2450_Radar"
        },
        # 3. ESP32 Console PCB (Recent)
        {
            "json": "knowledge/data/esp32_tft_console_pcb.json",
            "subdir": "test_console_production",
            "name": "ESP32_TFT_Console"
        },
        # 4. Unseen Synthetic Multi-Cell Test
        {
            "json": "knowledge/data/synthetic_multicell_test.json",
            "subdir": "test_synthetic_multicell",
            "name": "Synthetic_IoT_Node"
        }
    ]

    print("=======================================================")
    print("[*] EXECUTING MULTI-DATASET UNIFIED PIPELINE VERIFICATION")
    print("=======================================================")

    results = []
    for tc in test_cases:
        res = run_unified_pipeline_test(tc["json"], tc["subdir"], tc["name"])
        results.append((tc["name"], res.get("success", False)))

    print("\n=======================================================")
    print("[*] UNIFIED PIPELINE BATCH EXECUTION SUMMARY:")
    for name, success in results:
        status = "PASSED" if success else "FAILED"
        print(f"  - {name}: {status}")
    print("=======================================================")

if __name__ == "__main__":
    main()
