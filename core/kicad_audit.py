#!/usr/bin/env python3
"""
kicad_audit.py — Structural / electrical sanity checks for .kicad_pcb files.

Usage:
    python3 kicad_audit.py path/to/board.kicad_pcb [--json out.json] [--rule R001,R004,...]

This tool does NOT re-implement KiCad's DRC (track clearance, courtyard overlap,
etc.) — that requires the geometry engine. Instead it targets the class of
netlist-integrity and footprint-integrity issues that DRC often reports
confusingly or misses entirely:

    - pads with duplicate numbers within one footprint
    - pads with no net assigned (excluding intentionally unconnected pads
      like mounting holes, test points explicitly named, NC pins)
    - single-pin nets (dead stubs / vias with no other endpoint)
    - nets that "should" be electrically joined but aren't (heuristic, see R010)
    - decoupling caps whose two pads land on the same net (shorted cap)
    - footprints with pad count that doesn't match their declared package
      family for a small known set of patterns (SOT-223, common headers)
    - vias/segments referencing a net number not declared in (net ...) table
    - reference designator anomalies (duplicates, gaps suggesting deleted parts)

Every check is tagged with a rule ID (R0xx) that is documented in
RULES.md alongside remediation steps, so findings can be worked through
systematically.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from sexp import parse, find_all, find_direct, first_direct, Node


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Pad:
    number: str
    pad_type: str            # thru_hole, smd, np_thru_hole
    shape: str                # rect, circle, roundrect, ...
    net_id: Optional[int]
    net_name: Optional[str]
    layers: List[str]
    at: Tuple[float, float]


@dataclass
class Footprint:
    library_id: str
    reference: str
    value: str
    at: Tuple[float, float]
    layer: str
    pads: List[Pad] = field(default_factory=list)


@dataclass
class Finding:
    rule: str
    severity: str   # "error" | "warning" | "info"
    message: str
    location: str = ""   # human-readable pointer (ref/pad/net)


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _get_num_pair(at_node: List[Node]) -> Tuple[float, float]:
    # (at X Y [angle])
    x = float(at_node[1])
    y = float(at_node[2])
    return (x, y)


def extract_nets(root: Node) -> Dict[int, str]:
    """Extract ONLY the top-level (net <id> "<name>") declarations.

    IMPORTANT: (net ...) also appears nested inside (pad ...) blocks to
    reference which net a pad belongs to, e.g. (net 8 "GND") inside a pad,
    or bare (net 1) with no name. Those share the same tag "net" so a naive
    recursive find_all() would wrongly merge pad-level net references into
    the net *declaration* table, silently corrupting names (or blanking
    them) for nets whose id happens to match a pad's net id.

    We therefore only look at the root's DIRECT children.
    """
    nets = {}
    root_list = root if isinstance(root, list) else [root]
    for n in find_direct(root_list, "net"):
        # (net <id> "<name>")
        net_id = int(n[1])
        net_name = n[2] if len(n) > 2 else ""
        nets[net_id] = net_name
    return nets


def extract_footprints(root: Node) -> List[Footprint]:
    fps = []
    for fp_node in find_direct(root if isinstance(root, list) else [root], "footprint"):
        lib_id = fp_node[1] if len(fp_node) > 1 and isinstance(fp_node[1], str) else "?"
        ref = "?"
        value = "?"
        for prop in find_direct(fp_node, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                ref = prop[2]
            elif len(prop) >= 3 and prop[1] == "Value":
                value = prop[2]
        at_node = first_direct(fp_node, "at")
        at = _get_num_pair(at_node) if at_node else (0.0, 0.0)
        layer_node = first_direct(fp_node, "layer")
        layer = layer_node[1] if layer_node else "?"

        pads: List[Pad] = []
        for pad_node in find_direct(fp_node, "pad"):
            # (pad "<num>" <type> <shape> (at x y [ang]) (size ..) ...
            #      (layers ...) (net <id> "<name>") ...)
            number = pad_node[1] if len(pad_node) > 1 else ""
            pad_type = pad_node[2] if len(pad_node) > 2 else "?"
            shape = pad_node[3] if len(pad_node) > 3 else "?"
            pad_at_node = first_direct(pad_node, "at")
            pad_at = _get_num_pair(pad_at_node) if pad_at_node else (0.0, 0.0)
            layers_node = first_direct(pad_node, "layers")
            layers = layers_node[1:] if layers_node else []
            net_node = first_direct(pad_node, "net")
            net_id = int(net_node[1]) if net_node else None
            net_name = net_node[2] if net_node and len(net_node) > 2 else None
            pads.append(Pad(number, pad_type, shape, net_id, net_name, layers, pad_at))

        fps.append(Footprint(lib_id, ref, value, at, layer, pads))
    return fps


def extract_via_nets(root: Node) -> List[int]:
    out = []
    for v in find_all(root, "via"):
        net_node = first_direct(v, "net")
        if net_node:
            out.append(int(net_node[1]))
    return out


def extract_segment_nets(root: Node) -> List[int]:
    out = []
    for s in find_all(root, "segment"):
        net_node = first_direct(s, "net")
        if net_node:
            out.append(int(net_node[1]))
    return out


def extract_zones(root: Node) -> List[Tuple[List[str], bool]]:
    """Extract top-level zones: returns list of (layers_list, is_keepout_bool)."""
    zones = []
    root_list = root if isinstance(root, list) else [root]
    for z in find_direct(root_list, "zone"):
        keepout_node = first_direct(z, "keepout")
        is_keepout = keepout_node is not None
        layers_node = first_direct(z, "layers")
        layers: List[str] = []
        if layers_node and len(layers_node) > 1:
            for item in layers_node[1:]:
                if isinstance(item, str):
                    layers.append(item)
        layer_single = first_direct(z, "layer")
        if layer_single and len(layer_single) > 1 and isinstance(layer_single[1], str):
            layers.append(layer_single[1])
        zones.append((layers, is_keepout))
    return zones


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------
# Each rule function takes the parsed board context and returns Finding list.
# Rule IDs are stable identifiers referenced in RULES.md.

class BoardContext:
    def __init__(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self.root = parse(text)
        self.nets = extract_nets(self.root)
        self.footprints = extract_footprints(self.root)
        self.via_nets = extract_via_nets(self.root)
        self.segment_nets = extract_segment_nets(self.root)
        self.zones = extract_zones(self.root)

        # net_id -> set of (ref, pad_number) endpoints from footprint pads
        self.net_pad_endpoints: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        for fp in self.footprints:
            for pad in fp.pads:
                if pad.net_id is not None:
                    self.net_pad_endpoints[pad.net_id].append((fp.reference, pad.number))


KNOWN_UNCONNECTED_HINTS = {"NC", "N/C", "NOCONNECT", "DNC"}


def rule_R001_duplicate_pad_numbers(ctx: BoardContext) -> List[Finding]:
    """R001: A footprint must not have two pads sharing the same pad number
    UNLESS it is a legitimate multi-drill jumper pad (rare) — flag always,
    let the reviewer confirm intent."""
    findings = []
    for fp in ctx.footprints:
        seen = defaultdict(list)
        for pad in fp.pads:
            seen[pad.number].append(pad)
        for num, plist in seen.items():
            if len(plist) > 1:
                positions = ", ".join(f"({p.at[0]:.2f},{p.at[1]:.2f})" for p in plist)
                findings.append(Finding(
                    rule="R001", severity="error",
                    message=(f"Duplicate pad number '{num}' appears {len(plist)}x "
                             f"in footprint. Positions: {positions}. This is invalid "
                             f"unless intentionally jumpered pads with identical function."),
                    location=f"{fp.reference} ({fp.library_id})",
                ))
    return findings


def rule_R002_unassigned_pads(ctx: BoardContext) -> List[Finding]:
    """R002: SMD/thru-hole pads with no net at all. Mounting holes and pads
    whose number is empty ("") are expected to be netless and are skipped."""
    findings = []
    for fp in ctx.footprints:
        is_mounting = "mountinghole" in fp.library_id.lower()
        for pad in fp.pads:
            if pad.net_id is None:
                if is_mounting or pad.number == "":
                    continue  # expected: mechanical / unnumbered pad
                findings.append(Finding(
                    rule="R002", severity="error",
                    message=(f"Pad '{pad.number}' has no net assigned at all "
                             f"(missing (net ...) clause). If this pin should carry "
                             f"power/signal, the schematic<->PCB netlist is out of sync."),
                    location=f"{fp.reference} pad {pad.number}",
                ))
    return findings


def rule_R003_single_pin_nets(ctx: BoardContext) -> List[Finding]:
    """R003: A net that only touches ONE footprint pad is a dead net —
    either a stub that never reaches its destination, or a net that should
    have been merged with another (see R010)."""
    findings = []
    for net_id, endpoints in ctx.net_pad_endpoints.items():
        if len(endpoints) == 1 and net_id != 0:
            net_name = ctx.nets.get(net_id, f"<net {net_id}>")
            ref, pad = endpoints[0]
            findings.append(Finding(
                rule="R003", severity="warning",
                message=(f"Net '{net_name}' (id {net_id}) connects to only ONE "
                          f"footprint pad ({ref} pad {pad}). A net needs >=2 endpoints "
                          f"to serve a purpose; routing exists but goes nowhere."),
                location=net_name,
            ))
    return findings


def rule_R004_routed_but_no_pads(ctx: BoardContext) -> List[Finding]:
    """R004: Net has copper (segments/vias) but ZERO footprint pads reference
    it. This is the classic 'traces drawn to a component that was never
    actually wired in the netlist' bug."""
    findings = []
    routed_nets = set(ctx.via_nets) | set(ctx.segment_nets)
    for net_id in routed_nets:
        if net_id == 0:
            continue
        if net_id not in ctx.net_pad_endpoints or len(ctx.net_pad_endpoints[net_id]) == 0:
            net_name = ctx.nets.get(net_id, f"<net {net_id}>")
            findings.append(Finding(
                rule="R004", severity="error",
                message=(f"Net '{net_name}' (id {net_id}) has copper (tracks/vias) "
                          f"but is not connected to ANY footprint pad. Copper is "
                          f"floating relative to components."),
                location=net_name,
            ))
    return findings


