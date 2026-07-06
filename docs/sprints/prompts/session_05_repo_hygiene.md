### Session 5 — Repo hygiene

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

SOURCE OF TRUTH (read this first):
- docs/reviews/pulselab_review_05072026.md (section 5, "Otros puntos menores observados")

IMPORTANT — drift check: this is the lowest-risk session but still verify each item is
still true before acting (e.g. confirm scratch/test_drc_fail.py still exists and is still
unreferenced elsewhere before deleting it).

GOAL: Clean up low-risk technical debt that doesn't block any of the other research
sessions, and can be done independently/at any point in the sequence.

TASKS:
1. Pin dependency versions in requirements.txt (pygame, numpy, scikit-learn, mcp, fastmcp,
   skidl, schemdraw, matplotlib, pytest, openai, python-dotenv, peft, trl, bitsandbytes,
   datasets). Pick versions matching what's actually installed/tested in this environment
   where possible; run the test suite (tests/test_forge.py etc.) after pinning to confirm
   nothing broke, per docs/architecture/SEGURIDAD_DEPENDENCIAS.md's warning about numpy/
   pygame major-version regressions.
2. Confirm scratch/test_drc_fail.py is not imported/referenced anywhere else, then remove it
   (or move it under a clearly-named legacy/scratch location that's gitignored, if the team
   prefers keeping it locally rather than deleting).
3. Reconcile the duplicate architecture docs: docs/Architecture.md +
   docs/Architecture_violations.md (root) vs. docs/architecture/APP_ARCHITECTURE.md +
   docs/architecture/ARCHITECTURE_VIOLATIONS.md (subfolder). Diff their content, merge
   anything from the root versions that's missing from the subfolder versions (e.g. the
   autorouter A* description), and turn the root-level files into short stubs pointing to
   the subfolder versions (don't just delete them without a pointer, in case anything links
   to the old paths).
4. Optional if time permits: add a minimal .github/workflows/ci.yml that runs
   tests/test_forge.py and tests/test_rag_retrieval.py on push/PR (a draft already exists in
   docs/reviews/pulselab_review_23042026.md section 5.6 as a starting point, though verify it
   still matches current test file locations/needs before reusing it verbatim).

HANDOFF (required before ending this session):
- Update docs/reviews/pulselab_review_05072026.md section 5 to mark these items resolved.
- Update docs/roadmap.md if any of this closes an item tracked there (e.g. CI/CD).
- If you merged the architecture docs, update any cross-links in docs/roadmap.md,
  docs/calibration_forge/index.md, or README.md that pointed at the old locations.
```

---

One practical suggestion: after each session finishes, skim the "HANDOFF" edits it made to the docs before pasting the next prompt — that's the whole point of the protocol, and it's a cheap way to catch drift before it compounds across six sessions.
