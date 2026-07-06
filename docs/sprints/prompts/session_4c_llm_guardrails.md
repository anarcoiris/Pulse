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
