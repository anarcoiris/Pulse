# PulseLab Forge Roadmap

> **Role:** living  
> **Status:** active  
> **Source of truth for:** product phases and long-term themes (not day-to-day sprint blockers)  
> **Last verified:** 2026-07-07  
> **See also:** [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) · [`calibration_forge/index.md`](./calibration_forge/index.md)

## Currently Active: Phase 1 & 2 (Stability & Professionalism)

### Connectivity Engine (In Progress)
- [x] Wire-aware node detection.
- [ ] Multi-wire net propagation logic.
- [ ] Visual verification of complex nodes (BANCO in EMP circuit).

### Hardware Professionalization
- [x] Dedicated switch footprints (Tactile 6x6mm).
- [x] One-click Gerber Export (via `kicad-cli`).
- [x] Bill of Materials (BOM) generator.
- [x] **DRC Gate**: Automated safety check before export.
- [x] **Multi-platform**: Linux/macOS support for fabrication.
- [ ] Footprint selection UI in Properties Panel.
- [ ] Confirmation dialog for footprint overrides.
- [x] **PulseLogger**: Unified debug sink (`core/logger.py` — singleton, AI context buffer) **wired in** (06-jul-2026): `bridge/pcb_layout.py::autoroute()` (A* attempts/nodes explored), `bridge/gerber_export.py` (DRC/gerbers/drill/position/svg steps), `knowledge/circuit_synthesizer.py` and `knowledge/semantic_reviewer.py` (`ai_review` around LLM calls), plus the two `record_design_outcome()` call sites (previously silent `except: pass`, now logged). The AI Context Buffer (`get_context()`) is also injected into `circuit_synthesizer.py`'s JSON-decode retry path. See [`dormant_features_audit.md`](./calibration_forge/dormant_features_audit.md) §Resultado for details.
- [x] **Autorouter with collision avoidance**: A* implementation with pad clearance dilation and via-cost penalties (`bridge/pcb_layout.py::autoroute`), wired into `bridge/pcb_builder.py`. Resolves the gap tracked in the 23-Apr-2026 review.

---

## Future Goals

### Phase 3: Premium UI/UX (Aesthetics)
- [x] **Forge Studio CLI** — headless Rich REPL for streaming LLM debug (`python -m studio`); see [`calibration_forge/forge_studio.md`](./calibration_forge/forge_studio.md)
- [ ] **Forge Studio web canvas** — live schematic/PCB viewer (deferred; CLI v1 done)
- [ ] "Cyber Night" theme implementation.
- [ ] Simulation-responsive Wire Glow (Glow proportional to Voltage).
- [ ] Animated background particles and glassmorphism panels.
- [ ] Search/Selection tool for "Identified elements".

### Phase 4: Extended Automation
- [x] Automatic Design Rule Check (DRC) integration.
- [x] 3D Preview bridge (via KiCad CLI).
- [x] Support for external KiCad footprint libraries.
- [x] Interactive Footprint library browser in UI.
- [x] Sincronizar documentación y workflows.
- [x] Integrar `kicad-cli` cross-platform.
- [x] Ejecutar validación de DRC estricta antes de exportar Gerbers.
- [x] Mapear footprints de catálogo SMD moderno con `add_raw_footprint`.
- [x] Entrenar motor de Generación de Circuitos (`circuit_synthesizer.py`).

### Phase 5: High-Voltage Specialization
- [ ] Spark gap component model.
- [ ] Transmission line (coaxial) simulation model.
- [ ] RF keep-out zone automatic generation for high-freq pulse paths.

---

## Reviews & Research

Technical reviews (chronological, latest first):
- [`pulselab_review_05072026.md`](./reviews/pulselab_review_05072026.md) — current state recap, corrections to the April review, and 3 open research lines (see below).
- [`pulselab_review_23042026.md`](./reviews/pulselab_review_23042026.md) — superseded; kept as historical record.

Active research lines (Calibration Forge, see [`calibration_forge/index.md`](./calibration_forge/index.md) for the full index):
- [`pin_model_coverage.md`](./calibration_forge/pin_model_coverage.md) — ~~MCU pin tables truncated before LLM~~ **resuelto y re-confirmado sin regresión** (Session 3 fix + Session 4a migration to RAG, both 100% on `esp32_sensors`).
- [`kicad_symbol_kb.md`](./calibration_forge/kicad_symbol_kb.md) — ~~hand-maintain `pinouts_library.json`~~ **resuelto** (Session 4a): pinouts now sourced from a real KiCad install (5320 symbols / 29 libraries indexed) via RAG `chunk_type="pinout"`.
- [`knowledge_base_fidelity.md`](./calibration_forge/knowledge_base_fidelity.md) — ~~natural-language design intent dropped during RAG ingestion~~ **resuelto** (Session 1).
- [`prompt_vs_rag_balance.md`](./calibration_forge/prompt_vs_rag_balance.md) — Session 4b parte 1 (A/B confundido) recorded 06-jul; clean re-run pending after 4d verify. See [`calibration_forge/pipelines/llm_output_pipeline.md`](./calibration_forge/pipelines/llm_output_pipeline.md) §Resultado.
- [`dormant_features_audit.md`](./calibration_forge/dormant_features_audit.md) — ~~PulseLogger and design_experience loop not integrated~~ **resuelto** (Session 2).
