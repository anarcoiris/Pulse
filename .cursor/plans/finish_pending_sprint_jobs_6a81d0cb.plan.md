---
name: Finish pending sprint jobs
overview: "Finish all documented pending work in order: post-run bookkeeping for the in-flight A/B, embed index rebuild, Session 4c (guardrails), Session 4d (dual-backend routing), Session 4b clean A/B re-run, and Session 5 repo hygiene — with mandatory doc handoffs after each phase."
todos:
  - id: phase0-monitor
    content: Monitor A/B run to completion (variant A last case + variant B), no GPU-competing work
    status: completed
  - id: phase1-compile
    content: Compile confounded A/B comparison table into prompt_vs_rag_balance.md + preflight/index updates
    status: completed
  - id: phase1-embed
    content: Rebuild dense embed index and verify manifest chunk_count
    status: completed
  - id: phase2-4c-p0
    content: "Session 4c P0: normalized done_reason, post-parse pin validation, reviewer format/thinking fix, session_id passthrough, live verification"
    status: completed
  - id: phase3-4c-p1p3
    content: "Session 4c P1-P3: parse_llm_result, continuation turn, unified retries, guards, log fields, truncation-guard tests, metric + handoff docs"
    status: completed
  - id: phase4-4d
    content: "Session 4d: reviewer routing to atomic, cfg change, harness flags/manifest fields, routing tests + handoff"
    status: completed
  - id: phase5-4b
    content: "Session 4b: clean A/B re-run (checkpoint first), baseline table, evidence-driven rule-trim decision + handoff"
    status: in_progress
  - id: phase6-hygiene
    content: "Session 5: pin requirements, scratch cleanup, merge duplicate architecture docs, optional CI, fix duplicate git path artifacts"
    status: completed
isProject: false
---

# Finish All Pending Documented Jobs

Documented execution order (per [CURENT_SPRINT.md](CURENT_SPRINT.md)): 4a done → **4c → 4d → 4b → 5**, plus the immediate leftovers from today's harness session. The in-flight A/B run (variant A on last case, variant B next, ~1.5–2 h left) is left untouched until it exits.

## Phase 0 — While the run finishes (no GPU-competing work)
- Monitor terminal `333245` until both variants complete. No embed rebuild or LLM calls meanwhile (contention already measured: 430s → 880s per generation).

## Phase 1 — Post-run bookkeeping (immediately after exit)
- Compile the pin-coverage + semantic-review comparison table from `knowledge/data/validation_complex/runs/` for both variants; append to [docs/calibration_forge/prompt_vs_rag_balance.md](docs/calibration_forge/prompt_vs_rag_balance.md) **explicitly labeled as confounded evidence** (reviewer truncated on ~all cases; not the 4b baseline). Harvest reviewer-failure stats as 4c evidence.
- Rebuild dense embeddings: `python -m knowledge.build_embed_index` (clip fix + batching already landed); verify `manifest.json` chunk_count matches live KB (~5.7k).
- Update [session_4b_preflight_verification.md](docs/calibration_forge/session_4b_preflight_verification.md) and `index.md` checklists.

## Phase 2 — Session 4c P0 (unblocks everything)
Per the refined prompt in CURENT_SPRINT.md:
- Normalize `done_reason` across BOTH API paths in [knowledge/llm_client.py](knowledge/llm_client.py) (native `raw.done_reason` + OpenAI `finish_reason`, currently discarded); guardrails read only the normalized field. `length` or empty content ⇒ recoverable failure.
- Post-parse validation in `generate_circuit_json()`: MCU/IC with injected full pin table must have non-empty `pins`/`unconnected_pins`, else retry path.
- Reviewer truncation fix, preferred option: add `format` passthrough to `ollama_native.chat_native()` (Ollama structured outputs — bounds final JSON without killing thinking); fallbacks: `think=False` per-call, `disable_thinking=True`, raise `max_tokens`. Plus `session_id`/`meta` passthrough in `review_netlist()` (ends orphan log sessions).
- Verify live: `--case esp32_sensors` and `--case esp32_steppers`; stub MCU and empty reviewer must no longer pass as OK.

## Phase 3 — Session 4c P1–P3
- `parse_llm_result(content, thinking)` in [knowledge/llm_json.py](knowledge/llm_json.py), unifying the existing hidden OpenAI-path fallback.
- `messages` param on `LLMClient.chat()` + ONE continuation turn on truncated partial JSON (max 3 turns), logged with incrementing attempt.
- Unified retry triggers; pin-count guard vs `symbols_index`; prompt tightening (FIDELIDAD DE PINES).
- Observability: top-level `done_reason`/`content_len`/`thinking_len` in `llm_session_log`; `tests/test_llm_truncation_guards.py` with fixtures for the 4 failure modes; Generation Completeness metric in `evaluation_metrics.md`.
- Handoff: `llm_output_pipeline.md` §Resultado, truncation review, CURENT_SPRINT header ✅.

## Phase 4 — Session 4d (dual-backend orchestration)
- `SemanticReviewer` → `get_backend_client(resolve_backend_name(task="review"))`; change `llm.routing.review_backend` to `"atomic"` in [Pulse_cfg.json](Pulse_cfg.json).
- Start the atomic llama-server (`:11439`, profile concurrent2; stale pid in state file). `--review-backend` flag in the harness; `synthesis_backend`/`review_backend`/`generation_attempts`/`truncation_events` in manifests (extend existing fields, don't recreate).
- Routing tests + verification with both backends healthy; fallback check with atomic down. Handoff docs.

## Phase 5 — Session 4b clean A/B re-run (checkpoint before starting)
- Re-run `validate_complex_apps --variant a` then `--variant b` (5 cases each) with guardrails active — another multi-hour GPU run; will confirm timing before launching.
- Compile the real baseline table; make the evidence-driven rule-trim decision (task 2/3 of 4b prompt — extend the Session 2 DesignExperience POC if variant B holds up). Handoff: `prompt_vs_rag_balance.md`, review doc §6.

## Phase 6 — Session 5 repo hygiene
- Pin `requirements.txt` versions; remove/relocate `scratch/test_drc_fail.py`; merge duplicate architecture docs into `docs/architecture/` with root stubs; optional minimal CI workflow.
- Also resolve the duplicated backslash-path untracked doc entries visible in git status (Windows path artifact).

Every phase ends with its documented HANDOFF edits so the source-of-truth docs never drift.