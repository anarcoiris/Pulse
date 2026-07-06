### Session 4a — KiCad Symbol Knowledge Base (parser + index + RAG pinout unification) ✅ COMPLETED (06-jul-2026)

Outcome: `docs/calibration_forge/kicad_symbol_kb.md` §Resultado. Do not re-run unless drift check finds regressions. Config blocker `rag_top_k: 0.95` → resolved before 4b parte 1 — see `session_4b_preflight_verification.md` §7.

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

## PRIOR SESSION CONTEXT (Sessions 1-3 — all completed 06-jul-2026)

Session 1 (KB fidelity), Session 2 (PulseLogger + design_experience loop), and Session 3
(pin model coverage) are all DONE. Read their outcomes before touching shared files:
- docs/calibration_forge/knowledge_base_fidelity.md — §Resultado
- docs/calibration_forge/dormant_features_audit.md — §Resultado
- docs/calibration_forge/pin_model_coverage.md — §Resultado

What landed in Session 3 that THIS session builds directly on top of (do NOT redo, DO preserve):
- knowledge/circuit_synthesizer.py::_match_pinouts() returns list[tuple[str, dict]] ordered
  by score (primary match first).
- _compact_pinout(entry, full=True) injects the COMPLETE pin table for the primary match only;
  secondary matches stay capped by max_pinout_pins (14). This is the fix that solved the
  10.3% -> 100% pin coverage jump (see below) — do not reintroduce the old all-or-nothing cap.
- "NC" / "unconnected_pins" convention in the output schema (ATOMIC_JSON_SUFFIX in
  knowledge/llm_prompt_format.py + base_system_prompt rules), normalized by
  circuit_synthesizer._normalize_unconnected_pins() into unique NC_<label>_<pin> net names
  before reaching schematic_generator.py.
- knowledge/validate_complex_apps.py::_pin_coverage() metric, persisted per-case and in
  run_manifest.json under the "pin_coverage" key.

**Post-fix validation run (06-jul-2026 13:09-13:16 UTC, session `validate_20260706_130942_b1a9364b`,
backend `primary` only — `atomic` was unavailable):** re-ran `--case esp32_sensors` and
confirmed the fix works end-to-end with a real LLM call, not just the static sanity check:
pin coverage went **10.3% -> 100%** (U1 ESP32-WROOM-32: 39/39, OLED SSD1306: 4/4, SENSOR
BME280: 4/4; unused ESP32 pins correctly appeared as NC_U1_<n>). Full detail in
knowledge/data/validation_complex/runs/20260706_130942_validate_20260706_130942_b1a9364b/esp32_sensors.json.
This was a single case/backend — it does not replace the full 5-case baseline Session 4b
needs for its A/B experiment, it's confirmation the underlying mechanism you're about to
refactor already works and must not regress.

Also relevant: presets/esp32_usb_devkit.py and presets/esp32s2_usb_devkit.py hand-written
pin dicts only cover ~20% of their MCU's physical pins (pin_model_coverage.md §Alcance) —
this is a data-completeness problem this session's KiCad index should help close, not
something to "fix" by hand-editing the presets.

---

SOURCE OF TRUTH (read this first, in full):
- docs/calibration_forge/kicad_symbol_kb.md
- docs/calibration_forge/pin_model_coverage.md (§Resultado, for the injection semantics you must preserve)
- docs/reviews/pulselab_review_05072026.md (section 4.5, if present — otherwise treat kicad_symbol_kb.md as primary)

