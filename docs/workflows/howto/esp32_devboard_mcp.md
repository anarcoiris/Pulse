# ESP32 USB Devboard — MCP Workflow

Use PulseLab MCP tools (not raw chat) to produce manufacturable KiCad output.

## Prerequisites

- KiCad 8+ on PATH
- Ollama with `PULSE_LLM_MODEL` and `PULSE_EMBED_MODEL` (see [`.env.example`](../../.env.example))
- MCP server: `python mcp_server/server.py`

## Ordered tool calls

1. **`get_mcu_support_circuit("ESP32-WROOM-32")`** — decoupling, EN pull-up, USB-UART bridge notes
2. **`search_electronics_knowledge("USB UART ESP32 devboard differential")`** — RAG examples from training corpus
3. **`load_preset("esp32_usb_devkit")`** or **`generate_circuit_from_text(...)`** — netlist JSON
4. **`export_to_kicad(circuit_json)`** — netlist + BOM
5. **`create_pcb_layout(...)`** or GUI Forge → generates `.kicad_pcb` + `.kicad_sch`
6. **`calculate_usb_diff_pair()`** — W/S for 90 Ω differential (FR4 1.6 mm)
7. **`calculate_trace_width_for_impedance(50, ...)`** — power rail width
8. DRC gate → **`generate_pcb_gerbers(pcb_path)`**

## Presets

| Name | Description |
|------|-------------|
| `esp32_usb_devkit` | ESP32-WROOM-32 + CH340G + AMS1117 + GPIO headers |
| `esp32s2_usb_devkit` | ESP32-S2 native USB + LDO + UART header |
| `mcu` / `mcu_uart` | ESP8266 + CH340 reference |

## Rebuild embeddings

After updating training data:

```
python -m knowledge.build_embed_index
```

Or MCP: **`rebuild_embed_index()`**

## Validation

```
python tests/test_forge.py
python tests/test_rag_retrieval.py
python knowledge/calibration_run.py
```

Set `PULSE_CALIB_PCB=output/esp32_usb_devkit_test/pulselab_pcb/board.kicad_pcb` after integration test.
