# Independent & External Research Tracks

> **Role:** entry / map  
> **Status:** active  
> **Source of truth for:** standalone research projects decoupled from the core PulseLab Forge EDA engine  

PulseLab Forge core documentation and sprint planning live under [`docs/`](../docs/).

---

## 📌 Inherited & Off-Topic Research Reference

| Project | Description | Remote Repository |
|---------|-------------|-------------------|
| **Cristales_Solares** | Transparent IR-absorbing thermoelectric window materials research & simulations | [anarcoiris/Cristales_Solares](https://github.com/anarcoiris/Cristales_Solares) |

> ℹ️ *Note: `Cristales_Solares` was migrated to its own dedicated repository ([anarcoiris/Cristales_Solares](https://github.com/anarcoiris/Cristales_Solares)) to isolate Python environment dependencies and keep the PulseLab Forge core repository lightweight.*

---

## Project Template Convention

For any future parallel research track created under `documents/<ProjectName>/`:

| Path | Purpose |
|------|---------|
| `README.md` | Project hub — scope, links, how to start |
| `STATUS.md` | Living state — phase, blockers, next actions |
| `index.md` | Topic map and knowledge index |
| `manuscript/` | Long-form writing (reviews, papers) |
| `literature/` | Bibliography (`sources.bib`) and reading notes |
| `notes/` | Working notes and informal synthesis |
| `findings/` | Hypothesis → evidence → §Resultado |
| `data/` | Datasets, measured values, CSV exports |
| `simulations/` | Analysis code, notebooks, project-local Python deps |
| `tools/` | One-off scripts and utilities |
