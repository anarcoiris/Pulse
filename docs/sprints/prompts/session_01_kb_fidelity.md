### Session 1 — Knowledge-base fidelity fixes ✅ COMPLETED (06-jul-2026)

Outcome: `docs/calibration_forge/knowledge_base_fidelity.md` §Resultado. Do not re-run unless drift check finds regressions.

```
You are working on PulseLab Forge at C:\Users\soyko\Documents\Pulse-main.

SOURCE OF TRUTH (read these first, in full, before touching any code):
- docs/calibration_forge/knowledge_base_fidelity.md
- docs/reviews/pulselab_review_05072026.md (section 4.2 and the table in section 6)
- docs/calibration_forge/index.md (for how this fits the broader research index)

IMPORTANT — drift check: these docs were written 2026-07-05 as a snapshot of the code at
that time. Before implementing anything, re-read the actual current state of
knowledge/rag_engine.py and knowledge/kicad_schematic_parser.py and confirm the described
bugs still exist as written (line numbers may have shifted, someone may have partially
fixed it already, etc.). Treat the doc as a well-evidenced hypothesis, not gospel. If you
find the current code differs from what the doc describes, note the discrepancy and adapt
your plan — do not force a fix for a bug that's no longer there, and do not skip a bug just
because the line numbers moved.

GOAL: Improve the fidelity of what gets indexed into the RAG knowledge base, so retrieved
circuit examples actually carry design intent and schematic context instead of bare
component lists.

TASKS:
1. Fix knowledge/rag_engine.py::_summarize_circuit_data() so it reads the natural-language
   description from data["metadata"]["prompt"] (not just top-level "source"/"original_file"),
   for the self-generated training samples in knowledge/data/training/sample_*.json.
2. Extend knowledge/kicad_schematic_parser.py::KiCadSchematicParser to also capture:
   - title_block (title + comments)
   - free-floating (text "...") annotations
   - label / hierarchical_label / global_label net names
   Decide on a sensible output schema addition (e.g. a "description"/"notes" field) and
   thread it through to _summarize_circuit_data() so it actually gets indexed.
3. Determine whether the ~280 human_*.json training files under knowledge/data/training/
   can be regenerated from their original .kicad_sch sources (check knowledge/github_crawler.py
   and whether raw files are still on disk, e.g. knowledge/data/raw_kicad/) so the parser
   improvements actually apply retroactively. If raw files aren't available, document that
   as a known limitation rather than silently skipping it.
4. Rebuild the embedding index: python -m knowledge.build_embed_index
5. Run tests/test_rag_retrieval.py and knowledge/rag_engine.py's own __main__ self-test;
   confirm indexed excerpts for the RLC/RF example (or similar) now contain intent language,
   not just "etype label value".
6. Add a lightweight "description density" check to ElectronicsKnowledgeBase.stats()
   (knowledge/rag_engine.py) per the proposal in knowledge_base_fidelity.md, so this doesn't
   regress silently in the future.

HANDOFF (required before ending this session):
- Update docs/calibration_forge/knowledge_base_fidelity.md: check off / annotate which
  proposed steps you completed, and add a short "Resultado" section with what you found
  that differed from the original hypothesis (e.g. raw files missing, chunk counts before/after,
  actual retrieval quality change observed).
- Update the priority table in docs/reviews/pulselab_review_05072026.md (section 6) to mark
  these two 🔴 items as done, with a one-line pointer to the result section above.
- Update docs/calibration_forge/index.md milestone checklist accordingly.
- Explicitly flag anything that changes the starting assumptions for
  docs/calibration_forge/prompt_vs_rag_balance.md (Session 4 depends on this work) — e.g. if
  the KB improvement was smaller/larger than expected, say so there or in that doc directly.
```

---
