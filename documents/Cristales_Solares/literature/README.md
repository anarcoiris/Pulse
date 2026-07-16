# Literature — Cristales Solares

> **Role:** reference (bibliography)  

## Files

| File | Purpose |
|------|---------|
| [`sources.bib`](./sources.bib) | BibTeX — primary source of truth for citations |
| `notes/<author>_<year>_<topic>.md` | One note per paper (create as you read) |

## Reading workflow

1. Add BibTeX entry to `sources.bib` (DOI preferred).
2. Create `notes/<slug>.md` with: **claim**, **methods**, **numbers**, **relevance to OQ-n**.
3. Link the note from [`../index.md`](../index.md) material or theme row.
4. When a claim drives a design decision, cite it in a `findings/` doc §Resultado.

## Note template

```markdown
# Author et al. (YEAR) — short title

- **DOI:**
- **Relevance:** OQ-1 / materials / TE / …
- **Key numbers:**
- **Takeaway:**
- **Limitations:**
```

## Placeholder entries

` sources.bib` currently has **seed entries** from §8 of the literature review. Replace `@misc{...}` with proper `@article{...}` as you verify each source.
