#!/usr/bin/env python3
"""
sch_pcb_crosscheck.py — Compare a .kicad_sch against a .kicad_pcb to find:

  (a) Reference designators present on the PCB but absent from the
      schematic (components that were never actually designed — placed
      directly in the PCB editor).
  (b) Net names that appear as schematic labels but never appear in the
      PCB's net table (dead net names in the schematic, or naming
      mismatches).
  (c) Net names in the PCB net table that never appear as a schematic
      label anywhere (nets invented purely at PCB level).
  (d) A structural check of the schematic's lib_symbols cache: does each
      symbol definition actually contain (pin ...) sub-elements? A
      schematic symbol with ZERO pins cannot carry real electrical
      connectivity regardless of how many wires/labels surround it —
      this is checked BEFORE trusting any label-based net inference.

This is intentionally a coverage/diff tool, not a full ERC (Electrical
Rules Check) — KiCad's own ERC needs real pin geometry, which (d) may
reveal is entirely absent.
"""
from __future__ import annotations
import argparse
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from core.sexp import parse, find_all, find_direct, first_direct, Node


def load(path: str) -> Node:
    with open(path, "r", encoding="utf-8") as f:
        return parse(f.read())


# --------------------------------------------------------------------------
# Schematic extraction
# --------------------------------------------------------------------------

def sch_lib_symbol_pin_counts(root: Node) -> Dict[str, int]:
    """For each lib_symbols entry, count (pin ...) occurrences anywhere
    inside it (including nested unit sub-symbols and extends references)."""
    counts = {}
    extends_map = {}
    lib_symbols = first_direct(root, "lib_symbols")
    if not lib_symbols:
        return counts
    for sym in find_direct(lib_symbols, "symbol"):
        name = sym[1] if len(sym) > 1 else "?"
        pins = find_all(sym, "pin")
        counts[name] = len(pins)
        ext_node = first_direct(sym, "extends")
        if ext_node and len(ext_node) > 1:
            extends_map[name] = ext_node[1]

    # Resolve inherited pin count for symbols using extends
    for child, parent in extends_map.items():
        if counts.get(child, 0) == 0 and parent in counts:
            counts[child] = counts[parent]

    return counts



