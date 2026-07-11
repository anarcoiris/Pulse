# PulseLab Baseline Report

> **Role:** archive  
> **Status:** frozen (2026-07-05)  
> **Source of truth for:** nothing — historical snapshot only  
> **Last verified:** 2026-07-05  
> **See also:** [`../status/FORGE_STATUS.md`](../status/FORGE_STATUS.md) for current metrics

Run date: 2026-07-05 (post-implementation verification)

| Check | Result | Notes |
|-------|--------|-------|
| `tests/test_forge.py` | **8/8 PASS** | KiCad Gerber export skipped (not installed) |
| `tests/test_rag_retrieval.py` | **4/4 PASS** | Hybrid RAG + overlap rerank |
| `knowledge/calibration_run.py` | **100%** | `output/esp32_usb_devkit_test/pulselab_pcb/board.kicad_pcb` |
| RAG KB cold start | **358 chunks** | 326 `circuit_example` from training JSON |
| Embed index | **358 vectors** | `knowledge/data/embeddings/vectors.npy` |
| `tests/test_import_esp32.py` | **PASS** | 7 symbols parsed from esp32_v2 sch |
| `examples/esp32_devboard_v2.py` | **PASS** | PCB + sch generated |
| KiCad / Gerbers | **SKIP** | Install KiCad 8 for full fab pipeline |
| `validate_complex_apps.py` | **Requires Ollama** | Run with Qwythos per `.env` |

## Plan phases delivered

- Phase 0–1: Bug fixes (RAG training load, calibration, MCP presets, schematics, pinouts)
- Phase 2: nomic-embed hybrid RAG (`embed_client.py`, `build_embed_index`)
- Phase 3: Env config, agent prompts, MCP workflow doc
- Phase 4: `esp32_usb_devkit`, `esp32s2_usb_devkit`, USB diff-pair RF + PCB routing
- Phase 5: `design_experience.py` hooked to Forge + Gerber DRC

## Re-run verification

```powershell
$PY = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
cd C:\Users\soyko\Documents\Pulse-main
& $PY tests/test_forge.py
& $PY tests/test_rag_retrieval.py
$env:PULSE_CALIB_PCB = "output/esp32_usb_devkit_test/pulselab_pcb/board.kicad_pcb"
& $PY knowledge/calibration_run.py
```
