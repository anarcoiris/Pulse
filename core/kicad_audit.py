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
import math
from typing import Any, Dict, List, Optional, Tuple

from core.sexp import parse, find_all, find_direct, first_direct, Node


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
    rotation: float = 0.0
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


def extract_top_level_nets(root: Node) -> Dict[int, str]:
    """Extract ONLY top-level (net <id> "<name>") declarations."""
    nets = {}
    root_list = root if isinstance(root, list) else [root]
    for n in find_direct(root_list, "net"):
        try:
            net_id = int(n[1])
            net_name = n[2] if len(n) > 2 else ""
            nets[net_id] = net_name
        except (ValueError, TypeError):
            pass
    return nets


def extract_nets(root: Node) -> Dict[int, str]:
    nets = extract_top_level_nets(root)
    # Collect net names from footprint pads as fallback
    for fp in extract_footprints(root):
        for pad in fp.pads:
            if pad.net_id is not None and pad.net_name and pad.net_id not in nets:
                nets[pad.net_id] = pad.net_name
            elif pad.net_name and pad.net_name not in nets.values():
                nets[pad.net_name] = pad.net_name
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
        rotation = float(at_node[3]) if at_node and len(at_node) > 3 else 0.0
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
            net_id = None
            net_name = None
            if net_node and len(net_node) > 1:
                try:
                    net_id = int(net_node[1])
                    net_name = str(net_node[2]) if len(net_node) > 2 else None
                except (ValueError, TypeError):
                    net_name = str(net_node[1])
            pads.append(Pad(number, pad_type, shape, net_id, net_name, layers, pad_at))

        fps.append(Footprint(lib_id, ref, value, at, layer, rotation, pads))
    return fps


def extract_via_nets(root: Node) -> List[int]:
    out = []
    for v in find_all(root, "via"):
        net_node = first_direct(v, "net")
        if net_node:
            try:
                out.append(int(net_node[1]))
            except (ValueError, TypeError):
                pass
    return out


def extract_segment_nets(root: Node) -> List[int]:
    out = []
    for s in find_all(root, "segment"):
        net_node = first_direct(s, "net")
        if net_node:
            try:
                out.append(int(net_node[1]))
            except (ValueError, TypeError):
                pass
    return out


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
        self.declared_nets = extract_top_level_nets(self.root)
        self.nets = extract_nets(self.root)
        self.footprints = extract_footprints(self.root)
        self.via_nets = extract_via_nets(self.root)
        self.segment_nets = extract_segment_nets(self.root)

        # net_id -> set of (ref, pad_number) endpoints from footprint pads
        self.net_pad_endpoints: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        for fp in self.footprints:
            for pad in fp.pads:
                if pad.net_id is not None:
                    self.net_pad_endpoints[pad.net_id].append((fp.reference, pad.number))


KNOWN_UNCONNECTED_HINTS = {"NC", "N/C", "NOCONNECT", "DNC"}


def rule_R001_duplicate_pad_numbers(ctx: BoardContext) -> List[Finding]:
    """R001: A footprint must not have two pads sharing the same pad number
    UNLESS it is a legitimate shield tab or mechanical mounting pad."""
    findings = []
    for fp in ctx.footprints:
        seen = defaultdict(list)
        is_coax = "coaxial" in fp.library_id.lower() or "sma" in fp.library_id.lower()
        for pad in fp.pads:
            seen[pad.number].append(pad)
        for num, plist in seen.items():
            # Skip empty numbers, shield tabs, mechanical pad markers, and SMA ground legs
            if num in ("", "SH", "MP", "PAD", "EP") or num.startswith("SH") or (is_coax and num == "2"):
                continue
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
    """R002: SMD/thru-hole pads with no net at all. Mounting holes, shield tabs,
    and mechanical pads whose number is empty or 'SH' are expected to be netless and are skipped."""
    findings = []
    for fp in ctx.footprints:
        is_mounting = "mountinghole" in fp.library_id.lower() or fp.reference.startswith("MH")
        is_coax = "coaxial" in fp.library_id.lower() or "sma" in fp.library_id.lower()
        for pad in fp.pads:
            if pad.net_id is None:
                if is_mounting or pad.number in ("", "SH", "MP", "EP") or pad.number.startswith("SH") or (is_coax and pad.number == "2"):
                    continue  # expected: mechanical / shield / unnumbered pad
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
    declared = set(ctx.declared_nets.keys())
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


# --------------------------------------------------------------------------
# R013 — Copper connectivity (ratsnest) simulation
# --------------------------------------------------------------------------
# This reimplements, at a coordinate-matching level, what KiCad's DRC
# "unconnected_items" check does: for every net with >=2 pad endpoints,
# confirm that copper (segments + vias) actually forms a single connected
# graph joining all of them. R002/R003/R004 (earlier rules) check whether
# the NETLIST MODEL is coherent (pad has a net, net has endpoints); R013
# checks whether the PHYSICAL COPPER actually realizes that netlist —
# i.e. whether routing is complete. A net can pass every R00x check and
# still fail R013 if it's simply not fully routed yet.

