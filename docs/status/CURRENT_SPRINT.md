# Current sprint — Robustez Geométrica, CAD Interactivo y Co-Pilot IA (Agosto 2026)

> **Role:** living  
> **Status:** active  
> **Source of truth for:** session order, blockers, and next actions  
> **Last verified:** 2026-08-25  
> **See also:** [`../calibration_forge/index.md`](../calibration_forge/index.md) · [`../roadmap.md`](../roadmap.md) · [`../status/FORGE_STATUS.md`](./FORGE_STATUS.md)

## Execution order (Agosto Sprint)

**PCB Builder** ✅ → **Audit Gate R001-R014** ✅ → **Thermal & Ground Zone Engines** ✅ → **Component DB & Multi-Provider Fetchers** ✅ → **100% SCH↔PCB Parity** ✅ → **FastAPI Backend & Web UI** ✅ → **Visual Inference & 2D Drag CAD** ✅ → **Multi-Session Co-Pilot Chat** ✅ → **Peer Review & Courtyard Precision** ✅

## Where we are (25-aug-2026)

| Hito / Módulo | Estado | Documento / Artefacto |
|---|---|---|
| Automated PCB Builder | ✅ Completado | `bridge/pcb_builder.py` |
| Topological Audit Gate (R001-R014) | ✅ Completado | `core/kicad_audit.py` (15 unit tests) |
| Thermal Management Engine | ✅ Completado | `core/thermal_engine.py` (grid $3 \times 3$ en EPAD) |
| Ground Pour & Via Stitching Grid | ✅ Completado | `core/copper_zone_manager.py` (planos 0V + stitching) |
| Systematized Component DB & Candidates | ✅ Completado | `core/component_db.py` (39 componentes) |
| Multi-Provider Supply Chain Engine | ✅ Completado | `core/providers/` (JLCPCB + PCBWay con cache 24h) |
| Cross-check Esquemático↔PCB | ✅ Completado | `core/sch_pcb_crosscheck.py` (100% coincidencia) |
| Multi-Provider AI Circuit Synthesizer | ✅ Completado | `app/circuit_synthesizer.py` (Local + Cloud LLMs) |
| FastAPI Backend Gateway | ✅ Completado | `app/main.py` (19 endpoints REST) |
| Forge Studio Web Canvas (2D/3D WebGL) | ✅ Completado | `webapp/` (React + Three.js + Tailwind) |
| Visual Inference & 9-Pass Quality Gate | ✅ Completado | `core/visual_inference.py` (VIS-001..VIS-009) |
| Interactive 2D Drag-and-Drop CAD | ✅ Completado | `webapp/src/components/PCBViewer2D.tsx` |
| Multi-Session Co-Pilot & Patch Apply | ✅ Completado | `core/chat_session_manager.py`, `AIChatDrawer.tsx` |
| Copper Pour Serialization Fix & Thermal Spokes | ✅ Completado | `app/main.py`, `PCBViewer2D.tsx`, `pcb_layout.py` |
| Trigonometric Courtyards & Package Specs | ✅ Completado | `core/visual_inference.py`, `auto_placement.py` |
| Mounting Hole Repulsion Zones | ✅ Completado | `core/auto_placement.py` (radio de seguridad 4.5mm) |

## Next Phase Execution Plan

### Phase A: Schematic Rules, Component Knowledge Base & Corpus Expansion (Completed ✅)
- Formal electrical rules for I2C pullups, boot strapping, ESP32-S3, OLED SSD1306, PN532, CC1101, and 2/4-layer stackups verified via `core/corpus_evaluator.py`.

### Phase B: Calibration Forge, Benchmarking & Core Cleanups (Active ⏳)
1. **Benchmark**: Clean Session 4b A/B run (Prompt Rules vs. RAG Injection), peripheral pin coverage anomaly resolution.
2. **Architecture**: First-class typed `Net` objects in `CircuitGraph`, centralized `FootprintRegistry`, transactional undo/redo snapshotting.

## Key numbers (25-aug-2026)

- Tests: **178** passing across **30** test modules (`pytest tests/ -q` en 35.45s, 100% pass rate)
- API Integration Tests: **12/12** passing (`tests/test_api_gateway.py`, `tests/test_chat_session_manager.py`)
- Visual Inference Tests: **9/9** passing (`tests/test_visual_inference.py`)
- RAG: **5,708** chunks (5,328 `pinout`, 326 `circuit_example`, 80.06% description density)
- MCP tools: **31** (`mcp_server/server.py`)
- Web Studio: **4** primary viewports + **1** Multi-Session AI Co-Pilot Drawer + **1** Topological DRC Gate Modal
