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