_COORD_TOL = 3  # decimal places for coordinate matching (== 0.001mm grid)


def _layer_set_for_pad(pad: Pad) -> frozenset:
    expanded = set()
    for l in pad.layers:
        if l in ("*.Cu", "F&B.Cu"):
            expanded.add("F.Cu")
            expanded.add("B.Cu")
        else:
            expanded.add(l)
    return frozenset(expanded)


class _UnionFind:
    def __init__(self):
        self.parent: Dict[Any, Any] = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _extract_segments_raw(root: Node) -> List[Dict[str, Any]]:
    out = []
    for s in find_all(root, "segment"):
        start = first_direct(s, "start")
        end = first_direct(s, "end")
        layer_node = first_direct(s, "layer")
        net_node = first_direct(s, "net")
        if not (start and end and layer_node and net_node):
            continue
        out.append({
            "start": (round(float(start[1]), _COORD_TOL), round(float(start[2]), _COORD_TOL)),
            "end": (round(float(end[1]), _COORD_TOL), round(float(end[2]), _COORD_TOL)),
            "layer": layer_node[1],
            "net": int(net_node[1]),
        })
    return out


def _extract_vias_raw(root: Node) -> List[Dict[str, Any]]:
    out = []
    for v in find_all(root, "via"):
        at = first_direct(v, "at")
        layers_node = first_direct(v, "layers")
        net_node = first_direct(v, "net")
        drill_node = first_direct(v, "drill")
        size_node = first_direct(v, "size")
        if not (at and layers_node and net_node):
            continue
        out.append({
            "at": (round(float(at[1]), _COORD_TOL), round(float(at[2]), _COORD_TOL)),
            "layers": [l for l in layers_node[1:]],
            "net": int(net_node[1]),
            "drill": float(drill_node[1]) if drill_node else None,
            "size": float(size_node[1]) if size_node else None,
        })
    return out


def rule_R013_net_connectivity(ctx: BoardContext) -> List[Finding]:
    findings = []
    segments = _extract_segments_raw(ctx.root)
    vias = _extract_vias_raw(ctx.root)

    seg_by_net: Dict[int, List[Dict]] = defaultdict(list)
    for s in segments:
        seg_by_net[s["net"]].append(s)
    via_by_net: Dict[int, List[Dict]] = defaultdict(list)
    for v in vias:
        via_by_net[v["net"]].append(v)

    has_zones = bool(find_all(ctx.root, "zone"))

    for net_id, endpoints in ctx.net_pad_endpoints.items():
        if net_id == 0 or len(endpoints) < 2:
            continue  # R003 already flags single-pin nets separately

        net_name = ctx.nets.get(net_id, f"<net {net_id}>")
        
        # Ground nets with copper pour zones are unified through the plane
        is_gnd_net = any(g in net_name.upper() for g in ("GND", "PGND", "AGND", "DGND", "SGND"))
        if is_gnd_net and has_zones:
            continue

        uf = _UnionFind()

        pad_lookup: Dict[Tuple[float, float, str], List[str]] = defaultdict(list)
        pad_ids = []
        for fp in ctx.footprints:
            rot_rad = math.radians(getattr(fp, 'rotation', 0.0))
            cos_r = math.cos(rot_rad)
            sin_r = math.sin(rot_rad)
            for pad in fp.pads:
                if pad.net_id != net_id:
                    continue
                pad_id = f"PAD:{fp.reference}:{pad.number}"
                pad_ids.append(pad_id)
                rx = pad.at[0] * cos_r - pad.at[1] * sin_r
                ry = pad.at[0] * sin_r + pad.at[1] * cos_r
                x = round(fp.at[0] + rx, _COORD_TOL)
                y = round(fp.at[1] + ry, _COORD_TOL)
                for layer in _layer_set_for_pad(pad):
                    pad_lookup[(x, y, layer)].append(pad_id)
                uf.find(pad_id)

        seg_node_keys = []
        for i, s in enumerate(seg_by_net.get(net_id, [])):
            node = f"SEG{i}:{s['start']}"
            node2 = f"SEG{i}:{s['end']}"
            uf.union(node, node2)
            seg_node_keys.append((s["start"], s["layer"], node))
            seg_node_keys.append((s["end"], s["layer"], node2))

        via_node_keys = []
        for i, v in enumerate(via_by_net.get(net_id, [])):
            node = f"VIA{i}:{v['at']}"
            uf.find(node)
            for layer in v["layers"]:
                via_node_keys.append((v["at"], layer, node))

        all_keyed = list(seg_node_keys) + list(via_node_keys)
        by_coord_layer: Dict[Tuple[Tuple[float, float], str], List[str]] = defaultdict(list)
        for coord, layer, node in all_keyed:
            by_coord_layer[(coord, layer)].append(node)
        for (coord, layer), nodes in by_coord_layer.items():
            for n in nodes[1:]:
                uf.union(nodes[0], n)
            for (px, py, player), p_ids in pad_lookup.items():
                if player == layer or player in ("*.Cu", "F&B.Cu"):
                    if math.hypot(coord[0] - px, coord[1] - py) <= 0.65:
                        for pad_id in p_ids:
                            uf.union(nodes[0], pad_id)
            # T-Junction connection: point touching along the interior of a trace segment
            for i, s in enumerate(seg_by_net.get(net_id, [])):
                if s["layer"] == layer:
                    x1, y1 = s["start"]
                    x2, y2 = s["end"]
                    dx = x2 - x1
                    dy = y2 - y1
                    l2 = dx * dx + dy * dy
                    if l2 > 0.0001:
                        t = max(0.0, min(1.0, ((coord[0] - x1) * dx + (coord[1] - y1) * dy) / l2))
                        proj_x = x1 + t * dx
                        proj_y = y1 + t * dy
                        if math.hypot(coord[0] - proj_x, coord[1] - proj_y) <= 0.08:
                            seg_node = f"SEG{i}:{s['start']}"
                            uf.union(nodes[0], seg_node)

        components: Dict[Any, List[str]] = defaultdict(list)
        for pad_id in pad_ids:
            components[uf.find(pad_id)].append(pad_id)

        if len(components) > 1:
            comp_desc = "; ".join(
                "[" + ", ".join(p.split(":", 1)[1] for p in comp) + "]"
                for comp in components.values()
            )
            findings.append(Finding(
                rule="R013", severity="error",
                message=(f"Net '{net_name}' has {len(components)} disconnected copper "
                          f"islands among its {len(pad_ids)} pads — routing is "
                          f"incomplete. Groups: {comp_desc}. Needs at least "
                          f"{len(components) - 1} more track(s)/via(s) to fully join."),
                location=net_name,
            ))
    return findings


