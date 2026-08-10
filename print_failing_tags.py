import pprint
from pathlib import Path
from core.sexp import parse

full_text = Path("output/flipper_killer_mk_ii_0.6/board.kicad_pcb").read_text(encoding="utf-8")
ast = parse(full_text)

for child in ast[1:]:
    if isinstance(child, list) and child[0] in ("layers", "netclass"):
        print(f"=== TAG: {child[0]} ===")
        pprint.pprint(child)