IMPORTANT — drift check: kicad_symbol_kb.md was written 06-jul-2026 and states
knowledge/kicad_symbol_parser.py and knowledge/build_symbol_index.py do NOT exist yet, and
that bridge/kicad_bridge.py::find_kicad_symbol_dir() already locates the KiCad symbol
directory (path only, doesn't parse). Verify this is still true with a repo-wide search
before assuming you're building from scratch — someone may have started this since. Also
confirm knowledge/pinouts_library.json and knowledge/data/components.json still have the
~12 and ~10 entries respectively described in the doc's problem statement.

GOAL: Replace the ~12-entry hand-curated knowledge/pinouts_library.json as the primary
pinout data source with an index built from KiCad's own .kicad_sym symbol libraries
(thousands of parts, already containing pin names/numbers/types/footprints), and unify
pinout retrieval into the existing RAG engine instead of the separate ad-hoc keyword
scorer in circuit_synthesizer.py.

TASKS:
1. Implement knowledge/kicad_symbol_parser.py: an S-expression parser for .kicad_sym files
   (same style as the existing knowledge/kicad_schematic_parser.py — regex/tokenizer, no
   heavy deps). Output per symbol: lib_id, value, library, symbol, footprint_default, pins
   (pad number -> electrical name), pin_types (pad number -> electrical type), aliases.
   Merge multi-unit symbols (e.g. "LM358_1_1", "LM358_2_1") by pin number. Commit 2-3 small
   .kicad_sym fixture files (not the whole KiCad install) and add unit tests against them.
2. Implement `python -m knowledge.build_symbol_index`: walks
   bridge/kicad_bridge.py::find_kicad_symbol_dir() (or an explicit KICAD_SYMBOL_DIR env var
   override), filters to priority libraries first (RF_Module, MCU_*, Interface_USB,
   Regulator_*, Driver_Motor, Sensor_*, Connector_*), and writes
   knowledge/data/symbols_index.json (or SQLite if the JSON exceeds ~50MB), logging symbols
   parsed / errors / libraries skipped. If KiCad isn't installed in this environment, document
   that clearly and generate the index from whatever symbol libraries ARE available (e.g. any
   vendored under the repo), noting the limitation in your handoff rather than blocking.
3. Ingest chunk_type="pinout" entries into ElectronicsKnowledgeBase (knowledge/rag_engine.py)
   from the generated index, reusing the existing generic ingest_json()-style path where
   possible.
4. Migrate circuit_synthesizer._match_pinouts() / _load_pinouts() to query
   kb.query(description, top_k=..., chunk_type="pinout") instead of scoring
   pinouts_library.json by keyword. You MUST preserve, exactly:
   - The ordered list[tuple[str, dict]] return shape (best match first).
   - The full/compact injection logic: only the top/primary match gets the complete pin
     table (_compact_pinout(entry, full=True)); secondary matches stay capped by
     max_pinout_pins.
   - _normalize_unconnected_pins() running unchanged after the LLM response is parsed.
   Keep knowledge/pinouts_library.json in place as a small manual-override layer per
   kicad_symbol_kb.md's layered model (don't delete it) — it should only be consulted for
   parts missing from or contradicting the KiCad-derived index.
5. Update knowledge/validate_complex_apps.py::_pin_coverage() to also resolve components
   against the new symbols_index (by value or lib_id), in addition to pinouts_library.json,
   so previously-unmatched parts (e.g. "ESP8266_Node" in presets/mcu_uart.py) get a real
   pinout reference where KiCad has one, instead of reporting "n/a".
6. Regression check: re-run `python -m knowledge.validate_complex_apps --case esp32_sensors`
   (and esp32_usb_devkit if time allows) and confirm pin coverage does NOT regress below the
   100% / esp32_sensors baseline measured in the 06-jul-2026 13:09 run referenced above — this
   refactor must not reintroduce Session 3's truncation bug.
7. Run pytest tests/test_forge.py tests/test_rag_retrieval.py plus your new parser/index unit
   tests; all must pass before handoff.

HANDOFF (required before ending this session):
- Update docs/calibration_forge/kicad_symbol_kb.md: check off completed milestones in its
  "Próximos pasos" list, note actual symbol/library counts indexed, and flag any parts from
  the 5 validate_complex_apps test cases still unmatched.
- Update docs/calibration_forge/index.md and docs/roadmap.md to reflect the new pinout data
  source.
- Update docs/calibration_forge/pin_model_coverage.md if the regression check in task 6
  produced new numbers worth recording.
- Explicitly hand off to Session 4b: confirm (or correct) that
  circuit_synthesizer._get_pinouts_context() / _match_pinouts() now source from RAG, note any
  cfg changes (e.g. new rag_top_k for chunk_type="pinout"), and flag anything that changes
  Session 4b's starting assumptions in prompt_vs_rag_balance.md.
```

---
