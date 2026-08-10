import subprocess
from pathlib import Path
from core.sexp import parse

full_text = Path("output/flipper_killer_mk_ii_0.6/board.kicad_pcb").read_text(encoding="utf-8")
ast = parse(full_text)

def ast_to_sexpr(node, indent=0):
    ind = "  " * indent
    if isinstance(node, str):
        if " " in node or "(" in node or ")" in node or node == "":
            return f'"{node}"'
        return node
    elif isinstance(node, list):
        if not node:
            return "()"
        elems = [ast_to_sexpr(x, indent + 1) for x in node]
        if len(" ".join(elems)) < 80 and not any("\n" in e for e in elems):
            return f"({ ' '.join(elems) })"
        else:
            first = elems[0]
            rest = "\n".join(ind + "  " + e for e in elems[1:])
            return f"({first}\n{rest}\n{ind})"
    return str(node)

children = ast[1:]

def test_ast(child_list, label):
    new_ast = ["kicad_pcb"] + child_list
    text = ast_to_sexpr(new_ast)
    Path("test_ast.kicad_pcb").write_text(text, encoding="utf-8")
    res = subprocess.run(
        ['kicad-cli', 'pcb', 'export', 'svg', '--output', 'test_out.svg', '--layers', 'F.Cu,B.Cu,Edge.Cuts', 'test_ast.kicad_pcb'],
        capture_output=True, text=True
    )
    print(f"[{label}] Returncode: {res.returncode}")
    if res.returncode != 0:
        print("  STDERR:", res.stderr.strip())
    return res.returncode == 0

# Base minimal PCB
base = [
    ["version", "20240108"],
    ["paper", "A4"],
    ["layers", ["0", "F.Cu", "signal"], ["31", "B.Cu", "signal"], ["44", "Edge.Cuts", "user"]],
    ["net", "0", ""]
]

test_ast(base, "Bare Minimum Base")

# Add elements one by one to Bare Minimum Base
for c in children:
    if isinstance(c, list):
        tag = c[0]
        if tag in ("version", "paper", "net"): continue
        test_ast(base + [c], f"Base + single {tag}")
