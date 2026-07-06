"""
Build or refresh the dense embedding index for the electronics KB.
Requires Ollama with PULSE_EMBED_MODEL pulled (default: nomic-embed-text).

Usage:
    python -m knowledge.build_embed_index
"""

from __future__ import annotations

from knowledge.rag_engine import ElectronicsKnowledgeBase


def main() -> None:
    kb = ElectronicsKnowledgeBase()
    stats = kb.stats()
    print(f"Chunks loaded: {stats['total_chunks']} ({stats['by_type']})")
    result = kb.rebuild_embed_index(force=True)
    if "error" in result:
        print(f"ERROR: {result['error']}")
        print("TF-IDF RAG still works; run again when Ollama embed model is available.")
        return
    print(f"Indexed {result['indexed']} vectors -> {result['path']}")
    print("Updated stats:", kb.stats())


if __name__ == "__main__":
    main()
