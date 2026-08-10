import subprocess
from pathlib import Path
from core.sexp import parse

full_text = Path("output/flipper_killer_mk_ii_0.6/board.kicad_pcb").read_text(encoding="utf-8")
ast = parse(full_text)

def ast_to_sexpr(node):
    if isinstance(node, str):
        if " " in node or "(" in node or ")" in node or node == "":
            return f'"{node}"'
        return node
    elif isinstance(node, list):
        if not node:
            return "()"
        elems = [ast_to_sexpr(x) for x in node]
        if len(" ".join(elems)) < 80 and not any("\n" in e for e in elems):
            return f"({ ' '.join(elems) })"
        else:
            first = elems[0]
            rest = "\n".join("  " + e for e in elems[1:])
            return f"({first}\n{rest}\n)"
    return str(node)

children = ast[1:] # top level nodes
categories = {}
for c in children:
    if isinstance(c, list):
        tag = c[0]
        if tag not in categories:
            categories[tag] = []
        categories[tag].append(c)

def test(tag_list, label):
    test_children = []
    for tag in tag_list:
        if tag in categories:
            test_children.extend(categories[tag])
    text = ast_to_sexpr(["kicad_pcb"] + test_children)
    Path("test_single.kicad_pcb").write_text(text, encoding="utf-8")
    res = subprocess.run(
        ['kicad-cli', 'pcb', 'export', 'svg', '--output', 'test_out.svg', '--layers', 'F.Cu,B.Cu,Edge.Cuts', 'test_single.kicad_pcb'],
        capture_output=True, text=True
    )
    print(f"[{label}] -> Returncode: {res.returncode}")
    if res.returncode != 0:
        print("   STDERR:", res.stderr.strip())

base = ["version", "paper", "net"]
tags_to_check = ["generator", "general", "title_block", "layers", "setup", "netclass", "gr_line", "gr_arc", "gr_text"]

for tag in tags_to_check:
    test(base + [tag], f"Testing tag: {tag}")
