"""
generate_from_local_llm.py
===========================
End-to-End Pipeline:
  1. Prompt -> Local LLM (qwythos / atomic on http://127.0.0.1:11439/v1)
  2. LLM outputs JSON schema -> knowledge/data/esp32_tft_console_pcb_local.json
  3. JSON -> CircuitGraph -> PCBBuilder -> KiCad PCB + Gerbers in output/extrapolation_test/v0_1_0_local/
"""
import json
import sys
import os
import re
import csv
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.circuit_graph import CircuitGraph
from bridge.pcb_builder import PCBBuilder
from bridge.kicad_bridge import KiCadBridge

LLM_ENDPOINT = os.getenv("QWYTHOS_ENDPOINT", "http://127.0.0.1:11439/v1/chat/completions")

SYSTEM_PROMPT = """You are an expert PCB circuit designer AI. Your task is to output ONLY a raw JSON object representing an electronic circuit.
DO NOT include any conversational text, markdown formatting wrappers, or explanations outside the JSON.

JSON Structure Schema:
{
  "name": "Project Title",
  "version": "0.1.0",
  "board_width": 75.0,
  "board_height": 50.0,
  "net_classes": {
    "Default": {"clearance": 0.12, "trace_width": 0.15, "via_dia": 0.6, "via_drill": 0.3},
    "Power": {"clearance": 0.15, "trace_width": 0.50, "via_dia": 0.8, "via_drill": 0.4, "nets": ["PWR_5V_USB", "PWR_3V3_ESP"]}
  },
  "circuit": [
    {
      "etype": "Connector | R | C | IC | MCU | Header | Button | LED",
      "value": "Component Value",
      "symbol": "KiCad Symbol",
      "footprint": "KiCad Footprint",
      "position": [X, Y],
      "rotation": 0.0,
      "pins": {"pin_number": "NET_NAME"},
      "label": "Designator (e.g. U1, J1, SW1)",
      "jlcpcb_part": "LCSC Part Number (e.g. C165948)"
    }
  ]
}
"""

USER_PROMPT = """Generate a complete electronic circuit JSON for an ESP32-S3 TFT Console Board with the following specifications:
- Board size: 75.0mm x 50.0mm
- MCU: ESP32-S3-WROOM-1U (JLCPCB Part C9900027631)
- Display: 1x14 2.54mm Pin Header for ILI9341 2.8" SPI TFT (J_DISP)
- Controls: 7 Tactile Switches (D-Pad: SW_UP, SW_DOWN, SW_LEFT, SW_RIGHT, SW_OK + SW_SELECT, SW_BACK)
- Power: USB-C connector (HRO TYPE-C-31-M-12 / C165948), AMS1117-3.3 regulator (C6186), 5.1k CC resistors, decoupling caps, Power LED
- System: RESET button, BOOT button
- Expansion: 8-pin 2.54mm GPIO expansion header (J_EXP)
- Nets: Use PWR_GND for ground, PWR_5V_USB for 5V, PWR_3V3_ESP for 3.3V, USB_ESP_DP / USB_ESP_DN for USB signals.
"""


