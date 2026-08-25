"""
Minimal, dependency-free S-expression parser/tokenizer for KiCad .kicad_pcb files.

KiCad's format is a Lisp-like s-expression:
    (footprint "Name" (layer "F.Cu") (pad "1" thru_hole rect (at 0 0) ...))

We parse into nested Python lists, where:
    - atoms are strings (numbers stay as strings; caller converts as needed)
    - quoted strings keep their content (quotes stripped)
    - lists are Python lists

This is intentionally generic (no KiCad-specific schema baked in) so it stays
robust across KiCad versions / generator quirks.
"""
from __future__ import annotations
import re
from typing import Any, Iterator, List, Union

Node = Union[str, List["Node"]]

_TOKEN_RE = re.compile(
    r'''
      \s+                       # whitespace (skip)
    | "(?:[^"\\]|\\.)*"         # quoted string (handles escaped quotes)
    | \(                        # open paren
    | \)                        # close paren
    | [^\s()"]+                 # bare atom
    ''',
    re.VERBOSE,
)


def tokenize(text: str) -> Iterator[str]:
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok.strip() == "":
            continue
        yield tok


def parse(text: str) -> Node:
    """Parse the full file text; returns the single top-level node."""
    tokens = list(tokenize(text))
    if not tokens:
        return []
    pos = 0

    def _unquote(tok: str) -> str:
        if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
            inner = tok[1:-1]
            return inner.replace('\\"', '"').replace('\\\\', '\\')
        return tok

    def _parse_expr(i: int):
        if i >= len(tokens):
            raise SyntaxError("Unexpected end of input while parsing S-expression")
        tok = tokens[i]
        if tok == "(":
            lst: List[Node] = []
            i += 1
            while i < len(tokens) and tokens[i] != ")":
                node, i = _parse_expr(i)
                lst.append(node)
            if i >= len(tokens):
                raise SyntaxError("Unclosed parenthesis in S-expression")
            return lst, i + 1
        elif tok == ")":
            raise SyntaxError(f"Unexpected ')' at token {i}")
        else:
            return _unquote(tok), i + 1

    node, pos = _parse_expr(pos)
    if pos != len(tokens):
        # Multiple top-level forms is not expected for kicad_pcb, but tolerate.
        pass
    return node


def find_all(node: Node, tag: str) -> List[List[Node]]:
    """Recursively find every list node whose first element equals `tag`."""
    results: List[List[Node]] = []
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0] == tag:
            results.append(node)
        for child in node:
            results.extend(find_all(child, tag))
    return results


def find_direct(node: List[Node], tag: str) -> List[List[Node]]:
    """Find immediate children of `node` whose first element equals `tag`
    (does not recurse into grandchildren). node must be a list."""
    out = []
    for child in node:
        if isinstance(child, list) and child and isinstance(child[0], str) and child[0] == tag:
            out.append(child)
    return out


def first_direct(node: List[Node], tag: str) -> Union[List[Node], None]:
    r = find_direct(node, tag)
    return r[0] if r else None


def as_text(node: Node) -> str:
    """Render a node back to s-expression text (for diffs / debugging)."""
    if isinstance(node, str):
        if node == "" or re.search(r'[\s()"]', node):
            escaped = node.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        return node
    return "(" + " ".join(as_text(c) for c in node) + ")"