def rule_R005_component_totally_unrouted(ctx: BoardContext) -> List[Finding]:
    """R005: A non-mounting-hole footprint where every pad is either netless
    or on a single-pin net — i.e. the component is electrically isolated
    from the rest of the board despite being physically placed."""
    findings = []
    for fp in ctx.footprints:
        if "mountinghole" in fp.library_id.lower():
            continue
        if not fp.pads:
            continue
        problem_pads = 0
        for pad in fp.pads:
            if pad.number == "":
                continue
            if pad.net_id is None:
                problem_pads += 1
            elif len(ctx.net_pad_endpoints.get(pad.net_id, [])) <= 1:
                problem_pads += 1
        numbered_pads = [p for p in fp.pads if p.number != ""]
        if numbered_pads and problem_pads == len(numbered_pads):
            findings.append(Finding(
                rule="R005", severity="error",
                message=(f"Component '{fp.value}' ({fp.library_id}) has ALL "
                          f"{len(numbered_pads)} pads either netless or on dead-end "
                          f"nets. This part is not actually wired into the circuit."),
                location=fp.reference,
            ))
    return findings


def rule_R006_decoupling_cap_shorted(ctx: BoardContext) -> List[Finding]:
    """R006: A 2-pad passive (cap/resistor by naming convention 'C_' / 'R_')
    where both pads share the same net = short."""
    findings = []
    for fp in ctx.footprints:
        if len(fp.pads) == 2 and (fp.reference.startswith("C") or fp.reference.startswith("R")):
            p1, p2 = fp.pads[0], fp.pads[1]
            if p1.net_id is not None and p1.net_id == p2.net_id:
                net_name = ctx.nets.get(p1.net_id, f"<net {p1.net_id}>")
                findings.append(Finding(
                    rule="R006", severity="error",
                    message=(f"Both pads of {fp.reference} ({fp.value}) are on the "
                              f"same net '{net_name}' — this shorts the component."),
                    location=fp.reference,
                ))
    return findings


