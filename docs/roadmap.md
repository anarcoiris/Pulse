# PulseLab Forge Roadmap

> **Role:** living  
> **Status:** active  
> **Source of truth for:** product phases, architectural milestones, and long-term themes  
> **Last verified:** 2026-08-15  
> **See also:** [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) · [`last_session_review.md`](./last_session_review.md)

---

## Currently Active: Phase 1 (Completed) & Phase 2 (Expanded EDA & Backend)

### Phase 1: Connectivity & Core Placement Engine (Completed ✅)
- [x] **Topological Audit Gate (`core/kicad_audit.py`)**: 14 strict structural rules (R001-R014) pre-routing.
- [x] **Automated S-expression PCB Builder (`bridge/pcb_builder.py`)**: KiCad 10.0 / 8.0 unified S-expr generator.
- [x] **2D Auto-Placement Engine (`core/auto_placement.py`)**: Hooke attraction + Coulomb repulsion + hardware placement heuristics.
- [x] **Schema Validator (`core/schema_validator.py`)**: Pydantic v2 structured circuit validation.
- [x] **0 DRC Error Milestone**: Achieved 0 unconnected pads on `v0.9.82`, `v0.9.83`, and `v0.9.2-A..D` variants.

---

### Phase 2: Expanded Hardware Engines & Backend Integration (Active ⏳)

#### A. Thermal Management Engine
- [ ] **EPAD Thermal Via Arrays**: Automatic $N \times M$ thermal via grid generation for IC ground pads (e.g. ESP32-S3 Pad 41).
- [ ] **Thermal Relief Spoke Control**: Per-zone and per-pad thermal spoke width (`thermal_bridge_width`) and gap (`thermal_gap`) parameters in S-expressions.

#### B. Copper Pour & 0V Reference Plane Manager
- [ ] **Automated 0V Reference Planes**: Automatic double-sided `PWR_GND` copper pour generation on `F.Cu` and `B.Cu`.
- [ ] **Ground Via Stitching Grid**: Algorithmic via stitching array linking top and bottom ground planes.
- [ ] **Split Ground Plane Isolation**: Dynamic boundary calculation for isolated grounds (`PWR_GND` vs `PWR_GND_FLIPPER`).

#### C. FreeRouting Auto-Router Bridge
- [ ] **Automated Specctra DSN Export**: `kicad-cli pcb export dsn` bridge.
- [ ] **Headless FreeRouting Runner**: CLI wrapper executing FreeRouting JAR for automated trace routing.
- [ ] **Specctra SES Back-Annotation**: `kicad-cli pcb import ses` bridge for applying routed traces back to `.kicad_pcb`.

#### D. Stencil Logos & Graphical Artwork Engine
- [ ] **Vector/Bitmap Logo Ingestion**: Convert SVG/DXF graphics into KiCad `gr_poly`/`fp_poly` primitives.
- [ ] **Multi-Layer Stencil Placement**: Support logo rendering on `F.Cu`, `B.Cu`, `F.SilkS`, and `B.SilkS`.

#### E. FastAPI Backend Gateway & Supply Chain
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

### Phase 4: High-Voltage & RF Specialization
- [ ] Spark gap component model generator.
- [ ] Transmission line (coaxial / microstrip) impedance calculation model.
- [ ] RF keep-out zone automatic generation for high-frequency antenna paths (e.g. CC1101 / nRF24).