def sch_symbols(root: Node) -> List[Dict]:
    """Top-level placed symbol instances (not the lib_symbols cache)."""
    out = []
    for sym in find_direct(root, "symbol"):
        lib_id_node = first_direct(sym, "lib_id")
        lib_id = lib_id_node[1] if lib_id_node else "?"
        at_node = first_direct(sym, "at")
        at = (float(at_node[1]), float(at_node[2])) if at_node else (0.0, 0.0)
        ref = "?"
        value = "?"
        for prop in find_direct(sym, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                ref = prop[2]
            elif len(prop) >= 3 and prop[1] == "Value":
                value = prop[2]
        out.append({"ref": ref, "value": value, "lib_id": lib_id, "at": at})
    return out


def sch_labels(root: Node) -> List[Dict]:
    out = []
    for lbl in find_direct(root, "label"):
        name = lbl[1] if len(lbl) > 1 else "?"
        at_node = first_direct(lbl, "at")
        at = (float(at_node[1]), float(at_node[2])) if at_node else (0.0, 0.0)
        out.append({"name": name, "at": at})
    return out


def sch_wires(root: Node) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    out = []
    for w in find_direct(root, "wire"):
        pts = first_direct(w, "pts")
        if not pts:
            continue
        xy_nodes = find_direct(pts, "xy")
        if len(xy_nodes) < 2:
            continue
        p1 = (float(xy_nodes[0][1]), float(xy_nodes[0][2]))
        p2 = (float(xy_nodes[1][1]), float(xy_nodes[1][2]))
        out.append((p1, p2))
    return out


# --------------------------------------------------------------------------
# PCB extraction (reuse kicad_audit's BoardContext for consistency)
# --------------------------------------------------------------------------

from core.kicad_audit import BoardContext  # noqa: E402


# --------------------------------------------------------------------------
# Cross-check logic
# --------------------------------------------------------------------------

def run_crosscheck(sch_path: str, pcb_path: str) -> None:
    sch_root = load(sch_path)
    pcb_ctx = BoardContext(pcb_path)

    print("=" * 78)
    print("STRUCTURAL CHECK — do schematic symbols have real pins?")
    print("=" * 78)
    pin_counts = sch_lib_symbol_pin_counts(sch_root)
    if not pin_counts:
        print("No (lib_symbols ...) block found — cannot assess.")
    else:
        any_pins = False
        for name, count in pin_counts.items():
            flag = "OK" if count > 0 else "*** ZERO PINS ***"
            if count > 0:
                any_pins = True
            print(f"  {name:55s} pins={count:<3d} {flag}")
        if not any_pins:
            print()
            print("  >>> CRITICAL: every symbol definition in this schematic has")
            print("  >>> ZERO (pin ...) sub-elements. This means NO symbol in this")
            print("  >>> file carries real electrical connectivity — wires and")
            print("  >>> labels may be drawn to look connected, but there are no")
            print("  >>> pins for them to actually attach to. Any netlist derived")
            print("  >>> from this schematic (via ERC, 'Update PCB from Schematic',")
            print("  >>> or ratsnest generation) will be empty or wrong regardless")
            print("  >>> of wire/label placement. This is the most likely root")
            print("  >>> cause of the PCB-side netlist/routing issues found earlier.")
    print()

    print("=" * 78)
    print("REFERENCE DESIGNATOR COVERAGE — schematic vs PCB")
    print("=" * 78)
    sch_syms = sch_symbols(sch_root)
    sch_refs = {s["ref"] for s in sch_syms}
    pcb_refs = {fp.reference for fp in pcb_ctx.footprints}

    only_pcb = sorted(pcb_refs - sch_refs)
    only_sch = sorted(sch_refs - pcb_refs)
    both = sorted(sch_refs & pcb_refs)

    print(f"In schematic: {len(sch_refs)} refs   In PCB: {len(pcb_refs)} refs   "
          f"In both: {len(both)}")
    print()
    if only_pcb:
        print(f"Present in PCB but MISSING from schematic ({len(only_pcb)}):")
        for r in only_pcb:
            fp = next(f for f in pcb_ctx.footprints if f.reference == r)
            print(f"  - {r:15s} ({fp.value}, {fp.library_id})")
        print()
    if only_sch:
        print(f"Present in schematic but MISSING from PCB ({len(only_sch)}):")
        for r in only_sch:
            print(f"  - {r}")
        print()

    print("=" * 78)
    print("NET NAME COVERAGE — schematic labels vs PCB net table")
    print("=" * 78)
    sch_label_names = {l["name"] for l in sch_labels(sch_root)}
    pcb_net_names = {name for name in pcb_ctx.nets.values() if name}

    only_pcb_nets = sorted(pcb_net_names - sch_label_names)
    only_sch_labels = sorted(sch_label_names - pcb_net_names)
    both_nets = sorted(sch_label_names & pcb_net_names)

    print(f"Schematic label names: {len(sch_label_names)}   "
          f"PCB net table names: {len(pcb_net_names)}   Common: {len(both_nets)}")
    print()
    if only_pcb_nets:
        print(f"Net names in PCB with NO matching schematic label ({len(only_pcb_nets)}):")
        for n in only_pcb_nets:
            print(f"  - {n}")
        print()
    if only_sch_labels:
        print(f"Schematic labels with NO matching PCB net name ({len(only_sch_labels)}):")
        for n in only_sch_labels:
            print(f"  - {n}")
        print()

    print("=" * 78)
    print("LABEL FREQUENCY IN SCHEMATIC (how many times each net name is labeled)")
    print("=" * 78)
    freq = defaultdict(int)
    for l in sch_labels(sch_root):
        freq[l["name"]] += 1
    for name, count in sorted(freq.items(), key=lambda kv: -kv[1]):
        note = ""
        if count == 1:
            note = "  <-- appears only ONCE: a net label needs >=2 occurrences to join two points"
        print(f"  {name:20s} x{count}{note}")

    print()
    print("=" * 78)
    print("COMPONENTS WITH NO SCHEMATIC WIRES NEAR THEM (heuristic)")
    print("=" * 78)
    print("(Approximate: checks if ANY wire endpoint falls within 6mm of the")
    print(" symbol's placement coordinate. Since this schematic's symbols have")
    print(" no real pin geometry, this is a rough proxy, not a precise check.)")
    wires = sch_wires(sch_root)
    for s in sch_syms:
        sx, sy = s["at"]
        near = False
        for p1, p2 in wires:
            for (wx, wy) in (p1, p2):
                if abs(wx - sx) < 6.0 and abs(wy - sy) < 6.0:
                    near = True
                    break
            if near:
                break
        if not near:
            print(f"  - {s['ref']:12s} ({s['value']}) at {s['at']} — no nearby wire found")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("schematic", help="Path to .kicad_sch")
    ap.add_argument("pcb", help="Path to .kicad_pcb")
    args = ap.parse_args()
    run_crosscheck(args.schematic, args.pcb)


if __name__ == "__main__":
    main()
