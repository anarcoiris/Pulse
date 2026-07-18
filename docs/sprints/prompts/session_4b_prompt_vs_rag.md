### Session 4b — Prompt vs. RAG rebalancing (depends on 4a ✅, **4c P0 ✅**, **4d verified live ✅**)

**Prerequisites (18-jul-2026):**
- [`docs/calibration_forge/llm_output_pipeline.md`](docs/calibration_forge/llm_output_pipeline.md) — **Session 4c P0 complete + verified live** (runs `212059`, `213418`)
- Session 4d — **verified live** (run `20260716_004628` successfully offloaded reviews to the atomic backend)
- PCIe Instability Mitigation — **CRITICAL**: The Qwythos LLM server must launch with `--cache-ram 0` and dynamic VRAM tensor splitting to avoid physical PCIe reset failures (Lost GPU) on GPU1. See [Post-Mortem](../calibration_forge/verification/pcie_instability_postmortem.md).
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