def rule_R007_pad_layers_net_mismatch_placeholder(ctx: BoardContext) -> List[Finding]:
    """R007: Reserved for geometric DRC (clearance, overlap) — not computed
    here since it needs full geometry. Placeholder documents the boundary
    of this tool's coverage; see RULES.md R007 for how to run real DRC."""
    return []


SOT223_EXPECTED_PADS = 4  # 3 signal + tab, tab may share pad number with VOUT

def rule_R008_sot223_pad_shape(ctx: BoardContext) -> List[Finding]:
    """R008: SOT-223 3-pin regulator packages should expose exactly 3 UNIQUE
    pad numbers (tab is usually merged into pad 2 by the footprint generator,
    so 3 is normal; if pad 2 appears twice with DIFFERENT sizes, that is the
    telltale sign of a corrupted/hand-edited footprint, not a real tab)."""
    findings = []
    for fp in ctx.footprints:
        if "SOT-223" in fp.library_id and "3" in fp.library_id:
            nums = [p.number for p in fp.pads]
            unique_nums = set(nums)
            if len(nums) != len(unique_nums):
                findings.append(Finding(
                    rule="R008", severity="error",
                    message=(f"SOT-223-3 footprint has {len(nums)} pad entries but "
                              f"only {len(unique_nums)} unique numbers "
                              f"({sorted(unique_nums)}). Expected exactly 3 unique "
                              f"numbered pads (1=GND,2=VOUT/tab,3=VIN per AMS1117 "
                              f"convention, but VERIFY against the actual datasheet "
                              f"pinout silkscreen/orientation)."),
                    location=f"{fp.reference} ({fp.value})",
                ))
    return findings


