Here are five self-contained prompts, one per session, meant to be pasted into a fresh Agent-mode conversation each time, in order. Each one is written so it doesn't depend on this chat's history — it re-points the agent to the actual files (the "source of truth") rather than to my summaries of them.

A few notes on how I built these before the prompts themselves:

- **Source of truth = the docs in `docs/calibration_forge/*.md` and `docs/reviews/pulselab_review_05072026.md`**, not this conversation. They're dated snapshots (05-jul-2026) of what the code looked like when I read it — they are not guaranteed to still be 100% accurate by the time you run Session 3, 4, or 5, especially if an earlier session already touched shared files (`rag_engine.py`, `Pulse_cfg.json`, etc.).
- **Drift handling is baked into every prompt** as an explicit step: "verify against current code before acting, and if reality has diverged from the doc, update the doc to match reality — don't silently follow stale instructions and don't silently deviate without leaving a trace."
- **Handoff is mandatory**, not optional: each prompt ends by requiring the agent to update its own reference doc (mark done items, log deviations, add new findings) plus touch `docs/roadmap.md` / `docs/calibration_forge/index.md` / `FORGE_STATUS.md` if it changed something those track. This is exactly the sync discipline used when I created these docs — it should keep propagating forward.
- Session 4 has an extra guard clause because it structurally depends on Session 1's outcome — if you run them out of order, the agent will check and adapt instead of assuming Session 1 happened.
- **Session 1 completed 06-jul-2026** — see `docs/calibration_forge/knowledge_base_fidelity.md` §Resultado. Session 2 prompt below includes a prior-session context block; paste it as-is (do not strip it).
- **Session 2 completed 06-jul-2026** — see `docs/calibration_forge/dormant_features_audit.md` §Resultado. Session 3 prompt below now includes a prior-session context block (shared-file overlap warning on `circuit_synthesizer.py`); Session 4's dependency check was also updated to reflect that Session 2's design-experience loop is done and has a working POC. Paste both as-is.

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

### Session 3 — Pin model coverage

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

### Session 4 — Prompt vs. RAG rebalancing (depends on Session 1 + optionally Session 2)

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

SOURCE OF TRUTH (read these first, in full):
- docs/calibration_forge/prompt_vs_rag_balance.md
- docs/reviews/pulselab_review_05072026.md (section 4.3)
- docs/calibration_forge/knowledge_base_fidelity.md (§Resultado — Session 1 completed 06-jul-2026)

DEPENDENCY CHECK (do this before anything else):
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
  For task 4 below, build directly on this POC instead of starting from scratch —
  note in your handoff whether you kept, extended, or replaced it.

IMPORTANT — drift check: the specific rule text and cfg values quoted in
prompt_vs_rag_balance.md (rag_top_k: 1, temperature: 0.1, etc.) may have shifted if Session
3 already touched circuit_synthesizer.py. Re-read the live file before editing. Also note
Session 2 added `from core.logger import logger` and ai_review()/get_context() calls to
this file (see generate_circuit_json()) — preserve them, they're unrelated to this session's
scope.

GOAL: Determine whether the hardcoded "REGLAS OBLIGATORIAS" in circuit_synthesizer.py and
semantic_reviewer.py are still pulling their weight now that there's a bigger local model
and a richer RAG, and rebalance accordingly based on evidence, not assumption.

TASKS:
1. Unify knowledge/circuit_synthesizer.py::_match_pinouts() into ElectronicsKnowledgeBase
   (knowledge/rag_engine.py) as a proper chunk_type (e.g. "pinout"), replacing the separate
   keyword-scoring system with the existing hybrid retrieval.
2. Design and run an A/B comparison using knowledge/validate_complex_apps.py across all 5
   test cases (esp32_sensors, esp32_steppers, esp32_rf_nfc, esp32_usb_devkit, pulselab_zero):
   (a) current behavior with hardcoded rules + rag_top_k=1, vs.
   (b) hardcoded "OBLIGATORIAS" rules trimmed/removed + rag_top_k raised to 3-5.
   Use knowledge/semantic_reviewer.py issue counts (and manual inspection) as the quality
   signal. Record raw outputs under knowledge/data/validation_complex/runs/ as usual — don't
   overwrite prior runs.
3. Based on the result, decide how much of the rule text to trim from
   circuit_synthesizer.py's base_system_prompt and semantic_reviewer.py's _SYSTEM_PROMPT.
   Don't remove rules wholesale if (b) performs worse — this is meant to be evidence-driven,
   not a foregone conclusion.
4. Session 2 already prototyped this for one rule ("ESP32 EN needs 10k pull-up" — see
   knowledge/seed_poc_experience.py and knowledge/experiences/poc_esp32_en_pullup_rule.json).
   Decide whether to extend this pattern to the other "always-applicable" rules identified
   in your task 3 analysis (migrating them out of base_system_prompt / _SYSTEM_PROMPT into
   DesignExperience lessons), and if you do, actually remove the migrated rule text from the
   prompts this time (Session 2 deliberately left the prompt text in place, since that
   trade-off call belongs to this session).

HANDOFF (required before ending this session):
- Update docs/calibration_forge/prompt_vs_rag_balance.md with the A/B experiment results,
  your decision (and rationale) on what was trimmed/kept, and mark proposals done/rejected.
- Update docs/reviews/pulselab_review_05072026.md section 6 accordingly.
- If you had to scope down due to the dependency check above, leave a clear TODO pointer in
  both this doc and knowledge_base_fidelity.md so it's obvious a re-run is needed later.
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

One practical suggestion: after each session finishes, skim the "HANDOFF" edits it made to the docs before pasting the next prompt — that's the whole point of the protocol, and it's a cheap way to catch drift before it compounds across five sessions.