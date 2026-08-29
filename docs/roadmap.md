# PulseLab Forge Roadmap

> **Role:** living  
> **Status:** active  
> **Source of truth for:** product phases, architectural milestones, and long-term themes  
> **Last verified:** 2026-08-30  
> **See also:** [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) · [`status/FORGE_STATUS.md`](./status/FORGE_STATUS.md)

---

## Completed & Active Milestones

### Phase 1: Connectivity & Core Placement Engine (Completed ✅)
- [x] **Topological Audit Gate (`core/kicad_audit.py`)**: 14 strict structural rules (R001-R014) pre-routing.
- [x] **Automated S-expression PCB Builder (`bridge/pcb_builder.py`)**: KiCad 10.0 / 8.0 unified S-expr generator.
- [x] **2D Auto-Placement Engine (`core/auto_placement.py`)**: Hooke attraction + Coulomb repulsion + hardware placement heuristics.
- [x] **Schema Validator (`core/schema_validator.py`)**: Pydantic v2 structured circuit validation.
- [x] **0 DRC Error Milestone**: Achieved 0 unconnected pads on `v0.9.82`, `v0.9.83`, `v0.9.2-A..D`, and `v1.0.1`..`v1.0.4` variants.

---

### Phase 2: Expanded Hardware Engines, SCH↔PCB Parity & Component Database (Completed ✅)

#### A. Thermal Management Engine (Completed ✅)
- [x] **EPAD Thermal Via Arrays (`core/thermal_engine.py`)**: Automatic $3 \times 3$ thermal via grid generation for IC ground pads (ESP32-S3 Pad 41).
- [x] **Solid Zone Pad Connections**: Support `Pad.zone_connect = 2` (`solid`) for high-current power tabs and ground thermal pads.

#### B. Copper Pour & 0V Reference Plane Manager (Completed ✅)
- [x] **Automated 0V Reference Planes (`core/copper_zone_manager.py`)**: Automatic double-sided `PWR_GND` copper pour generation on `F.Cu` and `B.Cu`.
- [x] **Ground Via Stitching Grid**: Automatic inter-layer ground via stitching matrix linking top and bottom ground planes.
- [x] **0.50mm Thermal Peninsulas**: Configured $0.50\,\text{mm}$ thermal spoke width formatting for sturdy copper peninsulas.

#### C. FreeRouting Auto-Router Bridge (Completed ✅)
- [x] **Automated Specctra DSN Export (`bridge/freerouting_bridge.py`)**: `kicad-cli pcb export dsn` bridge.
- [x] **Headless FreeRouting Runner**: CLI wrapper executing FreeRouting JAR for automated trace routing.
- [x] **Specctra SES Back-Annotation**: `kicad-cli pcb import ses` bridge for applying routed traces back to `.kicad_pcb`.

#### D. Stencil Logos & Graphical Artwork Engine (Completed ✅)
- [x] **Vector/Bitmap Logo Ingestion (`bridge/graphics_engine.py`)**: Convert SVG/DXF graphics into KiCad `gr_poly`/`fp_poly` primitives.
- [x] **Multi-Layer Stencil Placement**: Support logo rendering on `F.Cu`, `B.Cu`, `F.SilkS`, and `B.SilkS`.

#### E. Schematic $\leftrightarrow$ PCB Parity & Verification Engine (Completed ✅)
- [x] **100% SCH $\leftrightarrow$ PCB Reference Parity**: Auto-generate mechanical mounting holes (`H1..H4`) and logo symbols (`LOGO1..LOGO2`) in `.kicad_sch` with `(in_bom no) (on_board yes)` flags (25/25 reference designators matched).
- [x] **Automated Cross-Check Gate Integration**: Embedded `sch_pcb_crosscheck.py` directly into `KiCadBridge.run_drc()` for automatic SCH $\leftrightarrow$ PCB net and reference validation.

#### F. Guaranteed Placement Topology & Component Database Systematization (Completed ✅)
- [x] **Guaranteed Auto-Placement Fallback**: `PCBBuilder` automatically invokes `AutoPlacementEngine` for unpositioned components.
- [x] **Systematized 39-Component Catalog**: Enriched `knowledge/data/components.json` with LCSC part numbers, official datasheet URLs, package specs, and alternative trade-off notes.
- [x] **Interactive Decision Assistant API**: Implemented `ComponentDB.find_candidates()`, `get_alternatives()`, and `inspect_component()`.

---

### Phase 2.5: Backend API Gateway & Multi-Provider Supply Chain (Completed ✅)
- [x] **FastAPI Backend Gateway (`app/main.py`)**: 19 endpoints providing end-to-end circuit synthesis, placement, thermal/zone processing, routing, supply chain search/replace, chat sessions, and KiCad/Gerber export.
- [x] **Multi-Provider AI Circuit Synthesizer (`app/circuit_synthesizer.py`)**: Support for Local LLMs (Ollama / Qwythos) and Cloud LLMs (OpenAI GPT-4o, Google Gemini, Groq, OpenRouter, Anthropic).
- [x] **JLCPCB / PCBWay Supply Chain Connector**: Real-time stock lookup & 1-click auto-replacement connector with Basic/Extended library tags.
- [x] **Passive Component Explicit Net Labeling**: Cleaned up single-occurrence fallback net names (`N1`, `N2`) in `SchematicGenerator`.

---

