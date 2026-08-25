# PulseLab — Active Task Tracker

**Last Updated:** August 25, 2026 (Peer Review, Copper Pour Fixes, Courtyard Geometry & Design Rules Verified)  
**Project:** PulseLab Generative EDA Platform (`Pulse-main`)  
**Current Phase:** Phase 2 — Hardware Engines, Production Containerization & Web Studio Integration

---

## 1. Summary of Completed & Verified Tasks ✅

- [x] **Copper Pour Zone Serialization & Thermal Relief Spoke Rendering (2026-08-25)**:
  - Fixed P0 attribute mismatch in `app/main.py` (`_copper_zones` $\rightarrow$ `_zones`, `z.polygon` $\rightarrow$ `z.points`).
  - Added thermal relief crosshair spokes in `webapp/src/components/PCBViewer2D.tsx` for ground/0V-connected pads.
  - Eliminated orphan `PWR_GND_FLIPPER` copper pour generation on generic/NEMA-17 boards in `bridge/pcb_layout.py`.
- [x] **Package Specification Expansion & Continuous Rotation Courtyards (2026-08-25)**:
  - Added physical package specs for `QFN-24-1EP_4x4mm`, `Pololu_Breakout-16`, `USB_Micro-B`, `TerminalBlock_2pin_P5.08mm`, and `JST_XH_4pin` in `core/visual_inference.py`.
  - Upgraded `AutoPlacementEngine.get_component_bounds()` with continuous trigonometric rotation envelopes ($W \cdot \cos\theta + H \cdot \sin\theta$).
  - Added M3 corner mounting hole repulsion (4.5mm safety radius) in auto-placement collision resolution.
- [x] **Critical Architecture Audit & Dissonance Resolution (2026-08-25)**:
  - Standardized `pins: Dict[str, str]` as universal canonical SSOT, restricting `n1`/`n2` strictly to 2-terminal passives.
  - Disambiguated 4-chip architecture for NEMA-17 stepper driver synthesis (`U_ESP32`, `U_UART`, `U_STEPPER`, `U_REG`).
  - Documented audit in `docs/reviews/review_20260825_critical_architecture_audit.md`.
  - Verified **178/178 pytest tests passing 100%** and Vite bundle building clean.
- [x] **Flipper Killer MK II v1.0 Prototype Iterations (`v1.0.1` $\rightarrow$ `v1.0.4`)**:
  - MicroSD Card slot (`J_SD`) + Backside OLED report display header (`J_DISP` on `B.Cu`).
  - Achieved **0 unconnected items / 0 DRC connection errors** across all 4 release iterations.
- [x] **Guaranteed Placement Topology Enforcement (`bridge/pcb_builder.py`)**:
  - `PCBBuilder` automatically invokes `AutoPlacementEngine` for unpositioned components, eliminating origin stacking.
- [x] **100% SCH $\leftrightarrow$ PCB Reference Parity & DRC Gate Integration**:
  - Auto-generate mechanical mounting holes (`H1..H4`) and logo symbols (`LOGO1..LOGO2`) in `.kicad_sch` with `(in_bom no) (on_board yes)`.
  - Verified **25/25 reference designators match 100%** between `.kicad_sch` and `.kicad_pcb`.
  - Embedded `sch_pcb_crosscheck.py` directly into `KiCadBridge.run_drc()`.
- [x] **Pad Connection Modes & 0.5mm Thermal Peninsulas**:
  - Added `Pad.zone_connect` (`2` = solid) for ESP32 EPAD (pad 41) and AMS1117 tab (pin 2/4).
  - Configured $0.50\,\text{mm}$ thermal spoke bridge width formatting for clean peninsulas.
- [x] **Inter-Layer Copper Pour Stitching (`F.Cu` $\leftrightarrow$ `B.Cu`)**:
  - `PCBBuilder._finalize()` automatically injects 2D ground via stitching matrices linking top and bottom ground planes.
- [x] **Component Library Systematization & Decision Assistant Engine**:
  - Enriched 39 components across 5 project domains with official datasheet URLs, LCSC part numbers, footprint specs, and alternative trade-off notes.
  - Implemented `ComponentDB.find_candidates()`, `get_alternatives()`, and `inspect_component()`.
- [x] **Multi-Provider Supply Chain Fetcher Engine**:
  - Live side-by-side component search across **JLCPCB (LCSC)** and **PCBWay** with 24-hour disk caching (`ProviderFetchManager`).
  - Hardened local/remote MPN and part ID lookups.
- [x] **Repository Cleanup & Disk Reclaim**:
  - Relocated external research project `Cristales_Solares` to standalone repo `anarcoiris/Cristales_Solares` (reclaiming 258 MB).
  - Archived 36 root debug/test files into `_archive/root_scratch/` and 34 old output dirs into `output/_archive/`.
  - Removed stale `core/to-review/` directory.
