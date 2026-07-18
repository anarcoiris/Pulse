# PulseLab documentation map

> **Role:** entry / map  
> **Status:** active  
> **Source of truth for:** where to find every class of documentation in this repo  
> **Last verified:** 2026-07-18  

## Start here

| Need | Document |
|------|----------|
| **What we're doing now** | [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) |
| **Current metrics** (tests, RAG chunks, MCP tools) | [`status/FORGE_STATUS.md`](./status/FORGE_STATUS.md) |
| **Product direction** (phases, themes) | [`roadmap.md`](./roadmap.md) |
| **System design** | [`architecture/APP_ARCHITECTURE.md`](./architecture/APP_ARCHITECTURE.md) |

## Calibration Forge (LLM / RAG / evaluation)

| Need | Document |
|------|----------|
| **Research hub** (findings, status, milestones) | [`calibration_forge/index.md`](./calibration_forge/index.md) |
| **LLM pipeline hardening** | [`calibration_forge/pipelines/llm_output_pipeline.md`](./calibration_forge/pipelines/llm_output_pipeline.md) |
| **Evaluator / training loop plan** | [`implementation_plan.md`](./implementation_plan.md) |
| **Agent paste prompts** (historical sessions) | [`sprints/prompts/`](./sprints/prompts/) |

## How to run things

| Task | Document / command |
|------|-------------------|
| **Forge Studio** (streaming LLM debug shell) | [`calibration_forge/forge_studio.md`](./calibration_forge/forge_studio.md) — `python -m studio` |
| Fab export + DRC gate | [`workflows/howto/fabrication_pipeline.md`](./workflows/howto/fabrication_pipeline.md) |
| MCP ESP32 devboard workflow | [`workflows/howto/esp32_devboard_mcp.md`](./workflows/howto/esp32_devboard_mcp.md) |
| Component / footprint management | [`workflows/howto/component_management.md`](./workflows/howto/component_management.md) |
| Batch LLM validation | `python -m knowledge.validate_complex_apps --case esp32_sensors` |

## Reference & architecture

- [`architecture/`](./architecture/) — APP architecture, violations, coding guidelines, design system, dependencies
- [`calibration_forge/evaluation_metrics.md`](./calibration_forge/evaluation_metrics.md) — metric definitions
- [`calibration_forge/logging_strategy.md`](./calibration_forge/logging_strategy.md) — PulseLogger / AI context buffer

## Historical (read-only)

| Type | Location |
|------|----------|
| Point-in-time reviews | [`reviews/`](./reviews/) |
| Frozen baselines | [`archive/`](./archive/) |
| One-off refactor tickets | [`workflows/plans/`](./workflows/plans/) |
| Verification / incident logs | [`calibration_forge/verification/`](./calibration_forge/verification/) |

## Independent research (outside Forge sprints)

| Project | Location |
|---------|----------|
| Cristales Solares — transparent TE windows | [`../documents/Cristales_Solares/`](../documents/Cristales_Solares/) |

See [`../documents/README.md`](../documents/README.md) for the research-projects map.

## Doc roles (convention)

Each doc under `docs/` should declare one primary role in front matter:

| Role | Purpose |
|------|---------|
| `entry` | Navigation only |
| `living` | Current sprint / metrics |
| `reference` | How the system works |
| `finding` | Research hypothesis → §Resultado |
| `verification` | Preflight / incident audit |
| `workflow` | Durable how-to |
| `review` | Frozen snapshot |
| `archive` | Do not edit in place |

Living docs link **down** to research §Resultado. Research docs link **up** to `CURRENT_SPRINT` for session ordering.

## Other top-level entries

- [`../README.md`](../README.md) — install & run
- [`../skills/`](../skills/) — structured knowledge base for agent evaluation (domain rules, finding schemas, case studies)
- [`reviews/`](./reviews/) — chronological technical reviews (latest: [`pulselab_review_18072026.md`](./reviews/pulselab_review_18072026.md))
