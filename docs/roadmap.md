# PulseLab Forge Roadmap

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
- [ ] **PulseLogger**: Unified debug sink for simulation and layout events.

---

## Future Goals

### Phase 3: Premium UI/UX (Aesthetics)
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
