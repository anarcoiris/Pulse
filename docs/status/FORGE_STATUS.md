# PulseLab Forge — system status

> **Role:** living  
> **Status:** active  
> **Source of truth for:** verifiable metrics (tests, RAG, MCP, pipeline)  
> **Last verified:** 2026-07-18  
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

| Metric | Value (2026-07-18) |
|--------|---------------------|
| Tests collected | **110** (`pytest tests/ --co -q`) |
| Test files | **17** (in `tests/`) |
| CI coverage | **4/17** test files (`ci.yml` — offline-safe subset) |
| Forge Studio unit tests | **10** (`test_ollama_native_stream`, `test_studio_session`) |
| Last full run | Run `python -m pytest tests/ -q` locally (suite includes optional KiCad / LLM skips) |

Historical note: pre-Session-3 baseline was 8/8 in `test_forge.py` only — see [`../archive/baseline_report_20260705.md`](../archive/baseline_report_20260705.md).

---

## RAG knowledge base

| Metric | Value (2026-07-18) |
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

| Backend | Role | Status |
|---------|------|--------|
| `primary` | Circuit synthesis (qwythos-9b-96k, 98k ctx) | ✅ Active |
| `atomic` | Fast JSON tasks; semantic review | ✅ **Verified live** (run 20260716) |

Harness: `python -m knowledge.validate_complex_apps --case esp32_sensors`

---

## Validation KPIs (latest run: 2026-07-16)

| Case | Components | Pin Coverage | Gen Attempts | Semantic Issues | Elapsed |
|------|------------|-------------|--------------|-----------------|---------|
| `pulselab_zero` | 24 | **97.4%** avg | 2 | 6 (3 critical) | 188s + 30s review |

Previous KPIs (2026-07-07 commit):
- `esp32_sensors`: 8 comp, 72.65% pin cov, 4 turns, 1 critical DRC
- `pulselab_zero`: 21 comp, 88.54% pin cov, 5 turns, 0 issues

---

## Forge Studio (Session 4e)

| Item | Value |
|------|-------|
| Entry point | `python -m studio` |
| Package | `studio/` (headless; no pygame) |
| Streaming transport | `knowledge/llm_client.py::chat_stream`, `ollama_native.py::chat_native_stream` |
| Docs | [`../calibration_forge/forge_studio.md`](../calibration_forge/forge_studio.md) |
| Dependency | `rich==14.3.3` |

Windows: `$env:PYTHONIOENCODING='utf-8'` + Windows Terminal. Requires Ollama `:11431` + `qwythos-9b-96k` for live runs.

---

## Skills knowledge base (NEW — since 2026-07-10)

| Item | Value |
|------|-------|
| Location | `skills/` |
| Active rules | **2** (`power_on_reset`, `decoupling_per_ic`) |
| Architecture | [`skills/ARCHITECTURE.md`](../../skills/ARCHITECTURE.md) — domain-separated, neutral intermediate model |
| Roadmap | [`skills/ROADMAP.md`](../../skills/ROADMAP.md) — 5 phases, evidence-driven |
| Finding schema | [`skills/finding.schema.json`](../../skills/finding.schema.json) |

---

## MCP

| Metric | Value |
|--------|-------|
| Tools exposed | **31** (`@mcp.tool` in `mcp_server/server.py`) |

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

- **4b clean A/B** — prompt rules vs richer RAG (decision deferred — **4d blocker now resolved**)
- **Forge Studio web canvas** — CLI v1 done; React viewer deferred (see [`forge_studio.md`](../calibration_forge/forge_studio.md))
- **Modelo Multipin** — Editor + netlist + schematic unification (cross-cutting, not a numbered session)
- Copper pours, scikit-rf, PDF datasheet ingestion — backlog
- **Skills KB expansion** — I2C pull-ups, boot strap pins, component library (see [`skills/ROADMAP.md`](../../skills/ROADMAP.md))

---

## Workflows

1. [Fabrication pipeline (DRC gate)](../workflows/howto/fabrication_pipeline.md)
2. [Component management](../workflows/howto/component_management.md)
3. [ESP32 devboard MCP workflow](../workflows/howto/esp32_devboard_mcp.md)
