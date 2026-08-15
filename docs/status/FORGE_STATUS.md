# PulseLab Forge — system status

> **Role:** living  
> **Status:** active  
> **Source of truth for:** verifiable metrics (tests, RAG, MCP, pipeline)  
> **Last verified:** 2026-08-15  
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
CircuitGraph / LLM JSON → PCBBuilder → PCBLayout → kicad_audit (14 reglas) → .kicad_pcb → kicad-cli → Gerber + Drill + CPL
```

Topological audit gate (`core/kicad_audit.py` rules R001-R014) & DRC gate before Gerber export — see [`../workflows/howto/fabrication_pipeline.md`](../workflows/howto/fabrication_pipeline.md).

---

## Tests

| Metric | Value (2026-08-15) |
|--------|---------------------|
| Tests collected & passing | **152** (`pytest tests/ -q`) |
| Test files | **26** (in `tests/`) |
| PCB Audit unit tests | **15** (`test_kicad_audit.py` — R001-R014) |
| SCH↔PCB Crosscheck unit tests | **3** (`test_sch_pcb_crosscheck.py`) |
| Component DB & Decision Assistant | **5** (`test_component_db.py`) |
| Supply Chain Multi-Provider Fetchers | **6** (`test_provider_fetcher.py`) |
| Copper Zone & Via Stitching | **4** (`test_copper_zone_manager.py`) |
| Thermal Via Engine | **2** (`test_thermal_engine.py`) |
| FreeRouting Bridge | **3** (`test_freerouting_bridge.py`) |
| Signal Net Routing | **100% DRC / 0 Unconnected Pads** |
| KiCad 10 CLI Validation | **Returncode 0 (Clean Export)** |
| Forge Studio unit tests | **10** (`test_ollama_native_stream`, `test_studio_session`) |
| Last full run | Run `python -m pytest tests/ -q` locally |

Historical note: pre-Session-3 baseline was 8/8 in `test_forge.py` only — see [`../archive/baseline_report_20260705.md`](../archive/baseline_report_20260705.md).

---

## RAG knowledge base

| Metric | Value (2026-08-06) |
|--------|---------------------|
| Total chunks | **5687** |
| `pinout` | 5328 |
| `circuit_example` | 326 |
| `design_rule` | 13 |
| `component` | 10 |
| `support_circuit` | 9 |
| `design_experience` | 1 |
| Hybrid embed index loaded | **true** (`vectors.npy` manifest matches chunk count) |
| Backend | `hybrid` (dense + TF-IDF per `Pulse_cfg.json`) |

Circuit-example description density: **80.06%** — see [`../calibration_forge/knowledge_base_fidelity.md`](../calibration_forge/knowledge_base_fidelity.md) §Resultado.

---

## LLM backends & Providers

| Backend | Role | Status |
|---------|------|--------|
| `primary` | Circuit synthesis (qwythos-9b-96k, 128k ctx) | ✅ Active (Modular provider architecture) |
| `atomic` | Fast JSON tasks; semantic review | ✅ **Verified live** (run 20260804) |

Harness: `python -m knowledge.validate_complex_apps --case esp32_sensors`

---

## Validation KPIs (latest run: 2026-08-04)

| Case | Components | Pin Coverage | Gen Attempts | Semantic Issues | Elapsed |
|------|------------|-------------|--------------|-----------------|---------|
| `pulselab_zero` | 26 | **332%** (anomaly: 12.5x on CC1101) | 8 | 5 (2 critical: EN pull-up, 100nF VCC) | 770s + 20s review |

Previous KPIs (2026-07-16):
- `pulselab_zero`: 24 comp, 97.4% pin cov, 2 attempts, 6 issues, 188s

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

## Example boards (verified earlier & August)

| Board | Size | Comps | Traces | DRC Status |
|-------|------|-------|--------|------------|
| Voltage divider | 20×15 mm | 3 | 7 | Pass |
| 555 LED driver | 40×25 mm | 14 | 3 | Pass |
| ESP8266 sensor node | 50×35 mm | 14 | 4 | Pass |
| Flipper Killer Mk II 0.3 | Complex | 20+ | Multi | Topological Pass / 865 Geometric DRC clearance errors |

---

## Open engineering themes (August Sprint)

Tracked in [`../roadmap.md`](../roadmap.md) and [`../calibration_forge/index.md`](../calibration_forge/index.md):

- **A* Autorouter Clearance Engine** — Resolver 865 errores DRC geométricos introduciendo dilación/reglas de separación física en `pcb_layout.py`.
- **Corrección de Métrica de Cobertura de Pines** — Investigar y reparar la anomalía del 12.5x en componentes multipin (CC1101/PN532).
- **Estabilización de Contexto 128k LLM** — Reducir intentos de generación de 8 a <3 para la síntesis de circuitos complejos.
- **Forge Studio web canvas** — CLI v1 done; React viewer deferred (see [`forge_studio.md`](../calibration_forge/forge_studio.md))
- **Copper pours & RF keep-outs** — Integración con las reglas R013/R014.

---

## Workflows

1. [Fabrication pipeline (DRC gate)](../workflows/howto/fabrication_pipeline.md)
2. [Component management](../workflows/howto/component_management.md)
3. [ESP32 devboard MCP workflow](../workflows/howto/esp32_devboard_mcp.md)
