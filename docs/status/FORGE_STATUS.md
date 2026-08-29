# PulseLab Forge — System Status

> **Role:** living  
> **Status:** active  
> **Source of truth for:** verifiable metrics (tests, RAG, MCP, pipeline)  
> **Last verified:** 2026-08-30  
> **See also:** [`CURRENT_SPRINT.md`](./CURRENT_SPRINT.md) · [`../roadmap.md`](../roadmap.md)

Refresh ritual after each sprint:

```powershell
cd C:\Users\soyko\Documents\Pulse-main
python -m pytest tests/ -q
python -c "from knowledge.rag_engine import ElectronicsKnowledgeBase; print(ElectronicsKnowledgeBase().stats())"
python -c "import re; from pathlib import Path; t=Path('mcp_server/server.py').read_text(encoding='utf-8'); print('mcp_tools', len(re.findall(r'@mcp\\.tool', t))+1)"
```

---

## 🚀 Unified Pipeline Architecture

```
Prompt / LLM JSON → AutoPlacementEngine → CircuitGraph → PCBBuilder → PCBLayout → kicad_audit (14 reglas) → sch_pcb_crosscheck → .kicad_pcb + .kicad_sch → kicad-cli → Gerber + Drill + CPL → 2D SVG / 3D Three.js WebGL
```

Topological audit gate (`core/kicad_audit.py` rules R001-R014) & 100% SCH $\leftrightarrow$ PCB parity gate before Gerber export — see [`../workflows/howto/fabrication_pipeline.md`](../workflows/howto/fabrication_pipeline.md).

---

## 🧪 Tests & Quality Metrics

| Metric | Value (2026-08-30) |
|--------|---------------------|
| Tests collected & passing | **198** (`pytest tests/ -q`, 100% pass rate) |
| Test modules | **35** (in `tests/`) |
| API Gateway integration tests | **7** (`test_api_gateway.py`) |
| Chat Session Manager unit tests | **5** (`test_chat_session_manager.py`) |
| Visual Inference unit tests | **9** (`test_visual_inference.py` — VIS-001..VIS-009) |
| Corpus Rules evaluator tests | **5** (`test_corpus_rules.py`) |
| PCB Audit unit tests | **15** (`test_kicad_audit.py` — R001-R014) |
| SCH↔PCB Crosscheck unit tests | **3** (`test_sch_pcb_crosscheck.py`) |
| Component DB & Decision Assistant | **5** (`test_component_db.py`) |
| Supply Chain Multi-Provider Fetchers | **6** (`test_provider_fetcher.py`) |
| Copper Zone & Via Stitching | **4** (`test_copper_zone_manager.py`) |
| Thermal Via Engine | **2** (`test_thermal_engine.py`) |
| FreeRouting Bridge | **4** (`test_freerouting_bridge.py`) |
| Unified Service Kernel | **1** (`test_service_kernel.py`) |
| Pipelines and Web API | **9** (`test_pipelines_and_web_api.py`) |
| RAG Hygiene and Immunization | **4** (`test_rag_hygiene.py`) |
| KiCad 10 CLI Validation | **Returncode 0 (Clean Export)** |
| Forge Studio unit tests | **9** (`test_ollama_native_stream`, `test_studio_session`) |
| Web Frontend Build | **Vite build returncode 0** |

---

## 🧠 RAG Knowledge Base

| Metric | Value (2026-08-30) |
|--------|---------------------|
| Total chunks | **5,708+** |
| `pinout` | 5,328 |
| `circuit_example` | 326 |
| `design_rule` | 13 |
| `component` | 20 |
| `support_circuit` | 9 |
| `design_experience` | 12 |
| Hybrid embed index loaded | **true** (`vectors.npy` manifest matches chunk count) |
| Backend | `hybrid` (dense + TF-IDF per `Pulse_cfg.json`) |

---

## 🤖 LLM Backends & Providers

| Backend | Role | Status |
|---------|------|--------|
| `primary` | Circuit synthesis (qwythos-9b-96k, 128k ctx) | ✅ Active (Modular provider architecture) |
| `atomic` | Fast JSON tasks; semantic review | ✅ **Verified live** |

---

## ⚡ FastMCP Server

| Metric | Value |
|--------|-------|
| Tools exposed | **36** (in `mcp_server/server.py`) |
| Domains | Simulation, RF, DRC, KiCad Bridge, Component DB, RAG, Layout, Supply Chain |

---

## 📱 Hardware Platforms & Reference Boards

| Board | Target | Comps | DRC Clearance | Routing Status |
|-------|--------|-------|---------------|----------------|
| **Flipper Killer MK II v5** | ESP32-S3 + Sub-GHz + NFC | 31 | Topological Pass | Native FreeRouting DSN / SES |
| **ESP32 LD2450 Radar + TFT** | ESP32-S3 + 24GHz Radar | 24 | Topological Pass | Automated Net Placement |
| **ESP32 TFT Console** | ESP32-S3 + ST7789 Display | 24 | Topological Pass | Automated Net Placement |
| **Synthetic Multi-Cell IoT** | Low Power Sensor Node | 9 | Topological Pass | Automated Net Placement |

---

## 🛠️ Workflows

1. [Fabrication pipeline (DRC gate)](../workflows/howto/fabrication_pipeline.md)
2. [Component management](../workflows/howto/component_management.md)
3. [ESP32 devboard MCP workflow](../workflows/howto/esp32_devboard_mcp.md)
