# PulseLab Forge — system status

> **Role:** living  
> **Status:** active  
> **Source of truth for:** verifiable metrics (tests, RAG, MCP, pipeline)  
> **Last verified:** 2026-07-07  
> **See also:** [`CURRENT_SPRINT.md`](./CURRENT_SPRINT.md) · [`../calibration_forge/index.md`](../calibration_forge/index.md)

Refresh ritual after each sprint:

```powershell
cd C:\Users\soyko\Documents\Pulse-main
python -m pytest tests/ -q
python -c "from knowledge.rag_engine import ElectronicsKnowledgeBase; print(ElectronicsKnowledgeBase().stats())"
python -c "import re; from pathlib import Path; t=Path('mcp_server/server.py').read_text(); print('mcp_tools', len(re.findall(r'@mcp\\.tool', t)))"
```

---

## Pipeline

```
CircuitGraph / LLM JSON → PCBLayout → .kicad_pcb → kicad-cli → Gerber + Drill + CPL
```

DRC gate before Gerber export — see [`../workflows/howto/fabrication_pipeline.md`](../workflows/howto/fabrication_pipeline.md).

---

## Tests

| Metric | Value (2026-07-07) |
|--------|---------------------|
| Tests collected | **102** (`pytest tests/ --co -q`) |
| Last full run | Run `python -m pytest tests/ -q` locally (suite includes optional KiCad / LLM skips) |

Historical note: pre-Session-3 baseline was 8/8 in `test_forge.py` only — see [`../archive/baseline_report_20260705.md`](../archive/baseline_report_20260705.md).

---

## RAG knowledge base

| Metric | Value (2026-07-07) |
|--------|---------------------|
| Total chunks | **5685** |
| `pinout` | 5326 |
| `circuit_example` | 326 |
| `design_rule` | 13 |
| `component` | 10 |
| `support_circuit` | 9 |
| `design_experience` | 1 |
| Hybrid embed index loaded | **true** (`vectors.npy` manifest matches chunk count) |
| Backend | `hybrid` (dense + TF-IDF per `Pulse_cfg.json`) |

Circuit-example description density: **~80%** post Session 1 — see [`../calibration_forge/knowledge_base_fidelity.md`](../calibration_forge/knowledge_base_fidelity.md) §Resultado.

---

## LLM backends

| Backend | Role |
|---------|------|
| `primary` | Circuit synthesis (qwythos-9b-96k, 98k ctx) |
| `atomic` | Fast JSON tasks; **configured** for semantic review (Session 4d — verify live) |

Harness: `python -m knowledge.validate_complex_apps --case esp32_sensors`

---

## MCP

| Metric | Value |
|--------|-------|
| Tools exposed | **31** (`@mcp.tool` in `mcp_server/server.py`) |

Categories unchanged from April review — see tool list in [`../reviews/pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §3 (count updated here).

---

## Example boards (verified earlier)

| Board | Size | Comps | Traces |
|-------|------|-------|--------|
| Voltage divider | 20×15 mm | 3 | 7 |
| 555 LED driver | 40×25 mm | 14 | 3 |
| ESP8266 sensor node | 50×35 mm | 14 | 4 |

---

## Open engineering themes

Tracked in [`../roadmap.md`](../roadmap.md) and [`../calibration_forge/index.md`](../calibration_forge/index.md):

- **4b clean A/B** — prompt rules vs richer RAG (decision deferred)
- **Modelo Multipin** — Editor + netlist + schematic unification (cross-cutting, not a numbered session)
- Copper pours, scikit-rf, PDF datasheet ingestion — backlog

---

## Workflows

1. [Fabrication pipeline (DRC gate)](../workflows/howto/fabrication_pipeline.md)
2. [Component management](../workflows/howto/component_management.md)
3. [ESP32 devboard MCP workflow](../workflows/howto/esp32_devboard_mcp.md)
