import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from knowledge.rag_engine import ElectronicsKnowledgeBase

kb = ElectronicsKnowledgeBase()
queries = [
    "microSD Hirose DM3AT pad rotation DRC",
    "ground copper zones KiCad 10 clearance",
    "Flipper Zero 18 pin canonical GPIO CC1101 NRF24",
]

print("=== TESTING RAG RETRIEVAL OF INGESTED EXPERIENCES ===")
for q in queries:
    results = kb.query(q, top_k=2)
    print(f"\nQuery: '{q}'")
    print(f"Results found: {len(results)}")
    for r in results:
        txt = r.get('text', '')[:140].replace('\n', ' ')
        src = r.get('source', '')
        t = r.get('type', '')
        print(f"  - [{t} | {src}] {txt}...")
