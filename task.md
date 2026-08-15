# PulseLab — Active Task Tracker

**Restored & Expanded Session:** August 15, 2026  
**Project:** PulseLab Generative EDA Platform (`Pulse-main`)  
**Current Phase:** Phase 2 — Backend Services, Thermal/Copper Engine, FreeRouting & Stencil Graphics

---

## 1. Latest Session State & Reference PCB Audit (`v0.9.82` / `v0.9.83` / `v0.9.2`)

- **Flipper Killer MK II Refinement**:
  - Achieved **0 unconnected ground pads / 0 DRC connection errors** (`v0.9.82` / `v0.9.83` / `v0.9.2` variants).
  - Fixed USB-C HRO `TYPE-C-31-M-12` pad regex matching (`RawFootprint.to_sexpr` fix for coincident pads `A1`/`B12`).
  - EPAD 3x3 GND thermal via matrix implemented for ESP32-S3 IC / MCU heat dissipation.
- **Reference PCB Audit (`C:\Users\soyko\Documents\Mis-PCBs\...`)**:
  - **Thermal Pads & Spokes**: EPAD thermal via matrices, `thermal_bridge_width` and `thermal_gap` zone settings.
  - **Copper Pour & 0V Reference Plane**: Double-sided `F.Cu`/`B.Cu` `PWR_GND` pour with via stitching grid and ground isolation splits (`PWR_GND` vs `PWR_GND_FLIPPER`).
  - **FreeRouting Integration**: DSN export / SES import workflow setup for automated signal routing.
  - **Stencil Logos & Artwork**: Silkscreen & copper layer stencil branding (`Logos:fabitive_logo`, `Logos:logo2`, `Logos:logo5`, `Custom:Flipper_Zero_GPIO`).
- **Phase 1 Execution Complete**:
  - `core/auto_placement.py` (2D Auto-Placement Engine using Hooke attraction + Coulomb repulsion + hardware heuristics).
  - `core/schema_validator.py` (Pydantic v2 structured output validation).

---

## 2. Active Roadmap & Pending Tasks

### A. Core EDA & Hardware Features (New Pending Tasks)
- [ ] **Task 1: Thermal Pads & Thermal Relief Manager (`core/thermal_engine.py`)**
  - Automated EPAD $N \times M$ thermal via grid generator for SMD IC pads.
  - Per-zone and per-pad thermal spoke width (`thermal_bridge_width`) and gap (`thermal_gap`) controls.
- [ ] **Task 2: Copper Pour & 0V Reference Plane Generator (`core/copper_zone_manager.py`)**
  - Automatic double-sided `PWR_GND` 0V reference layer fill generation.
  - Automated GND Via Stitching Grid algorithm with boundary detection and clearance handling.
  - Split-plane ground isolation manager (`PWR_GND` vs `PWR_GND_FLIPPER`).
- [ ] **Task 3: FreeRouting Integration Bridge (`bridge/freerouting_bridge.py`)**
  - Direct `.dsn` export via `kicad-cli pcb export dsn`.
  - Headless FreeRouting CLI execution wrapper (`java -jar freerouting.jar -de input.dsn -out output.ses`).
  - Direct `.ses` back-annotation via `kicad-cli pcb import ses`.
- [ ] **Task 4: Stencil Logos & Graphics Engine (`bridge/graphics_engine.py`)**
  - Vector SVG/DXF to S-expression polygon parser (`gr_poly`/`fp_poly`).
  - Logo placement support on `F.Cu`, `B.Cu`, `F.SilkS`, and `B.SilkS`.

### B. Backend Platform & LLM Infrastructure
- [ ] **Task 5: FastAPI Backend Gateway (`app/main.py` / `studio/`)**
  - Implement `/api/v1/generate-pcb` endpoint to trigger placement, thermal/zone processing, and routing pipeline.
- [ ] **Task 6: JLCPCB / LCSC Stock Lookup & Connector**
  - Real-time stock lookup & auto-replacement connector for missing/out-of-stock components.
- [ ] **Task 7: LLM Prompt & Context Stabilization**
  - Multi-turn prompt optimization for complex circuit synthesis maintaining < 3 retries.

---

## 3. Immediate Next Steps

1. Implement Thermal Via & Spoke generator module in `core/thermal_engine.py` & `bridge/pcb_builder.py`.
2. Build 0V Ground Plane & Via Stitching Grid module in `core/copper_zone_manager.py`.
3. Create FreeRouting CLI auto-routing bridge in `bridge/freerouting_bridge.py`.
4. Create Stencil Logo Ingestion module in `bridge/graphics_engine.py`.
5. Integrate with FastAPI backend service in `app/main.py`.