def rule_R009_net_id_not_declared(ctx: BoardContext) -> List[Finding]:
    """R009: A pad/via/segment references a net id that never appears in the
    top-level (net ...) table. Indicates a corrupted or hand-merged file."""
    findings = []
    declared = set(ctx.nets.keys())
    used = set(ctx.via_nets) | set(ctx.segment_nets)
    for fp in ctx.footprints:
        for pad in fp.pads:
            if pad.net_id is not None:
                used.add(pad.net_id)
    for net_id in sorted(used - declared):
        findings.append(Finding(
            rule="R009", severity="error",
            message=f"Net id {net_id} is used but never declared in the (net ...) table.",
            location=f"net id {net_id}",
        ))
    return findings


def rule_R010_suspicious_net_split(ctx: BoardContext) -> List[Finding]:
    """R010 (heuristic): Two nets whose NAMES suggest they should be the same
    rail (e.g. '3.3V_ESP' vs '3.3V_FLIPPER', or 'GND' vs 'GND2') but are
    modeled as separate net ids with no footprint bridging them. This is a
    heuristic based on naming, always needs human confirmation — flagged as
    'info' not 'error'."""
    findings = []
    import re as _re
    voltage_like = {}
    for net_id, name in ctx.nets.items():
        m = _re.match(r'^(\d+(?:\.\d+)?V)_', name)
        if m:
            voltage_like.setdefault(m.group(1), []).append((net_id, name))
    for voltage, group in voltage_like.items():
        if len(group) > 1:
            names = ", ".join(f"{n} (id {i})" for i, n in group)
            findings.append(Finding(
                rule="R010", severity="info",
                message=(f"Multiple distinct nets share the '{voltage}' prefix but "
                          f"are different nets: {names}. Confirm whether these should "
                          f"be electrically joined (e.g. via the regulator output) or "
                          f"are intentionally isolated rails."),
                location=voltage,
            ))
    return findings


