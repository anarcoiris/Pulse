# Índice de Investigaciones: Calibration Forge (Iterativa)

> **Role:** entry (research hub)  
> **Status:** active  
> **Source of truth for:** catalog of findings, references, and verification logs  
> **Last verified:** 2026-07-18  
> **See also:** [`../status/CURRENT_SPRINT.md`](../status/CURRENT_SPRINT.md) · [`../implementation_plan.md`](../implementation_plan.md) · [`../../skills/`](../../skills/) (knowledge base)

Este documento orquesta las líneas de investigación para el bucle de entrenamiento y validación de PulseLab Forge.

## Plan de ejecución

- [`implementation_plan.md`](../implementation_plan.md) — evaluator harness + session wiring
- [`../status/CURRENT_SPRINT.md`](../status/CURRENT_SPRINT.md) — **orden de sesiones y next actions**
- [`../sprints/prompts/`](../sprints/prompts/) — agent paste prompts (archived per session)

## Revisiones técnicas (históricas)

- [`pulselab_review_18072026.md`](../reviews/pulselab_review_18072026.md) — revisión vigente (18-jul-2026)
- [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) — anterior (05-jul-2026)
- [`pulselab_review_23042026.md`](../reviews/pulselab_review_23042026.md) — superada

---

## Active findings (open decisions)

| # | Topic | Doc | Status |
|---|-------|-----|--------|
| 8 | Balance prompt vs RAG | [`prompt_vs_rag_balance.md`](./prompt_vs_rag_balance.md) | 4b clean re-run pending (part 1 confounded) |

---

## Completed findings (§Resultado)

| # | Topic | Doc |
|---|-------|-----|
| 6 | Pin model coverage | [`pin_model_coverage.md`](./pin_model_coverage.md) |
| 7 | KB ingestion fidelity | [`knowledge_base_fidelity.md`](./knowledge_base_fidelity.md) |
| 9 | Dormant features (PulseLogger, design experience) | [`dormant_features_audit.md`](./dormant_features_audit.md) |
| 10 | KiCad symbol KB / pinout RAG | [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) |
| 11 | Forge Studio CLI (headless LLM debug) | [`forge_studio.md`](./forge_studio.md) |

---

## Reference (specs & infrastructure)

| Topic | Doc |
|-------|-----|
| Evaluation metrics | [`evaluation_metrics.md`](./evaluation_metrics.md) |
| Logging / AI context buffer | [`logging_strategy.md`](./logging_strategy.md) |
| GND vs `0` unification | [`gnd_unification.md`](./gnd_unification.md) |
| Forge Studio (headless LLM debug) | [`forge_studio.md`](./forge_studio.md) |

---

## Verification logs (incident / preflight)

| Doc | Notes |
|-----|-------|
| [`verification/session_4b_preflight.md`](./verification/session_4b_preflight.md) | Independent code/config audit before 4b |
| [`verification/pcie_instability_postmortem.md`](./verification/pcie_instability_postmortem.md) | PCIe hardware instability during validation runs |
| [`verification/llm_truncation_review_06072026.md`](./verification/llm_truncation_review_06072026.md) | Evidence for Session 4c — links to pipeline doc |

---

## Backlog research (not blocking current sprint)

| Topic | Doc |
|-------|-----|
| KiCad schematic parsing | [`kicad_parsing.md`](./kicad_parsing.md) |
| External datasets | [`dataset_research.md`](./dataset_research.md) |

---

## Estabilización pendiente (fuera de sesiones numeradas)

- **Undo/Redo Fix** — snapshot-first timing
- **Modelo Multipin** — Editor + netlist + esquemáticos (ver [`pin_model_coverage.md`](./pin_model_coverage.md))
- **Interactividad AI** — popup revisión semántica
- **Headless Mode** — CLI v1 shipped as **Forge Studio** (`python -m studio`) — see [`forge_studio.md`](./forge_studio.md); web canvas deferred

---

## Milestones

- [x] Sessions 1–3, 4a, 4c P0, 4d, 4e, 5 — ver §Resultado en docs citados
- [ ] **Session 4b clean A/B** — [`prompt_vs_rag_balance.md`](./prompt_vs_rag_balance.md) (4d blocker resolved 16-jul)

---
*Última actualización: 18-jul-2026 (weekly review sync — 4d verified, dead code removed, skills/ created)*
