# PulseLab Forge Roadmap

> **Role:** living  
> **Status:** active  
> **Source of truth for:** product phases and long-term themes (not day-to-day sprint blockers)  
> **Last verified:** 2026-08-06  
> **See also:** [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) · [`calibration_forge/index.md`](./calibration_forge/index.md)

## Currently Active: Phase 1, 2 & August Sprint (Robustness & Geometry)

### Connectivity & Topological Engine
- [x] Wire-aware node detection.
- [x] **Topological Audit Gate (`core/kicad_audit.py`)**: 14 reglas estructurales estrictas (R001-R014) pre-ruteo.
- [ ] Multi-wire net propagation logic.
- [ ] Visual verification of complex nodes (BANCO in EMP circuit).

### Hardware Professionalization & Generation
- [x] Dedicated switch footprints (Tactile 6x6mm).
- [x] One-click Gerber Export (via `kicad-cli`).
- [x] Bill of Materials (BOM) generator.
- [x] **DRC Gate**: Automated safety check before export.
- [x] **Multi-platform**: Linux/macOS support for fabrication.
- [x] **Automated S-expression PCB Builder (`bridge/pcb_builder.py`)**: Generación nativa de `.kicad_pcb` unificada.
- [x] **PulseLogger**: Unified debug sink (`core/logger.py`).
- [ ] **A* Autorouter Geometric Clearance Engine**: Dilación de reglas de separación física para eliminar errores de clearance en DRC.
- [ ] Footprint selection UI in Properties Panel.

---

## Future Goals

### Phase 3: Premium UI/UX (Aesthetics)
- [x] **Forge Studio CLI** — headless Rich REPL for streaming LLM debug (`python -m studio`); see [`calibration_forge/forge_studio.md`](./calibration_forge/forge_studio.md)
- [ ] **Forge Studio web canvas** — live schematic/PCB viewer (deferred; CLI v1 done)
- [ ] "Cyber Night" theme implementation.
- [ ] Simulation-responsive Wire Glow (Glow proportional to Voltage).

### Phase 4: Extended Automation & LLM Infrastructure
- [x] Automatic Design Rule Check (DRC) integration.
- [x] 3D Preview bridge (via KiCad CLI).
- [x] Support for external KiCad footprint libraries.
- [x] Interactive Footprint library browser in UI.
- [x] **Modular LLM Providers (`knowledge/providers/`)**: Soporte multi-backend local/cloud.
- [x] **Contexto Ampliado 128k (`circuit_agent.py`)**: Agente multicapa con seguimiento de estado.
- [ ] **Estabilización de Contexto LLM 128k**: Optimización de prompts para reducir reintentos (<3) en circuitos complejos.
- [ ] **Fix Bug Métrica Cobertura de Pines**: Corrección de cálculo de pines extraños (>100%).

### Phase 5: High-Voltage Specialization
- [ ] Spark gap component model.
- [ ] Transmission line (coaxial) simulation model.
- [ ] RF keep-out zone automatic generation for high-freq pulse paths.

---

## Reviews & Research

Technical reviews (chronological, latest first):
- [`pulselab_review_18072026.md`](./reviews/pulselab_review_18072026.md) — supervisor review: sprint discipline, structural hygiene, KPI progress, 12 action items.
- [`pulselab_review_05072026.md`](./reviews/pulselab_review_05072026.md) — state recap, corrections to April review, 3 open research lines.
- [`pulselab_review_23042026.md`](./reviews/pulselab_review_23042026.md) — superseded; kept as historical record.

Active research lines (Calibration Forge, see [`calibration_forge/index.md`](./calibration_forge/index.md) for the full index):
- [`pin_model_coverage.md`](./calibration_forge/pin_model_coverage.md) — ~~MCU pin tables truncated before LLM~~ **resuelto y re-confirmado sin regresión** (Session 3 fix + Session 4a migration to RAG, both 100% on `esp32_sensors`).
- [`kicad_symbol_kb.md`](./calibration_forge/kicad_symbol_kb.md) — ~~hand-maintain `pinouts_library.json`~~ **resuelto** (Session 4a): pinouts now sourced from a real KiCad install (5320 symbols / 29 libraries indexed) via RAG `chunk_type="pinout"`.
- [`knowledge_base_fidelity.md`](./calibration_forge/knowledge_base_fidelity.md) — ~~natural-language design intent dropped during RAG ingestion~~ **resuelto** (Session 1).
- [`prompt_vs_rag_balance.md`](./calibration_forge/prompt_vs_rag_balance.md) — Session 4b clean re-run pending (**4d blocker resolved** 16-jul). See [`calibration_forge/pipelines/llm_output_pipeline.md`](./calibration_forge/pipelines/llm_output_pipeline.md) §Resultado.
- [`dormant_features_audit.md`](./calibration_forge/dormant_features_audit.md) — ~~PulseLogger and design_experience loop not integrated~~ **resuelto** (Session 2).
