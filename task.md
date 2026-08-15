# PulseLab — Active Task Tracker

**Restored & Expanded Session:** August 15, 2026  
**Project:** PulseLab Generative EDA Platform (`Pulse-main`)  
**Current Phase:** Phase 2 — Hardware Engines, SCH↔PCB Cross-Check & Backend Integration

---

## 1. Prototype Accomplishments (`v1.0.1` $\rightarrow$ `v1.0.4`) & SCH↔PCB Parity

- **Flipper Killer MK II v1.0 Prototype Series**:
  - Added MicroSD Card slot (`J_SD` + `C_SD`) wired to ESP32-S3 SPI (GPIO 10, 11, 12, 13).
  - Added Backside OLED Report Display Header (`J_DISP`) wired to ESP32-S3 I2C (GPIO 4, 5) placed on `B.Cu` / `B.SilkS`.
  - Achieved **0 unconnected items / 0 DRC connection errors** across all 4 release iterations (`v1.0.1`, `v1.0.2`, `v1.0.3`, `v1.0.4`).
- **100% SCH $\leftrightarrow$ PCB Designator Parity**:
  - Implemented mechanical and stencil graphic symbol generation (`H1..H4`, `LOGO1..LOGO2`) in `SchematicGenerator`.
  - Verified **25 out of 25 reference designators match 100%** between `.kicad_sch` and `.kicad_pcb` via `sch_pcb_crosscheck.py`.
- **Completed Core Hardware Engines**:
  - `core/thermal_engine.py`: $3 \times 3$ EPAD thermal via grid.
  - `core/copper_zone_manager.py`: Double-sided `PWR_GND` 0V copper pour & via stitching grid.
  - `bridge/freerouting_bridge.py`: Specctra DSN export, FreeRouting engine, SES back-annotation.
  - `bridge/graphics_engine.py`: Stencil logo footprints & `gr_poly` vector graphics.

---

## 2. Active Roadmap & Pending Tasks

### A. SCH $\leftrightarrow$ PCB Coherence & DRC Integration
- [x] **Task 1: SCH $\leftrightarrow$ PCB Reference Designator Parity (100% Match)**
  - Auto-generate mechanical mounting holes (`H1..H4`) and logo symbols (`LOGO1..LOGO2`) in `.kicad_sch` with `(in_bom no) (on_board yes)`.
- [ ] **Task 2: SCH $\leftrightarrow$ PCB Cross-Check Gate Integration**
  - Embed `sch_pcb_crosscheck.py` directly into `KiCadBridge.run_drc()` so every prototype run automatically verifies schematic-PCB net & component parity alongside physical DRC checks.
- [ ] **Task 3: Passive Component Explicit Net Labeling**
  - Eliminate single-occurrence fallback net names (`N1`, `N2`) in `SchematicGenerator`.

### B. Backend Services & LLM Infrastructure
- [ ] **Task 4: FastAPI Backend Gateway (`app/main.py` / `studio/`)**
  - Implement `/api/v1/generate-pcb` endpoint to trigger placement, thermal/zone processing, schematic synthesis, and routing.
- [ ] **Task 5: JLCPCB / LCSC Stock Lookup & Connector**
  - Real-time stock lookup & auto-replacement connector for missing/out-of-stock components.
- [ ] **Task 6: LLM Prompt & Context Stabilization**
  - Multi-turn prompt optimization for complex circuit synthesis maintaining < 3 retries.

---

## 3. Immediate Next Steps

1. Embed `sch_pcb_crosscheck.py` validation into `KiCadBridge.run_drc()`.
2. Clean up single-occurrence net label stubs in `SchematicGenerator`.
3. Connect FastAPI service endpoints in `app/main.py`.
