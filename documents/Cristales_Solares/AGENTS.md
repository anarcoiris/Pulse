# Agent context — Cristales Solares

> Paste or reference this file when starting Cursor Agent sessions on this project.

## Scope

Independent **materials / photonics / thermoelectric window** research. Not Calibration Forge, not PCB LLM work.

## Read first

1. [`README.md`](./README.md) — scope and layout  
2. [`STATUS.md`](./STATUS.md) — phase and next actions  
3. [`index.md`](./index.md) — topic map  
4. [`manuscript/literature_review.md`](./manuscript/literature_review.md) — canonical science content  

## Writing rules

- New **claims** need a source → add to [`literature/sources.bib`](./literature/sources.bib) and a `notes/` entry.
- Settled investigations → [`findings/_template.md`](./findings/_template.md) with a **§Resultado** section.
- Update [`STATUS.md`](./STATUS.md) and [`index.md`](./index.md) when closing a milestone.
- Do not edit [`manuscript/full_draft_202607_archive.md`](./manuscript/full_draft_202607_archive.md) except to delete after dedup confirmation.

## Code rules

- Python for this project lives under [`simulations/`](./simulations/) and [`tools/`](./tools/).
- Use the project-local venv (`simulations/.venv`); do not add deps to root `requirements.txt` unless integrating with Pulse.
- Prefer numpy/scipy/matplotlib; document units in script headers.

## Language

Manuscript and notes may be **Spanish**; findings titles and STATUS may be bilingual. Keep symbol names (ε, μ, ZT, ΔT) consistent with [`glossary.md`](./glossary.md).

## Suggested agent tasks

| Task | Output |
|------|--------|
| Literature pass on WO₃ TE windows | `notes/`, bib entries |
| Drude–Lorentz visible/IR toy model | `simulations/em_drude_demo.py` |
| Facade ΔT energy balance | `findings/f01_facade_delta_t.md` |
| Material comparison table | `data/material_candidates.csv` |