def call_local_llm(prompt: str) -> str:
    print(f"-> Calling Local LLM at {LLM_ENDPOINT}...")
    req_payload = {
        "model": "qwen3-4b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }
    data_json = json.dumps(req_payload).encode("utf-8")
    req = urllib.request.Request(
        LLM_ENDPOINT,
        data=data_json,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_body = response.read().decode("utf-8")
            res_obj  = json.loads(res_body)
            content  = res_obj["choices"][0]["message"]["content"]
            return content
    except urllib.error.URLError as e:
        print(f"  [ERROR] Failed to connect to local LLM: {e}")
        return None


def clean_and_parse_json(raw_text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw_text)
    if match:
        raw_text = match.group(1)
    else:
        start_idx = raw_text.find("{")
        end_idx   = raw_text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            raw_text = raw_text[start_idx:end_idx+1]
    
    return json.loads(raw_text)


def generate_jlcpcb_files(out_dir: Path, json_path: Path = None):
    cpl_in  = out_dir / "cpl.csv"
    bom_in  = out_dir / "bom.csv"
    jlc_cpl = out_dir / "jlcpcb_cpl.csv"
    jlc_bom = out_dir / "jlcpcb_bom.csv"

    lcsc_map = {}
    if json_path and json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for comp in data.get("circuit", []):
                if "label" in comp and "jlcpcb_part" in comp:
                    lcsc_map[comp["label"]] = comp["jlcpcb_part"]

    cpl_rows = []
    if cpl_in.exists():
        with open(cpl_in, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ref = row.get("Ref", "").strip('"')
                if ref.startswith("H") and ref[1:].isdigit():
                    continue
                try:
                    rot = float(row.get("Rot", "0.0"))
                    if rot < 0:
                        rot += 360.0
                except ValueError:
                    rot = 0.0
                side  = row.get("Side", "top").lower()
                layer = "Top" if side == "top" else "Bottom"
                cpl_rows.append({
                    "Designator": f'"{ref}"',
                    "Mid X":      f"{float(row.get('PosX', 0)):.6f}",
                    "Mid Y":      f"{float(row.get('PosY', 0)):.6f}",
                    "Rotation":   f"{rot:.6f}",
                    "Layer":      layer,
                })
        with open(jlc_cpl, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
            writer.writeheader()
            for r in cpl_rows:
                f.write(f'{r["Designator"]},{r["Mid X"]},{r["Mid Y"]},{r["Rotation"]},{r["Layer"]}\n')
        print(f"  [OK] CPL -> {jlc_cpl}")

    if bom_in.exists():
        bom_rows = []
        with open(bom_in, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ref = row.get("Refs", "").strip('"')
                val = row.get("Value", "").strip('"')
                fp  = row.get("Footprint", "").strip('"')
                if not ref:
                    continue
                if ref.startswith("H") and ref[1:].isdigit():
                    continue
                if ref.endswith("?"):
                    ref = ref[:-1]
                lcsc_val = lcsc_map.get(ref, "")
                bom_rows.append({"Comment": val, "Designator": ref, "Footprint": fp, "LCSC": lcsc_val})
        with open(jlc_bom, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC"])
            writer.writeheader()
            writer.writerows(bom_rows)
        print(f"  [OK] BOM -> {jlc_bom}")


def run_pipeline():
    print("=" * 60)
    print("  END-TO-END PIPELINE: Prompt -> Local LLM -> PCB")
    print("=" * 60)

    local_json_path = root_dir / "knowledge/data/esp32_tft_console_pcb_local.json"
    
    # Step 1: Query Local LLM
    raw_response = call_local_llm(USER_PROMPT)
    if not raw_response:
        print("  Falling back to canonical JSON template...")
        canonical_path = root_dir / "knowledge/data/esp32_tft_console_pcb.json"
        with open(canonical_path, "r", encoding="utf-8") as f:
            circuit_data = json.load(f)
    else:
        try:
            circuit_data = clean_and_parse_json(raw_response)
            print("  [OK] LLM output successfully parsed as JSON!")
        except Exception as e:
            print(f"  [WARNING] JSON parsing error: {e}. Falling back to template.")
            canonical_path = root_dir / "knowledge/data/esp32_tft_console_pcb.json"
            with open(canonical_path, "r", encoding="utf-8") as f:
                circuit_data = json.load(f)

    # Save to local json path
    with open(local_json_path, "w", encoding="utf-8") as f:
        json.dump(circuit_data, f, indent=2)
    print(f"  Saved generated circuit schema to {local_json_path}")

    # Step 2: Build PCB
    extrapolation_base = root_dir / "output" / "extrapolation_test"
    sub_name = "v0_1_0_local"
    out_dir  = extrapolation_base / sub_name
    out_dir.mkdir(parents=True, exist_ok=True)

    circuit     = circuit_data.get("circuit", [])
    net_classes = circuit_data.get("net_classes", {})
    board_w     = circuit_data.get("board_width", 75.0)
    board_h     = circuit_data.get("board_height", 50.0)

    graph = CircuitGraph.from_component_dicts(circuit)

    builder = PCBBuilder.from_circuit_graph(
        graph,
        out_dir=str(extrapolation_base),
        project_name="ESP32 TFT Console Local (qwythos)",
        net_classes=net_classes,
        board_width=board_w,
        board_height=board_h,
        corner_radius=2.5,
        mounting_holes=True,
        skip_routing=True,
    )
    pcb = builder.pcb

    offset_x = (297.0 - board_w) / 2.0
    offset_y = (210.0 - board_h) / 2.0

    usb_abs_x = offset_x + (board_w / 2.0) - 28.0
    pcb.add_edge_cutout(cx=usb_abs_x, width=10.0, depth=2.5, edge="top")

    pcb.add_copper_pour(net="PWR_GND", layer="F.Cu", margin=0.5, priority=0)
    pcb.add_copper_pour(net="PWR_GND", layer="B.Cu", margin=0.5, priority=0)

    builder._pcb = pcb
    result = builder.save(sub_dir=sub_name)

    pcb_path = Path(result["path"])
    sch_path = Path(result.get("sch_path", ""))

    bridge = KiCadBridge()
    cli    = bridge._cli

    if cli and cli.exists():
        print("  [...] fill-zones...")
        subprocess.run(
            [str(cli), "pcb", "fill-zones", str(pcb_path)],
            capture_output=True, text=True, timeout=30,
        )

        print("  [...] DRC...")
        drc_res    = bridge.run_drc(pcb_path, output_dir=out_dir)
        violations = drc_res.get("violations", [])
        warnings   = drc_res.get("warnings", [])
        type_counts = {}
        for v in violations:
            vtype = v.get("type", "other")
            type_counts[vtype] = type_counts.get(vtype, 0) + 1
        unconn = type_counts.pop("unconnected_items", 0)
        iso    = type_counts.pop("isolated_copper", 0)
        print(f"  DRC: {len(violations)} violaciones | {len(warnings)} advertencias")
        print(f"    unconnected={unconn}  isolated_copper={iso}")

        subprocess.run(
            [str(cli), "sch", "export", "bom",
             "--output", str(out_dir / "bom.csv"), str(sch_path)],
            capture_output=True, text=True, timeout=30,
        )
        subprocess.run(
            [str(cli), "pcb", "export", "pos",
             "--output", str(out_dir / "cpl.csv"),
             "--format", "csv", "--units", "mm", str(pcb_path)],
            capture_output=True, text=True, timeout=30,
        )
        generate_jlcpcb_files(out_dir, json_path=local_json_path)

    print("\n" + "=" * 60)
    print(f"  END-TO-END PIPELINE COMPLETADO -> {out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
