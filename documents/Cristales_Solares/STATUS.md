# Cristales Solares — project status

> **Role:** living  
> **Last updated:** 2026-07-14  
> **Phase:** 0 — bootstrap & knowledge indexing  

## Current phase

| Item | State |
|------|-------|
| Manuscript relocated | ✅ [`manuscript/literature_review.md`](./manuscript/literature_review.md) |
| Informal appendix extracted | ✅ [`notes/informal_synthesis.md`](./notes/informal_synthesis.md) |
| Research folder structure | ✅ this commit |
| Bibliography seeded | ✅ [`literature/sources.bib`](./literature/sources.bib) |
| Simulation venv | ⏳ run Quick start in README locally |
| First finding doc | ⏳ pick one open question below |

## Next actions (recommended order)

1. **Literature pass** — replace placeholder bib entries with DOI-linked papers; one `notes/` file per paper.
2. **Deduplicate archive** — compare `full_draft_202607_archive.md` with `literature_review.md`; delete archive when satisfied.
3. **Finding 01** — formalize ΔT in real facades (§6.1) as [`findings/f01_facade_delta_t.md`](./findings/f01_facade_delta_t.md) using `_template.md`.
4. **Simulation 01** — Drude–Lorentz ε(ω) toy model in `simulations/` for visible vs IR bands (see `simulations/README.md`).
5. **Material shortlist** — table comparing WO₃, Bi₂Se₃, ITO+Bi₂Te₃ with sourced ZT and transmission numbers.

## Blockers

None for desk research. Lab/fabrication work not in scope until material shortlist + energy balance model exist.

## Milestones

- [ ] Phase 0 — environment + index (this bootstrap)
- [ ] Phase 1 — annotated bibliography (≥10 primary sources)
- [ ] Phase 2 — energy balance model (facade + vehicle glass)
- [ ] Phase 3 — candidate stack design (multilayer spec)
- [ ] Phase 4 — optional Pulse integration note (RF/optical stack)