def rule_R011_reference_designator_gaps(ctx: BoardContext) -> List[Finding]:
    """R011 (info): Reference designators with the same prefix show large
    numeric gaps (e.g. IC_001 then IC_006), suggesting deleted/never-placed
    components and an un-re-annotated design. Purely informational — gaps
    are not inherently wrong, but worth a human sanity check."""
    findings = []
    import re as _re
    by_prefix: Dict[str, List[int]] = defaultdict(list)
    pattern = _re.compile(r'^([A-Za-z_]+?)(\d+)$')
    for fp in ctx.footprints:
        m = pattern.match(fp.reference)
        if m:
            by_prefix[m.group(1)].append(int(m.group(2)))
    for prefix, nums in by_prefix.items():
        nums_sorted = sorted(nums)
        gaps = []
        for a, b in zip(nums_sorted, nums_sorted[1:]):
            if b - a > 1:
                gaps.append((a, b))
        if gaps:
            gap_str = ", ".join(f"{a}->{b}" for a, b in gaps)
            findings.append(Finding(
                rule="R011", severity="info",
                message=(f"Reference prefix '{prefix}' has numbering gaps: {gap_str}. "
                          f"May indicate deleted parts or a design assembled "
                          f"programmatically without re-annotation."),
                location=prefix,
            ))
    return findings


def rule_R012_duplicate_reference(ctx: BoardContext) -> List[Finding]:
    """R012: Two footprints sharing the exact same reference designator —
    always an error, KiCad annotation must be unique."""
    findings = []
    seen = defaultdict(int)
    for fp in ctx.footprints:
        seen[fp.reference] += 1
    for ref, count in seen.items():
        if count > 1:
            findings.append(Finding(
                rule="R012", severity="error",
                message=f"Reference designator '{ref}' is used by {count} footprints.",
                location=ref,
            ))
    return findings


def rule_R013_keepout_single_layer(ctx: BoardContext) -> List[Finding]:
    """R013: Keepout zones defined on only a single layer (e.g. F.Cu only).
    RF keepouts or copper clearings often need to cover both top and bottom
    (or all copper layers) to prevent ground planes from invalidating antenna radiation."""
    findings = []
    for idx, (layers, is_keepout) in enumerate(ctx.zones, 1):
        if is_keepout and len(layers) <= 1:
            layer_str = ", ".join(layers) if layers else "none"
            findings.append(Finding(
                rule="R013", severity="warning",
                message=(f"Keepout zone #{idx} is declared on only {len(layers)} layer "
                         f"({layer_str}). If this is an RF/antenna keepout, ensure "
                         f"opposite/internal ground planes are also kept out."),
                location=f"zone #{idx} ({layer_str})",
            ))
    return findings


def rule_R014_regulator_missing_caps(ctx: BoardContext) -> List[Finding]:
    """R014: Linear regulators (AMS1117, SOT-223 regulators) must have decoupling
    capacitors connected between each active power pin (VIN, VOUT) and GND."""
    findings = []
    cap_nets: Dict[int, List[str]] = defaultdict(list)
    for fp in ctx.footprints:
        if len(fp.pads) == 2 and fp.reference.startswith("C"):
            n1, n2 = fp.pads[0].net_id, fp.pads[1].net_id
            name1 = (ctx.nets.get(n1) or fp.pads[0].net_name or "") if n1 is not None else ""
            name2 = (ctx.nets.get(n2) or fp.pads[1].net_name or "") if n2 is not None else ""
            is_gnd1 = "gnd" in name1.lower()
            is_gnd2 = "gnd" in name2.lower()
            if is_gnd1 and n2 is not None and not is_gnd2:
                cap_nets[n2].append(fp.reference)
            elif is_gnd2 and n1 is not None and not is_gnd1:
                cap_nets[n1].append(fp.reference)

    REGULATOR_KEYWORDS = {"ams1117", "lm1117", "sot-223", "regulator_linear", "7805", "78m05"}
    for fp in ctx.footprints:
        lib_val = (fp.library_id + " " + fp.value).lower()
        if any(kw in lib_val for kw in REGULATOR_KEYWORDS):
            power_nets = set()
            for pad in fp.pads:
                if pad.net_id is not None:
                    name = ctx.nets.get(pad.net_id) or pad.net_name or ""
                    if name and "gnd" not in name.lower():
                        power_nets.add((pad.net_id, name))
            for net_id, net_name in power_nets:
                if net_id not in cap_nets or len(cap_nets[net_id]) == 0:
                    findings.append(Finding(
                        rule="R014", severity="warning",
                        message=(f"Regulator {fp.reference} ({fp.value}) power rail '{net_name}' "
                                 f"has no decoupling capacitor to GND."),
                        location=f"{fp.reference} ({net_name})",
                    ))
    return findings


