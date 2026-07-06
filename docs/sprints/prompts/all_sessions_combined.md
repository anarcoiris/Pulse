Here are self-contained prompts, one per session, meant to be pasted into a fresh Agent-mode conversation each time, in order. **Execution order for Sessions 4+:** 4a (done) → **4c** → **4d** → 4b → 5. **Current position (07-jul-2026):** 4c P0 done + verified live; 4c P1–P3 and 4d **code landed** (`llm_output_pipeline.md` §Resultado); 4b parte 1 (A/B confundido) recorded; **4b clean re-run** is next after live verify of atomic review routing.

A few notes on how I built these before the prompts themselves:

- **Source of truth = the docs in `docs/calibration_forge/*.md` and `docs/reviews/pulselab_review_05072026.md`**, not this conversation. They're dated snapshots (05-jul-2026) of what the code looked like when I read it — they are not guaranteed to still be 100% accurate by the time you run Session 3, 4a, 4b, or 5, especially if an earlier session already touched shared files (`rag_engine.py`, `Pulse_cfg.json`, etc.).
- **Drift handling is baked into every prompt** as an explicit step: "verify against current code before acting, and if reality has diverged from the doc, update the doc to match reality — don't silently follow stale instructions and don't silently deviate without leaving a trace."
- **Handoff is mandatory**, not optional: each prompt ends by requiring the agent to update its own reference doc (mark done items, log deviations, add new findings) plus touch `docs/roadmap.md` / `docs/calibration_forge/index.md` / `FORGE_STATUS.md` if it changed something those track. This is exactly the sync discipline used when I created these docs — it should keep propagating forward.
- Session 4a/4b have an extra guard clause because they structurally depend on Session 1's outcome (and on each other) — if you run them out of order, the agent will check and adapt instead of assuming prior sessions happened.
- **Session 1 completed 06-jul-2026** — see `docs/calibration_forge/knowledge_base_fidelity.md` §Resultado. Session 2 prompt below includes a prior-session context block; paste it as-is (do not strip it).
- **Session 2 completed 06-jul-2026** — see `docs/calibration_forge/dormant_features_audit.md` §Resultado. Session 3 prompt below now includes a prior-session context block (shared-file overlap warning on `circuit_synthesizer.py`); Session 4's dependency check was also updated to reflect that Session 2's design-experience loop is done and has a working POC. Paste both as-is.
- **Session 3 completed 06-jul-2026** — see `docs/calibration_forge/pin_model_coverage.md` §Resultado. **Post-fix validation run 06-jul-2026 13:09-13:16 UTC** (`validate_20260706_130942_b1a9364b`, backend `primary` only — `atomic` unavailable) confirmed the fix works end-to-end with a real LLM call: `esp32_sensors` pin coverage went **10.3% → 100%** (39/39 ESP32-WROOM-32, 4/4 SSD1306, 4/4 BME280), with unused pins correctly normalized as `NC_U1_<n>`. This closes the "pending post-fix measurement" gap noted in Session 3's handoff — see `pin_model_coverage.md` §Resultado and `prompt_vs_rag_balance.md`'s updated dependency note for the full numbers. Only this one case/backend was re-run; the other 4 cases are covered by Session 4b's own A/B baseline.
- **Session 4 was split into 4a and 4b** after Session 3 closed, because the original Session 4 prompt grew to include building a brand-new KiCad symbol-parsing subsystem (`docs/calibration_forge/kicad_symbol_kb.md`, added 06-jul-2026) on top of the original prompt-vs-RAG A/B experiment — two different-sized efforts that don't belong in one session. **Session 4a** builds the KiCad `.kicad_sym` parser + symbol index + unifies pinout retrieval into RAG (`chunk_type="pinout"`), preserving Session 3's full/compact injection semantics. **Session 4b** (depends on 4a) runs the original A/B experiment (hardcoded rules vs. richer RAG) using 4a's unified pinout retrieval. Paste 4a first, let it finish and hand off, then paste 4b.
- **Session 4a completed 06-jul-2026** — see `docs/calibration_forge/kicad_symbol_kb.md` §Resultado. KiCad 10.0 turned out to already be installed locally under `AppData\Local\Programs` (a path `find_kicad_symbol_dir()` didn't check) — fixed, then indexed **5320 real symbols across 29 priority libraries** into `knowledge/data/symbols_index.json`, ingested into the RAG as 5326 `chunk_type="pinout"` chunks (5320 KiCad + 10 curated overrides from `pinouts_library.json`, which still wins on name collision). `_match_pinouts()`/`_pin_coverage()` migrated as specified. A real regression was found and fixed mid-session: pure semantic ranking let a literally-named part (`BME280`) lose to a semantically-similar-but-wrong one (`TMP1075D`) — fixed with an exact-normalized-name boost layered on top of the RAG score inside `_match_pinouts()` only. Re-ran `--case esp32_sensors` post-fix: **100% pin coverage confirmed, no regression** vs. Session 3's baseline (`pytest tests/`: 79/79 passed). `pinouts_library.json` was **not** deprecated — it remains the sole source for breakout modules with no official KiCad symbol (SSD1306, PN532, CC1101, BME280) and for the 4 MCU/bridge parts already validated in Session 3.
- **LLM truncation review 06-jul-2026** — see [`docs/calibration_forge/llm_truncation_review_06072026.md`](docs/calibration_forge/llm_truncation_review_06072026.md). Session 4b validation runs exposed four output failure modes the pipeline did not handle. Fix via **Session 4c** (guardrails + multi-turn) and **Session 4d** (dual-backend orchestration) — master plan: [`docs/calibration_forge/llm_output_pipeline.md`](docs/calibration_forge/llm_output_pipeline.md).
- **Session 4b parte 1 (A/B confundido) 06-jul-2026 noche** — experimento ejecutado (runs `182955`/variant A, `201754`/variant B); datos en [`prompt_vs_rag_balance.md`](docs/calibration_forge/prompt_vs_rag_balance.md) §Resultado A/B. Semantic review inutilizable (9/10 truncados). Infra: `rag_top_k` fix, toggle `--variant`, embeddings rebuild (**5685** chunks). Trim decision **deferred**.
- **Session 4c P0 06-jul-2026 noche** — `done_reason` normalizado, `parse_llm_result()`, reviewer (`disable_thinking` + `json_mode` + 8192 tokens), validación post-parse pinouts, `session_id` en reviewer. **Verificado en vivo** en `--case esp32_rf_nfc` y `--case esp32_usb_devkit` (runs `212059`, `213418`) — reviewer devuelve JSON (61s / 115s) vs FAIL previo. P1–P3 code landed (continuation turn, truncation tests, observabilidad) — ver [`llm_output_pipeline.md`](docs/calibration_forge/llm_output_pipeline.md) §Resultado. `pytest`: **101 passed**.
- **Session 4d code landed 06-jul-2026** — `SemanticReviewer` → `get_backend_client(resolve_backend_name(task="review"))`, `Pulse_cfg.json` → `review_backend: "atomic"`, harness `--review-backend`, campos `synthesis_backend`/`review_backend`/`truncation_events` en manifiestos. **Pendiente:** corrida live que ejercite review en `atomic` (la verificación 4c usó `primary` por config previa al cambio).

---

### Session 1 — Knowledge-base fidelity fixes ✅ COMPLETED (06-jul-2026)

Outcome: `docs/calibration_forge/knowledge_base_fidelity.md` §Resultado. Do not re-run unless drift check finds regressions.

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

SOURCE OF TRUTH (read these first, in full, before touching any code):
- docs/calibration_forge/knowledge_base_fidelity.md
- docs/reviews/pulselab_review_05072026.md (section 4.2 and the table in section 6)
- docs/calibration_forge/index.md (for how this fits the broader research index)

IMPORTANT — drift check: these docs were written 2026-07-05 as a snapshot of the code at
that time. Before implementing anything, re-read the actual current state of
knowledge/rag_engine.py and knowledge/kicad_schematic_parser.py and confirm the described
bugs still exist as written (line numbers may have shifted, someone may have partially
fixed it already, etc.). Treat the doc as a well-evidenced hypothesis, not gospel. If you
find the current code differs from what the doc describes, note the discrepancy and adapt
your plan — do not force a fix for a bug that's no longer there, and do not skip a bug just
because the line numbers moved.

GOAL: Improve the fidelity of what gets indexed into the RAG knowledge base, so retrieved
circuit examples actually carry design intent and schematic context instead of bare
component lists.

TASKS:
1. Fix knowledge/rag_engine.py::_summarize_circuit_data() so it reads the natural-language
   description from data["metadata"]["prompt"] (not just top-level "source"/"original_file"),
   for the self-generated training samples in knowledge/data/training/sample_*.json.
2. Extend knowledge/kicad_schematic_parser.py::KiCadSchematicParser to also capture:
   - title_block (title + comments)
   - free-floating (text "...") annotations
   - label / hierarchical_label / global_label net names
   Decide on a sensible output schema addition (e.g. a "description"/"notes" field) and
   thread it through to _summarize_circuit_data() so it actually gets indexed.
3. Determine whether the ~280 human_*.json training files under knowledge/data/training/
   can be regenerated from their original .kicad_sch sources (check knowledge/github_crawler.py
   and whether raw files are still on disk, e.g. knowledge/data/raw_kicad/) so the parser
   improvements actually apply retroactively. If raw files aren't available, document that
   as a known limitation rather than silently skipping it.
4. Rebuild the embedding index: python -m knowledge.build_embed_index
5. Run tests/test_rag_retrieval.py and knowledge/rag_engine.py's own __main__ self-test;
   confirm indexed excerpts for the RLC/RF example (or similar) now contain intent language,
   not just "etype label value".
6. Add a lightweight "description density" check to ElectronicsKnowledgeBase.stats()
   (knowledge/rag_engine.py) per the proposal in knowledge_base_fidelity.md, so this doesn't
   regress silently in the future.

HANDOFF (required before ending this session):
- Update docs/calibration_forge/knowledge_base_fidelity.md: check off / annotate which
  proposed steps you completed, and add a short "Resultado" section with what you found
  that differed from the original hypothesis (e.g. raw files missing, chunk counts before/after,
  actual retrieval quality change observed).
- Update the priority table in docs/reviews/pulselab_review_05072026.md (section 6) to mark
  these two 🔴 items as done, with a one-line pointer to the result section above.
- Update docs/calibration_forge/index.md milestone checklist accordingly.
- Explicitly flag anything that changes the starting assumptions for
  docs/calibration_forge/prompt_vs_rag_balance.md (Session 4 depends on this work) — e.g. if
  the KB improvement was smaller/larger than expected, say so there or in that doc directly.
```

---

### Session 2 — Wire up `PulseLogger` + debug the `design_experience` loop ✅ COMPLETED (06-jul-2026)

Outcome: `docs/calibration_forge/dormant_features_audit.md` §Resultado. Do not re-run unless drift check finds regressions.

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

## PRIOR SESSION CONTEXT (Session 1 — completed 06-jul-2026)

Session 1 (Knowledge-base fidelity) is DONE. Read its outcome before touching shared files:
- docs/calibration_forge/knowledge_base_fidelity.md — §Resultado (sesión de fix, 05–06-jul-2026)
- docs/calibration_forge/prompt_vs_rag_balance.md — dependency note at top (Session 4 prereq)

What landed in Session 1 (do NOT redo):
- knowledge/rag_engine.py::_summarize_circuit_data() now indexes metadata.prompt as
  design_intent:, plus parser fields description/notes/net_labels.
- knowledge/kicad_schematic_parser.py extended (schema v1.1); self-test in __main__.
- ElectronicsKnowledgeBase.stats() has circuit_example_description_density.
- tests/test_rag_retrieval.py has test_rag_design_intent_retrieval (5 tests total).
- 320 human_*.json regenerated from knowledge/data/raw_kicad/; backup at
  knowledge/data/training_backup_20260705/.
- Verified: density 80.06% (261/326), test_rag_usb_retrieval now PASS (was FAIL).

What Session 1 did NOT finish (not your job unless you need RAG for validation):
- Dense embed rebuild failed — Ollama not running (WinError 10061). vectors.npy is
  STALE (pre-fix); TF-IDF is fresh. Run python -m knowledge.build_embed_index when
  Ollama + nomic-embed-text are up, before Session 4 A/B.

Environment gotchas (Windows, observed in Session 1):
- Agent shell may need elevated permissions (required_permissions: ["all"]) to spawn processes.
- Long Python runs / dataset_builder: set $env:PYTHONIOENCODING='utf-8' (emoji prints crash
  on cp1252 otherwise).

Files Session 2 will likely touch that Session 1 also used (but did not modify):
- knowledge/circuit_synthesizer.py — instrument with PulseLogger; still uses RAG via
  ElectronicsKnowledgeBase.
- bridge/gerber_export.py — record_design_outcome() already referenced here.

Index sync already done for Session 1; Session 2 owns this open milestone:
- docs/calibration_forge/index.md item 38: confirm/fix knowledge/experiences/ accumulation.

---

SOURCE OF TRUTH (read these first, in full):
- docs/calibration_forge/dormant_features_audit.md
- docs/calibration_forge/logging_strategy.md (original design spec for PulseLogger)
- docs/reviews/pulselab_review_05072026.md (section 4.4)

IMPORTANT — drift check: verify core/logger.py, bridge/gerber_export.py, and
ui/forge_controller.py still match what dormant_features_audit.md describes (it claims
PulseLogger is fully implemented but unused, and design_experience.py is wired but
knowledge/experiences/ is empty). If someone already started wiring these in since
2026-07-05, adjust scope accordingly and don't duplicate work — verify with a repo-wide
search for "PulseLogger" and "record_design_outcome" usage before assuming the doc's
snapshot is still accurate.

GOAL: Make the two dormant subsystems actually produce data, so future sessions (especially
the prompt/RAG rebalancing work) have real logs and real design-experience records to use.

TASKS:
1. Instrument core/logger.py (PulseLogger singleton) into the modules the original
   logging_strategy.md calls out: bridge/pcb_layout.py (especially the autoroute() A*
   attempts), bridge/gerber_export.py, knowledge/circuit_synthesizer.py, and
   knowledge/semantic_reviewer.py. Use the existing debug/info/warning/error/ai_review
   methods; don't redesign the logger itself unless you find a real defect in it.
2. Trace why knowledge/experiences/ has zero files despite record_design_outcome() being
   called from bridge/gerber_export.py / ui/forge_controller.py. Check for: silent
   exception swallowing, a code path that's never actually reached in the tested flows,
   wrong working directory / path resolution, or a flag that gates it off by default.
3. Exercise the full flow end-to-end (generate a circuit -> export PCB -> Gerbers) and
   confirm a DesignExperience JSON file actually appears in knowledge/experiences/, and
   that ingest_to_rag() results in a new chunk_type="design_experience" entry visible in
   ElectronicsKnowledgeBase.stats(). Use knowledge/calibration_run.py or
   knowledge/validate_complex_apps.py as the harness if convenient, and consider adding
   this check permanently to one of them so it doesn't silently break again.
4. Optional if time permits: wire logger.get_context() into
   circuit_synthesizer.py::_build_system_prompt()'s retry path, per the original "AI Context
   Buffer" idea in logging_strategy.md.

HANDOFF (required before ending this session):
- Update docs/calibration_forge/dormant_features_audit.md with what you found (root cause
  of the empty experiences/ dir, what you instrumented, any remaining gaps).
- Update docs/roadmap.md's PulseLogger line (currently marked "sink implemented but not
  wired") to reflect the real integration status.
- Update FORGE_STATUS.md item 3 (design-experience loop) to reflect whether it now
  produces data.
- Update docs/calibration_forge/index.md milestone checklist (item 38: experiences/).
- If you migrated any hardcoded rule into a DesignExperience lesson as a proof of concept,
  note that explicitly — it's directly relevant groundwork for Session 4
  (prompt_vs_rag_balance.md proposal #3).
```

---

### Session 3 — Pin model coverage ✅ COMPLETED (06-jul-2026)

Outcome: `docs/calibration_forge/pin_model_coverage.md` §Resultado. Re-correr `validate_complex_apps` con backends activos para medir cobertura post-fix (baseline LLM: 4/39 = 10.3% en `esp32_sensors`, 2026-07-05).

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

## PRIOR SESSION CONTEXT (Session 2 — completed 06-jul-2026)

Session 2 (PulseLogger + design_experience loop) is DONE. Read its outcome before
touching shared files:
- docs/calibration_forge/dormant_features_audit.md — §Resultado (sesión de wiring, 06-jul-2026)

What landed in Session 2 (do NOT redo):
- PulseLogger wired into bridge/pcb_layout.py (autoroute A* debug/warning/info),
  bridge/gerber_export.py (DRC/gerbers/drill/position/svg steps + fixed silent
  except around record_design_outcome), knowledge/circuit_synthesizer.py
  (ai_review around LLM calls/retries), knowledge/semantic_reviewer.py
  (ai_review with issue counts), ui/forge_controller.py (fixed silent except).
- Root cause of empty knowledge/experiences/ found and fixed: the
  record_design_outcome() hook was never reached by any automated/tested flow
  (it's a separate action from "Generate PCB"), AND DesignExperience.ingest_to_rag()
  never persisted chunks across process restarts. Fixed via new
  ElectronicsKnowledgeBase._load_experiences() in knowledge/rag_engine.py.
- New permanent regression test: tests/test_forge.py::test_design_experience_loop
  (9/9 tests passing; tests/test_rag_retrieval.py still 5/5).
- AI Context Buffer wired: logger.get_context() now injected into
  circuit_synthesizer.py::generate_circuit_json()'s JSON-decode retry path
  (last 20 log lines appended to the retry prompt).
- POC: knowledge/seed_poc_experience.py migrated the "ESP32 EN pull-up 10k" rule
  into a DesignExperience lesson (knowledge/experiences/poc_esp32_en_pullup_rule.json),
  confirmed retrievable via RAG. The rule was NOT removed from the prompts — that's
  Session 4's call to make per prompt_vs_rag_balance.md, not scoped to Session 2.

Files Session 3 will likely touch that Session 2 also modified:
- knowledge/circuit_synthesizer.py — now imports `from core.logger import logger`
  and has logger.ai_review()/logger.error() calls threaded through
  generate_circuit_json() (including inside the JSONDecodeError retry branch,
  which now also injects logger.get_context() into the retry prompt). You'll be
  near this if you touch _build_system_prompt() or base_system_prompt — preserve
  these calls when editing _compact_pinout() / base_system_prompt, don't strip
  them as unrelated noise.

Index sync already done for Session 2:
- docs/calibration_forge/index.md milestone item 38 (experiences/) — checked off.

---

SOURCE OF TRUTH (read this first, in full):
- docs/calibration_forge/pin_model_coverage.md
- docs/reviews/pulselab_review_05072026.md (section 4.1)

IMPORTANT — drift check: re-verify knowledge/circuit_synthesizer.py::_compact_pinout() and
the static example in base_system_prompt still behave as described (14-pin cap, 4-pin
example) before changing them — confirm current Pulse_cfg.json values for
llm.agents.circuit_synthesizer.max_pinout_pins. If another session already changed this
area, adjust rather than reverting or duplicating.

GOAL: Make generated circuits represent MCU pins faithfully — either by connecting them,
or by explicitly marking them as intentionally unconnected — instead of silently dropping
them past a size cap.

TASKS:
1. Redesign knowledge/circuit_synthesizer.py::_compact_pinout() so it no longer omits the
   entire pin table once it exceeds max_pinout_pins. Prefer: always include the full pin
   table for the MCU(s) that score highest in _match_pinouts(), reserving compaction for
   secondary/low-confidence matches only.
2. Add an explicit "NC" / "unconnected_pins" convention to the output schema: update the
   OUTPUT RULES in knowledge/llm_prompt_format.py (ATOMIC_JSON_SUFFIX) and the base rules
   in circuit_synthesizer.py's base_system_prompt so the model can declare pins it
   deliberately leaves floating, instead of just omitting them silently.
3. Replace or supplement the single static worked example in base_system_prompt (currently
   only 4/39 ESP32 pins) with a dynamic example built from a "golden" preset with fuller
   pin coverage, e.g. presets/esp32_usb_devkit.py, so the model's strongest prior isn't the
   least complete example in the system.
4. Add a "Pin Coverage Fidelity" metric (generated pins / total pins in
   knowledge/pinouts_library.json for that part) to knowledge/validate_complex_apps.py's
   per-case summary output, and document its formal definition in
   docs/calibration_forge/evaluation_metrics.md.
5. Check presets/esp32s2_usb_devkit.py and presets/mcu_uart.py for the same truncation
   pattern (pin_model_coverage.md flags this as an open question) — if hand-written presets
   have the same issue, note it; it means this isn't purely a prompt problem.
6. Re-run knowledge/validate_complex_apps.py --case esp32_sensors (and ideally the other 4
   cases) and confirm the new pin coverage metric improves versus today's baseline
   (4/39 pins observed in the 2026-07-05 19:20 UTC run).

HANDOFF (required before ending this session):
- Update docs/calibration_forge/pin_model_coverage.md: mark completed proposals, record the
  before/after pin coverage numbers you measured, and note what you found when checking the
  hand-written presets.
- Update docs/calibration_forge/evaluation_metrics.md with the finalized metric definition.
- Update the priority table in docs/reviews/pulselab_review_05072026.md (section 6).
- If you changed how pinouts are selected/injected, flag it clearly for Session 4, since
  that session considers merging this same pinout-matching logic into the main RAG engine.
```

---

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

### Session 4c — LLM output guardrails & multi-turn recovery — **P0 DONE** (P1–P3 code landed; see §Resultado)

**Prerequisite for Session 4b (P0 satisfied).** Full scope + verification: [`docs/calibration_forge/llm_output_pipeline.md`](docs/calibration_forge/llm_output_pipeline.md) §Resultado. Evidence: [`llm_truncation_review_06072026.md`](docs/calibration_forge/llm_truncation_review_06072026.md).

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

## PRIOR SESSION CONTEXT

Sessions 1–3 and 4a are DONE (see docs/calibration_forge/*/§Resultado). Session 4b (prompt
vs RAG A/B) is BLOCKED until this session lands P0 guardrails — do not start 4b here.

Also read session_4b_preflight_verification.md: fix `int(cfg("rag_top_k"))` truncating 0.95→0
if still present — that is a separate config bug but affects any validation run you use to
verify this session.

IMPORTANT — drift check: re-read the live failure logs cited in llm_truncation_review_06072026.md
(knowledge/data/llm_sessions/sessions/validate_20260706_182955_b47ed4ea/ and
validate_20260706_180421_48b2fa28/) and confirm the code paths in circuit_synthesizer.py,
semantic_reviewer.py, llm_json.py, ollama_native.py, llm_session_log.py still match the
review before implementing. Update llm_truncation_review if behavior already changed.

SOURCE OF TRUTH:
- docs/calibration_forge/llm_output_pipeline.md (§Session 4c entregables)
- docs/calibration_forge/llm_truncation_review_06072026.md (§Recommended mitigations P0–P3)
- docs/calibration_forge/logging_strategy.md (AI Context Buffer — extend, don't remove)

GOAL: Make LLM circuit generation and semantic review fail loudly and recoverably when
outputs truncate, stub, or parse as valid JSON but semantically incomplete — instead of
accepting misleading "OK" results in validate_complex_apps.

TASKS (P0 — must complete):
1. Normalize a top-level "done_reason" field in LLMClient's return dict for BOTH API paths,
   then read it in circuit_synthesizer and semantic_reviewer after every call. CRITICAL detail
   (code audit 06-jul, llm_output_pipeline.md §Auditoría): done_reason only exists on the
   native path today (ollama_native stores it in result["raw"]); LLMClient._chat_openai()
   DISCARDS choice.finish_reason and returns no "raw" at all. The atomic backend is
   OpenAI-only, so a guardrail reading result["raw"] would silently no-op exactly where
   Session 4d routes the reviewer. Map OpenAI finish_reason ("length"/"stop") and native
   raw.done_reason onto the same normalized field, and have all guardrails read ONLY it.
   Treat done_reason=="length" as failure. Treat empty content (after strip) as failure even
   if done_reason=="stop".
2. Post-parse validation in generate_circuit_json(): for each MCU/IC where _get_pinouts_context()
   injected a full pin table for that part value, require non-empty "pins" or "unconnected_pins"
   before accepting attempt 1. On failure, enter the same retry path as JSONDecodeError (attempt 2+).
3. semantic_reviewer: fix the empty-content truncation. Options in order of preference
   (research detail in llm_output_pipeline.md §Investigación externa — Ollama upstream issue
   16184 confirms num_predict caps thinking+content combined and recommends exactly this):
   (a) BEST: add a "format" passthrough to ollama_native.chat_native() payload (Ollama native
       structured outputs — bounds the final JSON without disabling thinking; ~1 line in the
       payload + a chat() kwarg) and have the reviewer pass format="json" or the issues schema;
   (b) pass think=False per-call on the native path (works top-level for Qwen3 family;
       note _use_native() currently ignores the per-call think override when deciding the
       path — works by accident today, document or fix);
   (c) disable_thinking=True (OpenAI path + reasoning_effort "none" — verify Ollama honors it
       for qwythos-9b-96k);
   (d) raise max_tokens in Pulse_cfg.json to 8192–16384 (palliative, compatible with all of
       the above — cheap to do regardless).
   Verify on a live --case esp32_sensors review. Routing review through atomic stays Session 4d
   scope. Document the choice in §Resultado.
   ALSO: extend review_netlist() to accept session_id/meta passthrough (like
   generate_circuit_json does) — today every review call lands in a random orphan session
   (attempt: 0, disconnected from the validation run that triggered it), which breaks A/B
   correlation for 4b.
4. ✅ ALREADY DONE (06-jul harness session — verify, do not redo): rag_top_k int-truncation
   fixed (Pulse_cfg.json 0.95 -> 1) + guard in circuit_synthesizer._circuit_example_rag_top_k()
   that warns and clamps to 1 if a future cfg edit truncates to 0 again.

TASKS (P1 — complete if P0 stable):
5. llm_json.py: add parse_llm_result(content, thinking) that tries content first, then extracts
   JSON from thinking when content is empty/invalid (use existing extract_json_text). NOTE:
   _chat_openai() already silently copies msg.thinking/msg.reasoning into content when content
   is empty (llm_client.py ~243-248) — the native path does not. UNIFY that existing behavior
   into parse_llm_result / one shared place instead of leaving two divergent fallbacks.
6. circuit_synthesizer: on done_reason length with partial JSON in content, add ONE continuation
   turn — append assistant partial + user "Continue the JSON from exactly where you stopped.
   No prose." Cap total turns at 3 per generation (initial + up to 2 recovery). Log each turn
   in llm_sessions with incrementing attempt meta. PREREQUISITE (code audit): LLMClient.chat()
   only accepts system+user strings and builds a fresh 2-message list internally — extend it
   with a messages/history parameter (both internal paths already consume message lists, small
   change) or add chat_continue(); without this there is no way to send the assistant partial.
7. Unify retry triggers: JSONDecodeError OR done_reason length OR post-parse semantic validation
   failure OR empty content — all should be able to trigger attempt 2 with logger.get_context().

TASKS (P2 — complete if time):
8. Pin count guard: reject components where len(pins) exceeds known pin count from symbols_index
   or pinouts_library by >10% (or hard cap 64 when no reference), retry with corrective user msg.
9. Tighten base_system_prompt FIDELIDAD DE PINES: when PINOUTS RELEVANTES lacks the MCU table,
   instruct "declare only used pins + unconnected_pins array" — do not enumerate unknown pads.

TASKS (P3 — observability + tests):
10. llm_session_log.record_llm_exchange: add top-level done_reason, content_len, thinking_len,
    eval_count from raw when present.
11. tests/test_llm_truncation_guards.py: fixture JSON files mimicking stub MCU, length truncation,
    thinking-only JSON, 1000-pin response — unit-test guards without live LLM.
12. docs/calibration_forge/evaluation_metrics.md: add "Generation Completeness" metric
    (MCU/IC pin declaration present when pinout was injected).

VERIFICATION (required):
- python -m knowledge.validate_complex_apps --case esp32_sensors (primary backend up)
- python -m knowledge.validate_complex_apps --case esp32_steppers
- Confirm: no run saves esp32_sensors.json with MCU lacking pins when synthesis "succeeds"
- pytest tests/test_llm_truncation_guards.py tests/test_forge.py (and any new tests) — all pass

HANDOFF (required):
- Update docs/calibration_forge/llm_output_pipeline.md §Resultado (Session 4c): what landed,
  before/after log snippets, which failure modes are now caught.
- Update llm_truncation_review_06072026.md: mark mitigations done, note remaining gaps for 4d.
- Update docs/calibration_forge/index.md milestone checklist.
- Update CURENT_SPRINT.md Session 4c header with ✅ when done.
- Explicitly unblock Session 4b only if P0 tasks 1–3 verified on live runs.
```

---

### Session 4d — Dual-backend orchestration & harness pipeline — **code landed** (live atomic verify pending)

**Recommended before Session 4b clean re-run.** Full scope: [`docs/calibration_forge/llm_output_pipeline.md`](docs/calibration_forge/llm_output_pipeline.md) §Session 4d + §Resultado.

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

## PRIOR SESSION CONTEXT

Session 4c P0 must be DONE — verify llm_output_pipeline.md §Resultado for 4c before starting.
Session 4b remains blocked until BOTH 4c P0 and this session's routing tasks are complete
(or explicitly deferred with written rationale in §Resultado).

IMPORTANT — drift check: confirm SemanticReviewer still uses get_llm_client() directly
(known smell as of 06-jul-2026) before refactoring. Confirm validate_complex_apps runs
cases strictly sequentially with no ThreadPool.

SOURCE OF TRUTH:
- docs/calibration_forge/llm_output_pipeline.md (§Session 4d, §Arquitectura objetivo)
- docs/calibration_forge/llm_truncation_review_06072026.md (§Impact on Session 4b)
- knowledge/llm_backends.py, knowledge/atomic_lane.py, Pulse_cfg.json llm.routing

GOAL: Use primary (Ollama :11431, reasoning) and atomic (llama-server :11439, fast JSON)
as complementary lanes — not two isolated clients — and make the validation harness report
per-stage backend and truncation metadata.

TASKS:
1. Refactor SemanticReviewer (and SemanticAIAgent if still used) to obtain LLM via
   get_backend_client(resolve_backend_name(task="review")) instead of get_llm_client().
   Honor llm.routing.review_backend from Pulse_cfg.json. NOTE (code audit 06-jul): the config
   value is currently "primary" — routing review to atomic requires changing
   llm.routing.review_backend to "atomic" in Pulse_cfg.json, not just the code refactor.
   auto_fallback already covers atomic-down (falls back to primary, as in all of today's runs).
2. Add optional CLI flags to validate_complex_apps.py:
   --backend (existing, synthesis) and --review-backend auto|primary|atomic
   (default: auto → routing config). Pass review backend into SemanticReviewer constructor.
   Check first whether 4c already added session_id/meta passthrough to review_netlist()
   (its task 3) — build on it rather than re-plumbing.
3. Default policy (document in §Resultado): synthesis on primary (think low), review on atomic
   (think none, json_mode true) when both healthy — reduces contention on reasoning budget.
   Two operational gotchas (llm_output_pipeline.md §Auditoría):
   (a) atomic is DOWN right now (health check to :11439 fails; qwythos.state.json has a stale
       pid) — start llama-server (scripts_dir in cfg, profile concurrent2) before verifying.
   (b) _chat_openai() pops response_format when is_reasoning_model(model) matches; the current
       atomic model qwen3-4b-instruct-48k does NOT match, so json_mode works — but if atomic
       ever runs a model with "qwq"/"r1"/"think" in the name, json_mode silently disables.
       Consider logging a warning on that pop.
4. Extend run_manifest.json / per-case JSON output with:
   - synthesis_backend, review_backend
   - generation_attempts, truncation_events (from 4c metadata if available)
   NOTE: "semantic_review" (issue_count/critical_count/issues) and "ab_variant" fields already
   exist per-case and in run_manifest since the 06-jul harness session — extend, don't recreate.
5. Investigate (document findings, implement only if low-risk): with concurrent2 atomic profile
   and primary up, measure whether sequential validate_complex_apps cases contend for GPU.
   Data point (06-jul evening): generations that took ~430s on an idle GPU stretched to
   ~790-880s while an embed rebuild briefly competed for the same Ollama instance — contention
   is real and measurable; capture before/after numbers in §Resultado.
   Do NOT parallelize all 5 A/B cases in this session — only document + optional 2-stage
   pipeline sketch for a future session.
6. Update mcp_server list_llm_backends / generate_circuit_from_text docs if routing changed.
7. Add tests/test_llm_backend_routing.py (or extend test_llm_backends.py): SemanticReviewer
   uses review route; synthesizer uses circuit route; fallback when atomic down.

VERIFICATION:
- With BOTH :11431 and :11439 healthy: one esp32_sensors run shows different backend ids in
  llm_session logs for circuit_synthesizer vs semantic_reviewer calls.
- With atomic down: review falls back to primary per auto_fallback without crash.
- pytest green.

HANDOFF (required):
- Update docs/calibration_forge/llm_output_pipeline.md §Resultado (Session 4d).
- Update docs/calibration_forge/index.md and CURENT_SPRINT.md Session 4d header.
- Update session_4b_preflight_verification.md if harness now covers semantic review routing.
- State clearly in prompt_vs_rag_balance.md dependency note: 4b may proceed after 4c+4d.
```

---

### Session 4b — Prompt vs. RAG rebalancing (depends on 4a ✅, **4c P0 ✅**, **4d verify pending**)

**Prerequisites (07-jul-2026):**
- [`docs/calibration_forge/llm_output_pipeline.md`](docs/calibration_forge/llm_output_pipeline.md) — **Session 4c P0 complete + verified live** (runs `212059`, `213418`)
- Session 4d — **code landed**; confirm one live run with `review_backend: atomic` before clean A/B (or document fallback in §Resultado)
- [`llm_truncation_review_06072026.md`](docs/calibration_forge/llm_truncation_review_06072026.md) — P0 mitigations verified on `esp32_rf_nfc` + `esp32_usb_devkit`
- **Parte 1 (confundido) already recorded** — [`prompt_vs_rag_balance.md`](docs/calibration_forge/prompt_vs_rag_balance.md) §Resultado A/B; do **not** use for trimming decisions

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

## PRIOR SESSION CONTEXT (Sessions 1-3 completed 06-jul-2026; Session 4a — see below)

Sessions 1 (KB fidelity), 2 (PulseLogger + design_experience loop), and 3 (pin model
coverage) are DONE — see their §Resultado sections in docs/calibration_forge/. Session 4a
(KiCad Symbol Knowledge Base) should also be DONE before you start this session; if it
isn't, STOP and either run 4a first or explicitly scope down (see DEPENDENCY CHECK).

What landed in Session 3 (do NOT redo):
- knowledge/circuit_synthesizer.py::_match_pinouts() / _compact_pinout(full=...) / NC
  convention / _normalize_unconnected_pins() — see pin_model_coverage.md §Resultado.
- Post-fix validation (06-jul-2026 13:09-13:16 UTC, run `validate_20260706_130942_b1a9364b`,
  backend `primary` only): esp32_sensors pin coverage confirmed 10.3% -> 100% with a real
  LLM call. This is ONE case on ONE backend — your task 2 A/B run below is what produces the
  full 5-case baseline; don't treat this single run as a substitute for it, but do treat it
  as evidence the pinout injection mechanism itself is sound going into the A/B.

What Session 4a should have landed (verify before proceeding):
- knowledge/kicad_symbol_parser.py + `python -m knowledge.build_symbol_index` +
  knowledge/data/symbols_index.json, ingested into ElectronicsKnowledgeBase as
  chunk_type="pinout".
- circuit_synthesizer._match_pinouts() now queries kb.query(..., chunk_type="pinout")
  instead of scoring pinouts_library.json directly, while preserving Session 3's
  ordered-list return shape, full/compact injection (primary match only gets the full pin
  table), and _normalize_unconnected_pins().
- Read docs/calibration_forge/kicad_symbol_kb.md §Próximos pasos (checked items) and
  pin_model_coverage.md for what 4a actually delivered vs. deferred.

DEPENDENCY CHECK (do this before anything else):
- Session 4c (LLM guardrails): MUST be complete — see llm_output_pipeline.md §Resultado.
  If P0 is not done, STOP — do not run the A/B experiment.
- Session 4d (dual-backend routing): SHOULD be complete — if deferred, document confounders
  (e.g. review still on primary) in your A/B writeup.
- Session 1 (KB fidelity): COMPLETED — see knowledge_base_fidelity.md §Resultado and the
  dependency note at the top of prompt_vs_rag_balance.md. RAG indexes enriched context
  (density ~80%). Caveat: dense vectors.npy may still be stale if Ollama was unavailable;
  run python -m knowledge.build_embed_index before the A/B if you want fresh dense retrieval.
- Session 2 (design_experience loop): COMPLETED — see dormant_features_audit.md
  §Resultado and prompt_vs_rag_balance.md's updated dependency note. The loop now
  produces real, durable data (knowledge/experiences/*.json persists and reloads
  into ElectronicsKnowledgeBase via _load_experiences()). A POC migration already
  exists: run `python -m knowledge.seed_poc_experience` to see the "ESP32 EN
  pull-up" rule migrated to a DesignExperience lesson and retrievable via
  kb.query(..., chunk_type="design_experience") — it already surfaces naturally
  in ESP32-related queries (see tests/test_rag_retrieval.py::test_rag_esp32_component).
  For task 3 below, build directly on this POC instead of starting from scratch —
  note in your handoff whether you kept, extended, or replaced it.
- Session 4a (KiCad symbol KB / pinout unification): check docs/calibration_forge/
  kicad_symbol_kb.md and pin_model_coverage.md for its actual completion state. If 4a
  was skipped, partially done, or fell back to pinouts_library.json for some parts, note
  that explicitly and adjust — your A/B experiment should still run, just document that
  pinout retrieval wasn't (fully) migrated to RAG yet.

IMPORTANT — drift check: the specific rule text and cfg values quoted in
prompt_vs_rag_balance.md (rag_top_k: 1, temperature: 0.1, etc.) may have shifted since
Session 3/4a touched circuit_synthesizer.py. Re-read the live file before editing —
specifically re-read _get_pinouts_context() and _build_system_prompt(), since 4a may have
changed how pinouts get injected into the prompt. Also note Session 2 added
`from core.logger import logger` and ai_review()/get_context() calls to this file (see
generate_circuit_json()) — preserve them, they're unrelated to this session's scope.

GOAL: Determine whether the hardcoded "REGLAS OBLIGATORIAS" in circuit_synthesizer.py and
semantic_reviewer.py are still pulling their weight now that there's a bigger local model,
a richer RAG, and (post-4a) unified pinout retrieval, and rebalance accordingly based on
evidence, not assumption.

TASKS:
1. Design and run an A/B comparison using knowledge/validate_complex_apps.py across all 5
   test cases (esp32_sensors, esp32_steppers, esp32_rf_nfc, esp32_usb_devkit, pulselab_zero):
   (a) current behavior with hardcoded rules + rag_top_k=1, vs.
   (b) hardcoded "OBLIGATORIAS" rules trimmed/removed + rag_top_k raised to 3-5.
   Use knowledge/semantic_reviewer.py issue counts (and manual inspection) as the quality
   signal, and record Pin Coverage Fidelity (knowledge/validate_complex_apps.py::_pin_coverage())
   for both variants as a secondary signal — it should stay high in both (a) and (b) if 4a's
   migration didn't regress anything. Record raw outputs under
   knowledge/data/validation_complex/runs/ as usual — don't overwrite prior runs, including
   the 06-jul-2026 13:09 esp32_sensors run referenced above.
2. Based on the result, decide how much of the rule text to trim from
   circuit_synthesizer.py's base_system_prompt and semantic_reviewer.py's _SYSTEM_PROMPT.
   Don't remove rules wholesale if (b) performs worse — this is meant to be evidence-driven,
   not a foregone conclusion.
3. Session 2 already prototyped this for one rule ("ESP32 EN needs 10k pull-up" — see
   knowledge/seed_poc_experience.py and knowledge/experiences/poc_esp32_en_pullup_rule.json).
   Decide whether to extend this pattern to the other "always-applicable" rules identified
   in your task 2 analysis (migrating them out of base_system_prompt / _SYSTEM_PROMPT into
   DesignExperience lessons), and if you do, actually remove the migrated rule text from the
   prompts this time (Session 2 deliberately left the prompt text in place, since that
   trade-off call belongs to this session).

HANDOFF (required before ending this session):
- Update docs/calibration_forge/prompt_vs_rag_balance.md with the A/B experiment results,
  your decision (and rationale) on what was trimmed/kept, and mark proposals done/rejected.
- Update docs/reviews/pulselab_review_05072026.md section 6 accordingly.
- If you had to scope down due to the dependency check above (e.g. Session 4a incomplete),
  leave a clear TODO pointer in both this doc and kicad_symbol_kb.md so it's obvious a
  re-run is needed later.
```

---

### Session 5 — Repo hygiene

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

SOURCE OF TRUTH (read this first):
- docs/reviews/pulselab_review_05072026.md (section 5, "Otros puntos menores observados")

IMPORTANT — drift check: this is the lowest-risk session but still verify each item is
still true before acting (e.g. confirm scratch/test_drc_fail.py still exists and is still
unreferenced elsewhere before deleting it).

GOAL: Clean up low-risk technical debt that doesn't block any of the other research
sessions, and can be done independently/at any point in the sequence.

TASKS:
1. Pin dependency versions in requirements.txt (pygame, numpy, scikit-learn, mcp, fastmcp,
   skidl, schemdraw, matplotlib, pytest, openai, python-dotenv, peft, trl, bitsandbytes,
   datasets). Pick versions matching what's actually installed/tested in this environment
   where possible; run the test suite (tests/test_forge.py etc.) after pinning to confirm
   nothing broke, per docs/architecture/SEGURIDAD_DEPENDENCIAS.md's warning about numpy/
   pygame major-version regressions.
2. Confirm scratch/test_drc_fail.py is not imported/referenced anywhere else, then remove it
   (or move it under a clearly-named legacy/scratch location that's gitignored, if the team
   prefers keeping it locally rather than deleting).
3. Reconcile the duplicate architecture docs: docs/Architecture.md +
   docs/Architecture_violations.md (root) vs. docs/architecture/APP_ARCHITECTURE.md +
   docs/architecture/ARCHITECTURE_VIOLATIONS.md (subfolder). Diff their content, merge
   anything from the root versions that's missing from the subfolder versions (e.g. the
   autorouter A* description), and turn the root-level files into short stubs pointing to
   the subfolder versions (don't just delete them without a pointer, in case anything links
   to the old paths).
4. Optional if time permits: add a minimal .github/workflows/ci.yml that runs
   tests/test_forge.py and tests/test_rag_retrieval.py on push/PR (a draft already exists in
   docs/reviews/pulselab_review_23042026.md section 5.6 as a starting point, though verify it
   still matches current test file locations/needs before reusing it verbatim).

HANDOFF (required before ending this session):
- Update docs/reviews/pulselab_review_05072026.md section 5 to mark these items resolved.
- Update docs/roadmap.md if any of this closes an item tracked there (e.g. CI/CD).
- If you merged the architecture docs, update any cross-links in docs/roadmap.md,
  docs/calibration_forge/index.md, or README.md that pointed at the old locations.
```

---

One practical suggestion: after each session finishes, skim the "HANDOFF" edits it made to the docs before pasting the next prompt — that's the whole point of the protocol, and it's a cheap way to catch drift before it compounds across six sessions.