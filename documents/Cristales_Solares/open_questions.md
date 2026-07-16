# Open questions — Cristales Solares

> **Role:** backlog  
> Promote to `findings/fNN_*.md` when investigated.

## OQ-1 — Facade ΔT under real HVAC

**Question:** What steady-state ΔT is achievable across a window film in a occupied building (not just concentrated sun)?

**Why it matters:** Seebeck output scales with ΔT; §6.1 identifies this as the main limiter.

**Next step:** Energy balance sketch — solar input, interior convection, U-value of glass stack. → Finding `f01_facade_delta_t`.

---

## OQ-2 — Cost / area scalability

**Question:** Which candidate materials (WO₃, Bi₂Se₃, ITO+Bi₂Te₃) have a credible path to m²-scale deposition?

**Next step:** Literature + industry datasheets; table in `data/material_candidates.csv`.

---

## OQ-3 — Transparency vs TE efficiency Pareto front

**Question:** Is there a measured Pareto curve (transmission % vs W/m²) for ultrathin TE on glass?

**Next step:** Extract from §5 references once bib is populated.

---

## OQ-4 — Hybrid PV + TE stacking order

**Question:** Optimal layer order for narrow-band PV + IR-absorbing TE + glass substrate?

**Next step:** Optical transfer matrix model in `simulations/`.

---

## OQ-5 — Vehicle regulatory / aesthetic constraints

**Question:** How do automotive glazing rules constrain visible transmission and tint?

**Next step:** Separate note in `notes/` — out of scope until building case is modeled.

---

## OQ-6 — Connection to Pulse RF / HV roadmap

**Question:** If Pulse Phase 5 adds RF keep-out and specialized stacks, does this research inform material ε(ω) models?

**Next step:** One-page bridge note after Phase 2 simulation exists.
