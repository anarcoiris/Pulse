# PulseLab Forge Roadmap

> **Role:** living  
> **Status:** active  
> **Source of truth for:** product phases, architectural milestones, and long-term themes  
> **Last verified:** 2026-08-15  
> **See also:** [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) · [`last_session_review.md`](./last_session_review.md)

---

## Currently Active: Phase 1 (Completed) & Phase 2 (Expanded Hardware & SCH↔PCB Parity)

### Phase 1: Connectivity & Core Placement Engine (Completed ✅)
- [x] **Topological Audit Gate (`core/kicad_audit.py`)**: 14 strict structural rules (R001-R014) pre-routing.
- [x] **Automated S-expression PCB Builder (`bridge/pcb_builder.py`)**: KiCad 10.0 / 8.0 unified S-expr generator.
- [x] **2D Auto-Placement Engine (`core/auto_placement.py`)**: Hooke attraction + Coulomb repulsion + hardware placement heuristics.
- [x] **Schema Validator (`core/schema_validator.py`)**: Pydantic v2 structured circuit validation.
- [x] **0 DRC Error Milestone**: Achieved 0 unconnected pads on `v0.9.82`, `v0.9.83`, `v0.9.2-A..D`, and `v1.0.1`..`v1.0.4` variants.

---

### Phase 2: Expanded Hardware Engines & Schematic-PCB Parity (Active ⏳)

#### A. Thermal Management Engine (Completed ✅)
- [x] **EPAD Thermal Via Arrays (`core/thermal_engine.py`)**: Automatic $3 \times 3$ thermal via grid generation for IC ground pads (ESP32-S3 Pad 41).
- [x] **Thermal Relief Spoke Control**: Per-zone and per-pad thermal spoke width (`thermal_bridge_width`) and gap (`thermal_gap`) parameters in S-expressions.

#### B. Copper Pour & 0V Reference Plane Manager (Completed ✅)
- [x] **Automated 0V Reference Planes (`core/copper_zone_manager.py`)**: Automatic double-sided `PWR_GND` copper pour generation on `F.Cu` and `B.Cu`.
- [x] **Ground Via Stitching Grid**: Algorithmic via stitching array linking top and bottom ground planes.
- [x] **Split Ground Plane Isolation**: Dynamic boundary calculation for isolated grounds (`PWR_GND` vs `PWR_GND_FLIPPER`).

#### C. FreeRouting Auto-Router Bridge (Completed ✅)
- [x] **Automated Specctra DSN Export (`bridge/freerouting_bridge.py`)**: `kicad-cli pcb export dsn` bridge.
- [x] **Headless FreeRouting Runner**: CLI wrapper executing FreeRouting JAR for automated trace routing.
- [x] **Specctra SES Back-Annotation**: `kicad-cli pcb import ses` bridge for applying routed traces back to `.kicad_pcb`.

#### D. Stencil Logos & Graphical Artwork Engine (Completed ✅)
- [x] **Vector/Bitmap Logo Ingestion (`bridge/graphics_engine.py`)**: Convert SVG/DXF graphics into KiCad `gr_poly`/`fp_poly` primitives.
- [x] **Multi-Layer Stencil Placement**: Support logo rendering on `F.Cu`, `B.Cu`, `F.SilkS`, and `B.SilkS`.

#### E. Schematic $\leftrightarrow$ PCB Parity & Verification Engine (Active ⏳)
- [x] **100% SCH $\leftrightarrow$ PCB Reference Parity**: Auto-generate mechanical mounting holes (`H1..H4`) and logo symbols (`LOGO1..LOGO2`) in `.kicad_sch` with `(in_bom no) (on_board yes)` flags (25/25 reference designators matched).
- [ ] **Automated Cross-Check Gate Integration**: Embed `sch_pcb_crosscheck.py` directly into `KiCadBridge.run_drc()` for automatic SCH $\leftrightarrow$ PCB net and reference validation.
- [ ] **Explicit Net Labeling**: Eliminate generic fallback net labels (`N1`, `N2`) in `SchematicGenerator`.

#### F. FastAPI Backend Gateway & Supply Chain (Active ⏳)
- [ ] **FastAPI Backend Gateway (`app/main.py`)**: Expose `/api/v1/generate-pcb` endpoint.
- [ ] **JLCPCB / LCSC Stock Connector**: Real-time stock lookup & auto-replacement connector for active BOM lines.
- [ ] **LLM Context & Prompt Optimization**: Maintain multi-turn prompt stability with < 3 retries on complex circuits.

---

## Future Goals

### Phase 3: Premium Web UI/UX & WebGL 3D Viewer
- [x] **Forge Studio CLI** — headless Rich REPL (`python -m studio`).
- [ ] **Forge Studio Web Canvas** — Next.js / Vite React frontend with live 2D SVG schematic/PCB viewer.
- [ ] **WebGL 3D PCB Viewer** — Interactive 3D board rendering with component models.
- [ ] **"Cyber Night" Dark Theme** — Dynamic UI styling with reactive wire glow.
