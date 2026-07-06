"""
knowledge/seed_poc_experience.py
=================================
Proof-of-concept: migrate ONE hardcoded "REGLA OBLIGATORIA" rule out of the
system prompts and into a `DesignExperience` lesson recoverable via RAG.

This is groundwork for docs/calibration_forge/prompt_vs_rag_balance.md
(proposal #3) — it does NOT remove the rule from
knowledge/circuit_synthesizer.py's base_system_prompt or
knowledge/semantic_reviewer.py's _SYSTEM_PROMPT (that trade-off is explicitly
scoped to the future "prompt vs. RAG rebalancing" session, which needs an A/B
comparison first). It only proves that:

  1. A hand-authored lesson can be persisted as a DesignExperience record.
  2. It survives a process restart (thanks to
     ElectronicsKnowledgeBase._load_experiences()).
  3. It is retrievable via kb.query(..., chunk_type="design_experience") for
     a query relevant to the rule.

Run: python -m knowledge.seed_poc_experience
Idempotent: skips seeding if the record already exists on disk.
"""
from __future__ import annotations

from knowledge.design_experience import DesignExperience, _EXPERIENCES_DIR
from knowledge.rag_engine import ElectronicsKnowledgeBase

POC_BOARD_ID = "poc_esp32_en_pullup_rule"

# Migrated verbatim from:
#   - knowledge/circuit_synthesizer.py base_system_prompt, "REGLAS UART / USB (OBLIGATORIAS)"
#   - knowledge/semantic_reviewer.py _SYSTEM_PROMPT, rule #5
POC_LESSON = (
    "ESP32 EN pin requires a 10k pull-up resistor to 3.3V for reliable boot; "
    "without it the board may fail to leave reset. GPIO0 (BOOT) must also be "
    "able to reach GND to enter flash mode."
)


def seed() -> DesignExperience:
    existing = _EXPERIENCES_DIR / f"{POC_BOARD_ID}.json"
    if existing.exists():
        print(f"POC experience already seeded: {existing}")
        return DesignExperience.from_file(existing)

    exp = DesignExperience(
        board_id=POC_BOARD_ID,
        timestamp="2026-07-06T00:00:00+00:00",
        mcu="ESP32",
        lessons_learned=[POC_LESSON],
        passed=True,
        drc_violations=0,
    )
    path = exp.save()
    n_ingested = exp.ingest_to_rag()
    print(f"Seeded {path} ({n_ingested} chunk(s) ingested into the throwaway KB instance)")
    return exp


def verify_retrieval() -> None:
    """Confirm the lesson survives a fresh (new-process-like) KB instance."""
    kb = ElectronicsKnowledgeBase()
    results = kb.query("ESP32 EN pin boot reset pull-up", top_k=5, chunk_type="design_experience")
    found = any(POC_BOARD_ID in r.get("source", "") for r in results)
    print(f"design_experience chunks in fresh KB: {kb.stats()['by_type'].get('design_experience', 0)}")
    print(f"Retrieval check for '{POC_BOARD_ID}': {'FOUND' if found else 'NOT FOUND'}")
    for r in results:
        print(f"  - {r.get('source')}: {r.get('excerpt', '')[:100]}")
    assert found, "POC lesson not retrievable from a fresh KB instance — persistence fix regressed."


if __name__ == "__main__":
    seed()
    verify_retrieval()
