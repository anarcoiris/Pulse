# Current sprint — Calibration Forge

> **Role:** living  
> **Status:** active  
> **Source of truth for:** session order, blockers, and next actions  
> **Last verified:** 2026-07-18  
> **See also:** [`../calibration_forge/index.md`](../calibration_forge/index.md) · [`../roadmap.md`](../roadmap.md) · [`../status/FORGE_STATUS.md`](./FORGE_STATUS.md)

## Execution order (Sessions 4+)

**4a** ✅ → **4c** ✅ (P0 verified) → **4d** ✅ (verified live 16-jul) → **4b** ⏳ → **5** ✅ (repo hygiene)

## Where we are (18-jul-2026)

| Session | Status | Outcome doc |
|---------|--------|-------------|
| 1 — KB fidelity | ✅ | [`knowledge_base_fidelity.md`](../calibration_forge/knowledge_base_fidelity.md) §Resultado |
| 2 — PulseLogger + design experience | ✅ | [`dormant_features_audit.md`](../calibration_forge/dormant_features_audit.md) §Resultado |
| 3 — Pin model coverage | ✅ | [`pin_model_coverage.md`](../calibration_forge/pin_model_coverage.md) §Resultado |
| 4a — KiCad symbol KB | ✅ | [`kicad_symbol_kb.md`](../calibration_forge/kicad_symbol_kb.md) §Resultado |
| 4c — LLM guardrails | ✅ P0 live | [`pipelines/llm_output_pipeline.md`](../calibration_forge/pipelines/llm_output_pipeline.md) §Resultado |
| 4d — Dual-backend orchestration | ✅ **verified live** | Run `20260716_004628` confirms `review_backend: atomic` successful |
| 4b — Prompt vs RAG A/B | ⏳ clean re-run | [`prompt_vs_rag_balance.md`](../calibration_forge/prompt_vs_rag_balance.md) |
| 4e — Forge Studio CLI | ✅ | [`forge_studio.md`](../calibration_forge/forge_studio.md) §Resultado |
| 5 — Repo hygiene | ✅ | [`verification/session_4b_preflight.md`](../calibration_forge/verification/session_4b_preflight.md) §Session 5 |

## Next actions

1. **Session 4b clean A/B** — `--variant a` + `--variant b`, 5 cases each; use [`prompt_vs_rag_balance.md`](../calibration_forge/prompt_vs_rag_balance.md) for decision criteria. **Unblocked by PCIe instability mitigation (VRAM cache isolation) — execute immediately.**
2. **Defer trimming decision** until 4b clean data (part 1 run `182955`/`201754` is confounded — do not use for rule removal).
3. **Clean planning checks** — verify or correct false completion checkmarks in `current_plan_10072026.md` (e.g. DRC unification, symbol maps).

## Active blockers

None. Session 4d and the subsequent physical PCIe link reset crashes are resolved. 
- *Hardware Blocker:* Dynamic prompt caching offloading (`--cache-ram`) in `llama.cpp` saturated the PCIe link, causing GPU1 drops and kernel-level hangs. Mitigated via VRAM-only cache (`--cache-ram 0`) and dynamic tensor splitting. See [Post-Mortem](../calibration_forge/verification/pcie_instability_postmortem.md).

Previous preflight blockers from [`verification/session_4b_preflight.md`](../calibration_forge/verification/session_4b_preflight.md) §7 remain resolved:
- `rag_top_k` int-truncation bug fixed (`≥ 1`)
- Embeddings manifest matches **5685** chunks (`embed_index_loaded: true`)
- Reviewer guardrails (4c P0) verified on runs `212059` / `213418`

## Agent prompts

Paste-ready session prompts live in [`../sprints/prompts/`](../sprints/prompts/) (split from the former monolithic `CURRENT_SPRINT.md`).

Handoff discipline: update the relevant finding doc §Resultado, then sync [`../calibration_forge/index.md`](../calibration_forge/index.md) and [`FORGE_STATUS.md`](./FORGE_STATUS.md) if metrics changed.

## Key numbers (see FORGE_STATUS for refresh ritual)

- RAG: **5685** chunks (5326 `pinout`, 326 `circuit_example`)
- Tests: **110** collected (`pytest tests/ --co -q`); Forge Studio: **10** unit tests
- MCP tools: **31** (`mcp_server/server.py`)
- Forge Studio: `python -m studio` — see [`forge_studio.md`](../calibration_forge/forge_studio.md)
- Latest validation: run `20260716` — `pulselab_zero` 24 components, 97.4% pin coverage, 2 gen attempts

## Changes since last sync (07-jul → 18-jul)

- Session 4d **verified live** (run 20260716 uses `review_backend: atomic` successfully)
- Diagnosed PCIe instability (Lost GPU error) caused by `--cache-ram`; resolved with `--cache-ram 0` mitigation
- Dead code removed: `knowledge/kicad_importer.py`, `knowledge/layout_ai.py`
- `skills/` knowledge base subsystem created (2 active rules, formal architecture)
- 6 validation runs executed (10-16 jul)
- `pulselab_review_23042026.md` restored (had been deleted with 7 dangling references)
- `requirements.txt`: `rich` pinned to `==14.3.3`
- `docs/README.md`: broken root stub links fixed, `skills/` reference added
- Weekly review: [`../reviews/pulselab_review_18072026.md`](../reviews/pulselab_review_18072026.md)
- Root hygiene completed: moved loose tests to `tests/fixtures/`, `current_plan.md` to `docs/archive/`, `Hierarchical-island-packing-algorythm.md` to `docs/architecture/`

