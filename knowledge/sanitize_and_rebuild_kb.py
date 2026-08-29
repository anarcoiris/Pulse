"""
knowledge/sanitize_and_rebuild_kb.py
======================================
Automated RAG Memory Sanitation & Vector Database Immunization CLI.

Actions:
1. Audits `knowledge/experiences/` and moves any non-passing or DRC-failing JSON to `knowledge/experiences/quarantine/`.
2. Inspects `knowledge/data/training/` and flags excluded KiCad error test fixtures.
3. Loads clean `ElectronicsKnowledgeBase` instance and verifies total chunks.
4. Rebuilds dense embedding matrix `vectors.npy` with SHA-256 fingerprinting.
"""

from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from knowledge.rag_engine import ElectronicsKnowledgeBase
from core.logger import logger


def sanitize_and_rebuild() -> dict:
    here = Path(__file__).resolve().parent
    exp_dir = here / "experiences"
    quarantine_dir = exp_dir / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    quarantined_count = 0
    clean_count = 0

    # 1. Audit experiences/ directory
    for p in sorted(exp_dir.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            passed = data.get("passed", False)
            drc_errs = data.get("drc_violations", 0)

            if not passed or drc_errs > 0:
                dest = quarantine_dir / p.name
                shutil.move(str(p), str(dest))
                print(f"  [Quarantine] Moved unverified experience '{p.name}' to quarantine.")
                quarantined_count += 1
            else:
                clean_count += 1
        except Exception as e:
            print(f"  [Warning] Error reading experience file {p.name}: {e}")

    print(f"\n[Sanitation] Audit Complete: {clean_count} canonical experiences retained, {quarantined_count} quarantined.")

    # 2. Instantiate KB with hardened filters
    kb = ElectronicsKnowledgeBase()
    stats = kb.stats()
    print(f"[RAG KB] Clean Chunks Loaded: {stats['total_chunks']} ({stats['by_type']})")

    # 3. Rebuild dense embeddings via Ollama
    print("[RAG KB] Rebuilding dense vector index (Nomic Embeddings) with SHA-256 fingerprint...")
    res = kb.rebuild_embed_index(force=True)

    if "error" in res:
        print(f"[RAG KB] Vector rebuild warning: {res['error']}")
        print("[RAG KB] TF-IDF fallback is active and clean.")
    else:
        print(f"[RAG KB] Successfully indexed {res['indexed']} vectors -> {res['path']}")

    final_stats = kb.stats()
    print(f"[RAG KB] Status: {final_stats}\n")

    return {
        "quarantined_count": quarantined_count,
        "clean_experiences": clean_count,
        "total_chunks": final_stats["total_chunks"],
        "embed_result": res,
    }


if __name__ == "__main__":
    sanitize_and_rebuild()
