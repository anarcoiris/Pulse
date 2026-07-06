# Evaluator & training loop — implementation plan

> **Role:** reference  
> **Status:** active (stub index)  
> **Source of truth for:** how Calibration Forge sessions connect to the evaluator harness  
> **Last verified:** 2026-07-07  
> **See also:** [`calibration_forge/index.md`](./calibration_forge/index.md) · [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md)

This file replaces the missing `implementation_plan.md` link from the Calibration Forge index.

## Components

| Piece | Location | Doc |
|-------|----------|-----|
| Complex-case harness | `knowledge/validate_complex_apps.py` | [`calibration_forge/evaluation_metrics.md`](./calibration_forge/evaluation_metrics.md) |
| Circuit synthesis | `knowledge/circuit_synthesizer.py` | [`calibration_forge/prompt_vs_rag_balance.md`](./calibration_forge/prompt_vs_rag_balance.md) |
| Semantic review | `knowledge/semantic_reviewer.py` | [`calibration_forge/pipelines/llm_output_pipeline.md`](./calibration_forge/pipelines/llm_output_pipeline.md) |
| RAG / KB | `knowledge/rag_engine.py` | [`calibration_forge/knowledge_base_fidelity.md`](./calibration_forge/knowledge_base_fidelity.md) |
| Run artifacts | `knowledge/data/validation_complex/runs/` | per-run `run_manifest.json` |

## Session sequence

See [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) for live order and blockers.

## Agent execution prompts

[`sprints/prompts/`](./sprints/prompts/)