- [x] **Documentation Modernization & Knowledge Base Alignment**:
  - Restructured `skills/` into domain hierarchy (`_corpus-meta/`, `ee-fundamentals/`, `schematic-rules/`, `tool-adapter/`, `_case-studies/`, `evaluation/`).
  - Rewrote root `README.md` and `docs/README.md` master index with 0 absolute/personal local path links.
- [x] **Production Containerization & GHCR Pipeline (2026-08-24)**:
  - Created multi-stage `Dockerfile` (Node 20 Alpine frontend build + Python 3.12 slim backend runtime).
  - Created `.github/workflows/docker-publish.yml` for automated GitHub Actions CI/CD to `ghcr.io/anarcoiris/pulse:latest` (278 MB image size).
  - Created PowerShell launcher `scripts/launch-pulselab.ps1` with `-Mode Container|Native`, `-Port`, `-Pull`, `-Build`, `-Stop`, `-Status`, `-Logs`, `-OpenBrowser`.
  - Integrated into Ollama Multi-GPU Service Orchestrator Dashboard (`C:\Users\soyko\Documents\Ollama\docker\`).
- [x] **Clean Dynamic Path Resolution & Llama.cpp Integration (2026-08-24)**:
  - Sanitized all hardcoded Windows user paths across scripts, Docker Compose files, and Python modules.
  - Dynamically resolve `llama-server` / Qwythos endpoints via `LLAMACPP_BASE_URL` or `PULSE_ATOMIC_BASE_URL` on port 11440.
- [x] **MCU Unused Pins & Datasheet Pinout Parity (2026-08-24)**:
  - Unused MCU pins in KiCad schematics (`.kicad_sch`) automatically receive explicit `(no_connect)` visual markers.
  - IPC-7351B standard pad numbering (Pin 1 counter-clockwise) aligned across physical footprints, symbols, and vector generators.
- [x] **Web Studio User Edition Drag-and-Drop Position Lock Fix (2026-08-24)**:
  - Added `user_placed: bool` and `fixed: bool` fields to `ComponentSpec` in `core/schema_validator.py`.
  - Preserved user $[X, Y]$ coordinates during `AutoPlacementEngine` macro seeding, force relaxation, and collision resolution.
  - Verified with `test_api_update_component_position_preserves_user_drag` (**178/178 pytest unit tests passing**).

---

## 2. Active Backlog & Next Action Items ⏳

### A. Core Pipeline & Schematic Cleaning
- [x] **Task 1: Passive Component Explicit Net Labeling**
  - Cleaned up single-occurrence fallback net names (`N1`, `N2`) in `bridge/schematic_generator.py` so only real signals receive schematic wire stub labels.

### B. Backend Services & Web API Integration
- [x] **Task 2: FastAPI Backend Gateway (`app/main.py`)**
  - Implemented `/api/v1/prompt-to-circuit`, `/api/v1/generate-pcb`, `/api/v1/presets`, `/api/v1/export/kicad`, `/api/v1/export/gerber`, `/api/v1/supply-chain/search`, and `/api/v1/supply-chain/replace`.
  - Added support for Local LLMs (Ollama) and Cloud LLMs (OpenAI GPT-4o, Google Gemini, Groq, OpenRouter, Anthropic) via `app/circuit_synthesizer.py`.
  - Integrated 2D vector primitives extraction and 3D WebGL mesh dimensional metadata generation.
- [x] **Task 3: Real-Time Stock Lookup & Part Replacement Connector**
  - Real-time stock lookup & auto-replacement connector for active BOM lines using `ProviderFetchManager` with JLCPCB vs PCBWay stock, pricing, and Basic/Extended catalog badges.

### C. Web UI & 3D Interactive Canvas (Phase 3)
- [x] **Task 4: Forge Studio Web Canvas (`webapp/`)**
  - Built full React + Vite + Tailwind studio UI in `webapp/`:
    - `webapp/src/components/PCBViewer2D.tsx` (2D multi-layer canvas with pan, zoom, net highlighting, and layer toggles).
    - `webapp/src/components/PCBViewer3D.tsx` (Photorealistic Three.js 3D WebGL PCB viewer with orbit controls, soldermask toggles, and component packages).
    - `webapp/src/components/SchematicViewer.tsx` (Interactive 2D schematic diagram).
    - `webapp/src/components/BOMSupplyChainTable.tsx` (Live BOM table with stock, pricing, and 1-click part replacement).
    - `webapp/src/components/DRCReportModal.tsx` (R001–R014 rules pass/fail report & 100% SCH $\leftrightarrow$ PCB parity check).
  - Verified 158/158 unit tests passing and verified live browser operation on `http://localhost:3000`.

### E. EDA Origin Alignment, Visual Grids & Design Rules Representation
- [x] **Task 6: Unified Board-Center Coordinate Normalization & Visual Grids**
  - Normalized all 2D vector primitives and 3D WebGL mesh geometry to exact board center `(0, 0)`.
  - Added pad rotation trigonometry (`rot_x = pad.x * cos_t + pad.y * sin_t`) for exact pad footprint alignment.
  - Implemented multi-mode grid selector (1.0mm metric, 5.0mm major, 2.54mm imperial 100 mil) and live cursor coordinate HUD.
  - Implemented interactive DRC clearance envelopes visualizer (0.20mm / 0.15mm rings around traces, pads, vias).

### J. Visual Inference, Hitbox Normalization & Interactive Visual Editing
- [x] **Task 11: Dedicated Visual Inference, Normalized Hitboxes & Interactive 2D Layout Editing**
  - Created `core/visual_inference.py` implementing normalized physical footprint dimensions for 50+ packages, courtyard bounding boxes (hitboxes), and 5-pass visual inspection gate (`VIS-001` through `VIS-005`).
  - Enhanced 2D and 3D visual rendering for all tracks (`F.Cu`/`B.Cu`), vias, drills, ICs (with Pin 1 markers), pin headers, buttons, and color-coded passive components.
  - Implemented interactive component selection, mouse drag-and-drop, selectable grid snapping (`1.0 mm`, `0.5 mm`, `2.54 mm`, `0.1 mm`, `Free`), live collision visualizer (green clear / red pulsing collision bounds), and rotation controls (`R` shortcut) in `webapp/src/components/PCBViewer2D.tsx`.
  - Wired up live re-routing via `@app.post("/api/v1/update-component-position")` and synchronized state across the web studio.
  - Added unit test suite `tests/test_visual_inference.py` (**163 / 163 tests passing 100%**).
  - Verified against `output/flipper_killer_mk_ii_0.9.82_unrouted` and all generative presets.

### K. Multi-Session Conversational AI Co-Pilot & Chatbox
- [x] **Task 12: Multi-Session Human + AI Assisted Building Chatbox**
  - Implemented `core/chat_session_manager.py` with multi-session persistence per project under `output/sessions/{project_id}/{session_id}.json`, context injection (active parts, nets, DRC findings, visual inspection score), and structured patch extraction.
  - Added backend chat endpoints in `app/main.py` (`/api/v1/chat/sessions`, `/api/v1/chat/message`, `/api/v1/chat/apply-patch`) supporting local `llama-server.exe` (port 11440) and cloud providers.
  - Created `webapp/src/components/AIChatDrawer.tsx` with session tabs (`+ New Chat`, delete, switch), markdown message rendering, quick suggestion prompt chips, and 1-click **"Apply Patch to Design"** cards.
  - Wired up bidirectional design updates in `webapp/src/App.tsx` with live re-routing.
  - Created unit test suite `tests/test_chat_session_manager.py` (**168 / 168 tests passing 100%**).

### L. Phase A: Schematic Rules, Component Knowledge Base & Corpus Expansion
- [x] **Task 13: Formal Electrical Rules & Neutral Intermediate Evaluator**
  - Implemented `skills/schematic-rules/rules/i2c_bus_pullups.yaml` + narrative skill (I2C pull-up to power rail vs pull-down prevention).
  - Implemented `skills/schematic-rules/rules/boot_strap_pins.yaml` + narrative skill (GPIO0/BOOT strapping vs EN reset delay).
  - Implemented `skills/component-library/parts/esp32-s3.yaml` (48-pin reference schema with pin roles).
  - Implemented `skills/component-library/parts/{ssd1306,pn532,cc1101}.yaml` peripheral pin role specifications.
  - Implemented `skills/component-library/skills/led-modeling-gap.md` (`kind: led` with anode/cathode and current limiting).
  - Implemented `skills/pcb-rules/rules/stackup_basics.yaml` + skill (2-layer and 4-layer reference plane rules).
  - Implemented `skills/tool-adapter/kicad/SKILL.md` (Neutral KiCad translation layer).
  - Implemented `skills/orchestration/skills/iteration-loop.md` (Stopping criteria, fix priority order, corpus promotion).
  - Built `core/corpus_evaluator.py` deterministic rule evaluator and `tests/test_corpus_rules.py` (**173 / 173 tests passing 100%**).

---

## 3. Next Execution Phase: Phase B Backlog ⏳

### Phase B: Calibration Forge, Benchmarking & Core Cleanups
- [ ] **Task 14: Clean Session 4b A/B Benchmark & Rule-Trim Decision**
  - Run 10-run clean benchmark (Prompt Rules vs RAG Injection) with dual-backend guardrails.
  - Investigate and resolve the $12.5\times$ peripheral pin coverage anomaly on CC1101/PN532.
  - Optimize LLM context usage to minimize synthesis retries ($<3$ attempts).
- [ ] **Task 15: Architectural Refactoring & Netlist Cleanups**
  - Migrate from string-based node names to first-class, typed `Net` objects in `CircuitGraph`.
  - Unify `FootprintRegistry` centralizing physical dimensions, pads, and courtyard keepouts.
  - Implement snapshot-based transactional undo/redo history stack across 2D/3D visual CAD editors.





