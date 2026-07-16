# Independent research projects

> **Role:** entry / map  
> **Status:** active  
> **Source of truth for:** self-contained research tracks separate from PulseLab Forge product docs  

Pulse Forge lives under [`docs/`](../docs/). **This folder** holds parallel research and manuscript work that may later connect to Pulse (e.g. RF materials, simulation) but does not share Forge sprint status or Calibration Forge session numbering.

## Active projects

| Project | Topic | Entry |
|---------|-------|-------|
| **Cristales_Solares** | Transparent IR-absorbing thermoelectric window materials | [`Cristales_Solares/README.md`](./Cristales_Solares/README.md) |

## Conventions

Each project under `documents/<ProjectName>/` follows the same layout:

| Path | Purpose |
|------|---------|
| `README.md` | Project hub — scope, links, how to start |
| `STATUS.md` | Living state — phase, blockers, next actions |
| `index.md` | Topic map and knowledge index |
| `manuscript/` | Long-form writing (reviews, papers) |
| `literature/` | Bibliography (`sources.bib`) and reading notes |
| `notes/` | Working notes and informal synthesis |
| `findings/` | Hypothesis → evidence → **§Resultado** (same discipline as Calibration Forge) |
| `data/` | Datasets, measured values, CSV exports |
| `simulations/` | Analysis code, notebooks, project-local Python deps |
| `tools/` | One-off scripts and utilities |

## Adding a new project

```powershell
mkdir documents\NewProject\{manuscript,literature,notes,findings,data,simulations,tools}
# Copy STATUS.md and index.md templates from Cristales_Solares and adapt.
```

Link the new project from this file and optionally from [`docs/README.md`](../docs/README.md) under a **Research (external)** row.
