# Current sprint — Calibration Forge

> **Role:** living  
> **Status:** active  
> **Source of truth for:** session order, blockers, and next actions  
> **Last verified:** 2026-07-07  
> **See also:** [`../calibration_forge/index.md`](../calibration_forge/index.md) · [`../roadmap.md`](../roadmap.md) · [`../status/FORGE_STATUS.md`](./FORGE_STATUS.md)

## Execution order (Sessions 4+)

**4a** ✅ → **4c** ✅ (P0 verified) → **4d** (~ code landed) → **4b** ⏳ → **5** ✅ (repo hygiene)

## Where we are (07-jul-2026)

| Session | Status | Outcome doc |
|---------|--------|-------------|
| 1 — KB fidelity | ✅ | [`knowledge_base_fidelity.md`](../calibration_forge/knowledge_base_fidelity.md) §Resultado |
| 2 — PulseLogger + design experience | ✅ | [`dormant_features_audit.md`](../calibration_forge/dormant_features_audit.md) §Resultado |
| 3 — Pin model coverage | ✅ | [`pin_model_coverage.md`](../calibration_forge/pin_model_coverage.md) §Resultado |
| 4a — KiCad symbol KB | ✅ | [`kicad_symbol_kb.md`](../calibration_forge/kicad_symbol_kb.md) §Resultado |
| 4c — LLM guardrails | ✅ P0 live | [`pipelines/llm_output_pipeline.md`](../calibration_forge/pipelines/llm_output_pipeline.md) §Resultado |
| 4d — Dual-backend orchestration | ~ code landed | same — **pending live verify** review on `atomic` |
| 4b — Prompt vs RAG A/B | ⏳ clean re-run | [`prompt_vs_rag_balance.md`](../calibration_forge/prompt_vs_rag_balance.md) |
| 5 — Repo hygiene | ✅ | [`verification/session_4b_preflight.md`](../calibration_forge/verification/session_4b_preflight.md) §Session 5 |

## Next actions

1. **Verify Session 4d live** — run `validate_complex_apps` with `review_backend: atomic`; confirm semantic review JSON on ≥1 case.
2. **Session 4b clean A/B** — `--variant a` + `--variant b`, 5 cases each; use [`prompt_vs_rag_balance.md`](../calibration_forge/prompt_vs_rag_balance.md) for decision criteria.
3. **Defer trimming decision** until 4b clean data (part 1 run `182955`/`201754` is confounded — do not use for rule removal).

## Active blockers (resolved infra)

Preflight blockers from [`verification/session_4b_preflight.md`](../calibration_forge/verification/session_4b_preflight.md) §7 are **resolved**:

- `rag_top_k` int-truncation bug fixed (`≥ 1`)
- Embeddings manifest matches **5685** chunks (`embed_index_loaded: true`)
- Reviewer guardrails (4c P0) verified on runs `212059` / `213418`

## Agent prompts

Paste-ready session prompts live in [`../sprints/prompts/`](../sprints/prompts/) (split from the former monolithic `CURENT_SPRINT.md`).

Handoff discipline: update the relevant finding doc §Resultado, then sync [`../calibration_forge/index.md`](../calibration_forge/index.md) and [`FORGE_STATUS.md`](./FORGE_STATUS.md) if metrics changed.

## Key numbers (see FORGE_STATUS for refresh ritual)

- RAG: **5685** chunks (5326 `pinout`, 326 `circuit_example`)
- Tests: **102** collected (`pytest tests/ --co -q`)
- MCP tools: **31** (`mcp_server/server.py`)