### Phase 3: Premium Web UI/UX & WebGL 3D Viewer (Completed ✅)
- [x] **Forge Studio CLI** — headless Rich REPL (`python -m studio`).
- [x] **Forge Studio Web Canvas (`webapp/`)** — React + Vite + Tailwind frontend with live 2D SVG multi-layer schematic/PCB viewer with interactive net highlighting and layer toggles (`F.Cu`, `B.Cu`, `F.SilkS`, `Pads`, `Vias`, `Zones`).
- [x] **Three.js Photorealistic 3D PCB Viewer** — Interactive 3D WebGL board rendering with camera orbit controls, FR4 matte soldermask, copper traces, and component 3D packages (ESP32 RF shield, USB-C receptacle, tactile buttons, SOT-223, LEDs, 0805 SMD passives).
- [x] **Topological DRC & Quality Gate Modal** — Real-time R001–R014 rules pass/fail reporting and 100% SCH $\leftrightarrow$ PCB reference parity verification.
- [x] **"Cyber Night" Dark Studio Theme** — Cyberpunk CAD aesthetic with reactive net highlight glow and preset selectors.

---

### Phase 4: Visual Inference, Courtyard Normalization & Interactive 2D CAD Layout (Completed ✅)
- [x] **Visual Inference Engine (`core/visual_inference.py`)**: Standardized 50+ physical package dimensions ($W \times H \times T$), pin counts, lead geometry, and IPC-7351B courtyard safety margins ($+0.25\,\text{mm}$ to $+0.50\,\text{mm}$).
- [x] **5-Pass Visual Inspection Gate (`VIS-001`..`VIS-005`)**: Courtyard overlap/collision audit, board edge keepouts ($\ge 2.5\,\text{mm}$), decoupling capacitor proximity ($\le 8.0\,\text{mm}$), thermal relief via density, and unrouted net airwire detection.
- [x] **Interactive 2D Drag-and-Drop Canvas (`PCBViewer2D.tsx`)**: Real-time mouse dragging with selectable grid snapping (`1.0 mm`, `0.5 mm`, `2.54 mm / 100 mil`, `0.1 mm`, `Free`), live green/red pulsing collision visualization, and keyboard rotation shortcuts (`R` / `Shift+R`).
- [x] **Dynamic Re-Routing on Drop (`/api/v1/update-component-position`)**: Seamless layout re-computation and 2D/3D state synchronization.

---

### Phase 5: Multi-Session Conversational AI Co-Pilot & Chatbox (Completed ✅)
- [x] **Project Chat Session Manager (`core/chat_session_manager.py`)**: Multiple isolated, switchable chat sessions per project persisted in `output/sessions/{project_id}/{session_id}.json`.
- [x] **Design Context-Aware System Prompts**: Real-time injection of active circuit components, nets, board dimensions, DRC findings, and visual score into LLM context.
- [x] **Structured Circuit Patch Proposals (`circuit_patch`)**: AI proposes discrete `ADD_COMPONENT`, `REMOVE_COMPONENT`, `UPDATE_COMPONENT`, and `REROUTE` actions.
- [x] **Web Studio Co-Pilot Drawer (`webapp/src/components/AIChatDrawer.tsx`)**: Tabbed session header, streaming message rendering, quick suggestion chips, and 1-click **"⚡ Apply Patch to Design"** cards with instant live re-routing.

### Phase 6: Continuous Rotation Courtyards, Zone Geometry & Design Rules (Completed ✅)
- [x] **Zone Serialization & Thermal Relief Spoke Rendering**: Fixed P0 attribute mismatch in `app/main.py` (`_copper_zones` $\rightarrow$ `_zones`, `z.polygon` $\rightarrow$ `z.points`) and added thermal crosshair spokes in `PCBViewer2D.tsx`.
- [x] **Trigonometric Rotation Envelopes**: Continuous $W \cdot \cos\theta + H \cdot \sin\theta$ OBB bounding box projection for arbitrary component angles.
- [x] **Package Specification Expansion**: Added real physical specifications for `QFN-24-1EP_4x4mm`, `Pololu_Breakout-16`, `USB_Micro-B`, `TerminalBlock_2pin_P5.08mm`, and `JST_XH_4pin` in `core/visual_inference.py`.
- [x] **Corner Mounting Hole Avoidance**: Radial keepout avoidance in `_resolve_geometric_collisions()` with 4.5mm safety clearance to guarantee no components overlap with M3 screw heads.

---

## Upcoming Phases & Workstreams

### Phase A: Schematic Rules, Component Knowledge Base & Corpus Expansion (Completed ✅)
*Focus: Formalizing hardware domain rules, peripheral yaml models, and stackup validation.*
- [x] **Schematic & Component Rules**: `schematic-rules/rules/i2c_bus_pullups.yaml`, `boot_strap_pins.yaml`, `component-library/parts/{esp32-s3,ssd1306,pn532,cc1101}.yaml`, `led-modeling-gap.md`.
- [x] **Physical Layout & Adapter Rules**: `pcb-rules/rules/stackup_basics.yaml`, `tool-adapter/kicad/SKILL.md`, `orchestration/skills/iteration-loop.md`.
- [x] **Evaluator Engine & Test Suite**: `core/corpus_evaluator.py` & `tests/test_corpus_rules.py` (5/5 tests passing).

### Phase B: Calibration Forge, Benchmarking & Core Cleanups (Active ⏳)
*Focus: LLM synthesis benchmark, context optimization, and core architecture refactoring.*
1. **Clean Session 4b A/B Benchmark (`prompt_vs_rag_balance.md`)**:
   - Run 10-run clean benchmark (Prompt Rules vs. RAG injection) with dual-backend guardrails.
   - Investigate peripheral pin coverage anomaly on CC1101/PN532.
   - Optimize LLM context usage to minimize synthesis retries ($<3$ attempts).
2. **Architectural & Core Cleanups (`ARCHITECTURE_VIOLATIONS.md`)**:
   - First-class typed `Net` objects in `CircuitGraph`.
   - Centralized `FootprintRegistry` unifying footprints and pin mappings.
   - Transactional undo/redo snapshot serialization across 2D/3D editors.