# --------------------------------------------------------------------------
# R014 — Hole-to-hole clearance (drilled holes only: vias + thru_hole pads)
# --------------------------------------------------------------------------

def rule_R014_hole_to_hole_clearance(ctx: BoardContext, min_clearance_mm: float = 0.25) -> List[Finding]:
    """R014: Center-to-center distance minus both drill radii must be >=
    min_clearance_mm. Default 0.25mm mirrors KiCad's common default
    'hole to hole' constraint — ALWAYS VERIFY against the actual board's
    configured Design Rules (Board Setup > Constraints) since this value
    is not stored inside kicad_pcb's own text and may be customized."""
    findings = []
    points: List[Tuple[str, float, float, float]] = []  # (label, x, y, drill_mm)

    for fp_node in find_direct(ctx.root, "footprint"):
        ref = "?"
        for prop in find_direct(fp_node, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                ref = prop[2]
        fp_at_node = first_direct(fp_node, "at")
        fx, fy = _get_num_pair(fp_at_node) if fp_at_node else (0.0, 0.0)
        for pad_node in find_direct(fp_node, "pad"):
            pad_type = pad_node[2] if len(pad_node) > 2 else ""
            if pad_type not in ("thru_hole", "np_thru_hole"):
                continue
            drill_node = first_direct(pad_node, "drill")
            if not drill_node:
                continue
            drill_val = None
            for tok in drill_node[1:]:
                try:
                    drill_val = float(tok)
                    break
                except (ValueError, TypeError):
                    continue
            if drill_val is None:
                continue
            pad_at_node = first_direct(pad_node, "at")
            px, py = _get_num_pair(pad_at_node) if pad_at_node else (0.0, 0.0)
            num = pad_node[1] if len(pad_node) > 1 else ""
            points.append((f"{ref} pad {num}", fx + px, fy + py, drill_val))

    for i, v in enumerate(find_all(ctx.root, "via")):
        at = first_direct(v, "at")
        drill_node = first_direct(v, "drill")
        if not (at and drill_node):
            continue
        x, y = float(at[1]), float(at[2])
        drill_val = float(drill_node[1])
        points.append((f"via#{i}@({x:.2f},{y:.2f})", x, y, drill_val))

    n = len(points)
    for i in range(n):
        li, xi, yi, di = points[i]
        for j in range(i + 1, n):
            lj, xj, yj, dj = points[j]
            dist = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
            edge_to_edge = dist - (di / 2.0) - (dj / 2.0)
            if edge_to_edge < min_clearance_mm:
                findings.append(Finding(
                    rule="R014", severity="warning",
                    message=(f"Hole-to-hole clearance {edge_to_edge:.4f}mm between "
                              f"{li} (drill {di}mm) and {lj} (drill {dj}mm) is below "
                              f"the {min_clearance_mm}mm threshold used for this check "
                              f"(VERIFY against the board's actual configured minimum "
                              f"in Board Setup > Constraints — this tool cannot read "
                              f"that value from the file)."),
                    location=f"{li} <-> {lj}",
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
    rule_R013_net_connectivity,
    rule_R014_hole_to_hole_clearance,
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
