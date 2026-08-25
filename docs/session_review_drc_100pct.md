# Session Review — DRC 0 Errors + 100% Visual Score Achievement

**Date:** 2026-08-23  
**Session checkpoint:** 13

---

## Achieved

| Preset | DRC Errors | Visual Score | Routing |
|--------|-----------|-------------|---------|
| `esp32_tft_console` | **0** | **100%** | 25/25 segs, 32 nets |
| `flipper_addon` | **0** | **100%** | 17/17 segs, 44 nets |
| `sensor_node` | **0** | **100%** | 17/17 segs, 32 nets |
| `power_supply` | **0** | **100%** | 11/11 segs, 10 nets |
| `ne555_flasher` | **0** | **100%** | 13/13 segs, 6 nets |

---

## Root Cause of Remaining Violations

pcb_builder.py collision resolver used pad bounding box + 0.35mm fixed margin.
VisualInferenceEngine uses max(spec_width, pad_span) + courtyard_margin — much larger for SOIC-16 with 16 pads spanning 7.8x9.49mm.

The two systems used different geometry — the resolver declared no collision where the inspector found one.

---

## Fixes Applied

1. bridge/pcb_builder.py — _get_courtyard_aabb() helper + unified geometry
2. bridge/pcb_builder.py — Board edge keepout (2.5mm) in spiral search
3. core/auto_placement.py — Button edge clearance formula correction
4. core/auto_placement.py — Passive seeding: Top/Bottom channels always
5. core/auto_placement.py — AABB IC keepout in _relax_netlist_forces

## Key Lesson

The collision resolver and the visual inspector MUST use the same geometry computation. 
If they diverge — even by using pad-extent-only vs max(spec, pad_span) — the resolver will 
place components in positions the inspector later rejects.
