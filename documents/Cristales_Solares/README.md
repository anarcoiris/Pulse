# Cristales Solares — transparent thermoelectric window research

> **Role:** entry (research hub)  
> **Status:** active — project bootstrap  
> **Author:** Santiago Javier Espino Heredero  
> **Started:** July 2026  
> **See also:** [`STATUS.md`](./STATUS.md) · [`index.md`](./index.md) · [`glossary.md`](./glossary.md)

## Research question

Can we design **window-grade materials** that are:

1. **Transparent** in the visible band (400–700 nm),
2. **Absorbent** in the infrared (building thermal / solar IR),
3. **Thermoelectrically active** (Seebeck → usable power at modest ΔT)?

Primary manuscript: [`manuscript/literature_review.md`](./manuscript/literature_review.md).

## Quick start

```powershell
cd C:\Users\soyko\Documents\Pulse-main\documents\Cristales_Solares\simulations
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter lab   # optional — install jupyter separately if desired
```

Read [`STATUS.md`](./STATUS.md) for the current phase and next actions. Use [`AGENTS.md`](./AGENTS.md) when working with Cursor Agent on this project.

## Repository layout

```
Cristales_Solares/
  README.md              ← you are here
  STATUS.md              ← living sprint for this project
  index.md               ← knowledge map (topics ↔ files)
  glossary.md            ← terms and symbols
  open_questions.md      ← research backlog
  AGENTS.md              ← agent / collaborator context
  manuscript/
    literature_review.md ← canonical long-form review (cleaned)
    full_draft_202607_archive.md  ← original export (duplicates + chat UI tail)
  literature/
    sources.bib          ← bibliography (expand as you read)
    README.md
  notes/
    informal_synthesis.md
    _template.md
  findings/
    _template.md
  data/                  ← CSV, measured ε, ZT tables
  simulations/           ← Python analysis env
  tools/                 ← helper scripts
```

## Relationship to PulseLab Forge

This project is **materials / photonics / TE physics**, not PCB LLM pipeline work. Possible future bridges:

- Import selected **design rules** or **component models** if RF/optical stacks enter Pulse Phase 5 (HV/RF).
- Reuse Forge **documentation discipline** (findings with §Resultado, STATUS refresh).

No dependency on `knowledge/rag_engine.py` or Ollama for core research.

## Key metrics (targets from literature review)

| Metric | Visible target | IR / TE target |
|--------|----------------|----------------|
| ε′ (visible) | 1–4 | — |
| ε″ (visible) | < 0.1 | — |
| ε′ (IR) | — | 4–6 |
| ε″ (IR) | — | 0.5–3 |
| Visible transmission | > 80 % | — |
| Power density (TE, solar) | — | ~10–50 W/m² (thin-film prototypes) |
| ZT (nano composites) | — | 0.3–0.6 reported |