ALL_RULES = [
    rule_R001_duplicate_pad_numbers,
    rule_R002_unassigned_pads,
    rule_R003_single_pin_nets,
    rule_R004_routed_but_no_pads,
    rule_R005_component_totally_unrouted,
    rule_R006_decoupling_cap_shorted,
    rule_R008_sot223_pad_shape,
    rule_R009_net_id_not_declared,
    rule_R010_suspicious_net_split,
    rule_R011_reference_designator_gaps,
    rule_R012_duplicate_reference,
    rule_R013_keepout_single_layer,
    rule_R014_regulator_missing_caps,
]


def run_audit(path: str, rule_filter: Optional[List[str]] = None) -> List[Finding]:
    ctx = BoardContext(path)
    findings: List[Finding] = []
    for rule_fn in ALL_RULES:
        rule_id = rule_fn.__name__.split("_")[1]  # e.g. "R001"
        if rule_filter and rule_id not in rule_filter:
            continue
        findings.extend(rule_fn(ctx))
    return findings, ctx


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def print_report(findings: List[Finding], ctx: BoardContext) -> None:
    findings_sorted = sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule))
    n_err = sum(1 for f in findings if f.severity == "error")
    n_warn = sum(1 for f in findings if f.severity == "warning")
    n_info = sum(1 for f in findings if f.severity == "info")

    print("=" * 78)
    print(f"KiCad PCB Audit — {len(ctx.footprints)} footprints, {len(ctx.nets)} declared nets")
    print(f"Findings: {n_err} errors, {n_warn} warnings, {n_info} info")
    print("=" * 78)
    for f in findings_sorted:
        tag = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[f.severity]
        print(f"[{f.rule}] {tag} | {f.location}")
        print(f"        {f.message}")
        print()

    if not findings:
        print("No issues detected by the implemented rule set.")
        print("(Remember: this tool does not replace KiCad's geometric DRC —")
        print(" run Inspect > Design Rules Checker for clearance/overlap checks.)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board", help="Path to .kicad_pcb file")
    ap.add_argument("--json", help="Also write findings as JSON to this path")
    ap.add_argument("--rule", help="Comma-separated rule IDs to run, e.g. R001,R002")
    args = ap.parse_args()

    rule_filter = args.rule.split(",") if args.rule else None
    findings, ctx = run_audit(args.board, rule_filter)
    print_report(findings, ctx)

    if args.json:
        payload = {
            "board": args.board,
            "summary": {
                "footprints": len(ctx.footprints),
                "declared_nets": len(ctx.nets),
                "errors": sum(1 for f in findings if f.severity == "error"),
                "warnings": sum(1 for f in findings if f.severity == "warning"),
                "info": sum(1 for f in findings if f.severity == "info"),
            },
            "findings": [asdict(f) for f in findings],
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"\nJSON report written to {args.json}")

    # Exit code reflects severity for CI usage
    if any(f.severity == "error" for f in findings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
