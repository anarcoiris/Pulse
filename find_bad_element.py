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

def test_ast(child_list):
    text = ast_to_sexpr(["kicad_pcb"] + child_list)
    Path("test_find.kicad_pcb").write_text(text, encoding="utf-8")
    res = subprocess.run(
        ['kicad-cli', 'pcb', 'export', 'svg', '--output', 'test_out.svg', '--layers', 'F.Cu,B.Cu,Edge.Cuts', 'test_find.kicad_pcb'],
        capture_output=True, text=True
    )
    return res.returncode == 0

print("Full board AST test:", test_ast(children))

# Test removing each top-level node individually
bad_nodes = []
for i, child in enumerate(children):
    if isinstance(child, list):
        tag = child[0]
        # Copy without this node
        test_nodes = children[:i] + children[i+1:]
        if test_ast(test_nodes):
            print(f"--> FIX SUCCESS: Removing node {i} (tag: {tag}) fixed the PCB load error!")
            bad_nodes.append((i, tag, child))

if not bad_nodes:
    print("Removing single top-level nodes did not fix it. Multiple nodes involved.")
