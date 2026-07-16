"""
bridge/island_layout.py
=======================
Hierarchical Island Packing Algorithm for PulseLab.

Groups components into topological islands based on net connectivity,
estimates physical sizes, and packs them into a non-overlapping layout.

Two modes:
  - 'pcb':       returns positions in mm for PCBLayout
  - 'schematic': returns positions in grid units for SchematicGenerator
                  (constrained to fit A4 paper)
"""

from __future__ import annotations
import math
from typing import List, Dict, Tuple, Any

# ═══════════════════════════════════════════════════════════════════════════════
# SIZE ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════════

# Approximate physical sizes in mm  (width, height)
_PCB_SIZES = {
    "MCU":          (22.0, 28.0),   # ESP32-S3-WROOM-1: 18x25.5 + clearance
    "IC_large":     (12.0, 10.0),   # SOP-16, QFP, modules
    "IC_small":     ( 6.0,  6.0),   # SOP-8, small ICs
    "IC_header":    ( 3.0,  0.0),   # per-pin height calculated dynamically
    "S":            ( 7.0,  7.0),   # tactile switch + keepout
    "R":            ( 3.5,  2.0),   # 0805 with courtyard
    "C":            ( 3.5,  2.0),
    "L":            ( 3.5,  2.0),
    "V":            ( 6.0,  4.0),   # battery / power header
    "GND":          ( 2.0,  2.0),
    "default":      ( 6.0,  6.0),
}

# Schematic grid units (columns, rows) — much smaller numbers
_SCH_SIZES = {
    "MCU":          ( 6,  8),
    "IC_large":     ( 4,  5),
    "IC_small":     ( 3,  3),
    "IC_header":    ( 2,  0),       # per-pin
    "S":            ( 2,  2),
    "R":            ( 2,  1),
    "C":            ( 2,  1),
    "L":            ( 2,  1),
    "V":            ( 2,  2),
    "GND":          ( 1,  1),
    "default":      ( 3,  3),
}

POWER_NETS = frozenset({
    "GND", "3.3V", "3V3", "VCC", "5V", "VBUS", "VCC33",
    "GND_PAD", "0", "",
})


def _classify(c) -> str:
    """Classify a component into a size category."""
    etype = getattr(c, "etype", "")
    # value may be coerced to float 0.0 for string ICs, so also check label
    val = str(getattr(c, "value", "")).upper()
    label = str(getattr(c, "label", "")).upper()
    f_id = str(getattr(c, "footprint_id", "") or "").upper()
    n_pins = len(getattr(c, "pins", {}) or {})
    pins_dict = getattr(c, "pins", {}) or {}
    # Combined identity string for keyword matching
    identity = " ".join([val, label, f_id])

    if etype == "MCU" or "ESP32" in identity:
        return "MCU"
    if etype == "IC":
        POWER_NETS_LOCAL = {"GND", "3.3V", "3V3", "VCC", "5V", "VBUS", "VCC33", "GND_PAD", "0", ""}
        signal_nets = {n for n in pins_dict.values() if n not in POWER_NETS_LOCAL}
        # If this IC has real signal nets, it's a functional module (SSD1306, PN532 etc.)
        # Signal presence overrides any footprint/label name heuristics
        if signal_nets:
            if n_pins >= 20:
                return "IC_large"
            return "IC_small"
        # No signal nets -> pure connector / header
        return "IC_header"

    if etype in _PCB_SIZES:
        return etype
    return "default"


def estimate_size(c, mode: str = "pcb") -> Tuple[float, float]:
    """Return (width, height) for a component."""
    cat = _classify(c)
    table = _PCB_SIZES if mode == "pcb" else _SCH_SIZES

    w, h = table.get(cat, table["default"])

    # Dynamic height for headers based on pin count
    if cat == "IC_header":
        n_pins = max(len(getattr(c, "pins", {}) or {}), 2)
        per_pin = 2.54 if mode == "pcb" else 1.2
        h = n_pins * per_pin
        w = table["IC_header"][0]   # keep width fixed

    return (w, h)


# ═══════════════════════════════════════════════════════════════════════════════
# TOPOLOGICAL GROUPING
# ═══════════════════════════════════════════════════════════════════════════════

def group_into_islands(components: List[Any]) -> List[List[Any]]:
    """
    Group components into topological islands.

    Strategy:
      1. Find the single primary anchor (MCU, or the IC with most signal nets).
      2. All ICs/headers that share signal nets with the primary anchor
         become its dependents (placed near it), NOT independent islands.
      3. Components that share signal nets with a secondary IC but NOT the
         primary anchor form their own small islands.
      4. Pure power-only passives (decoupling caps) become standalone islands.
    """
    if not components:
        return []

    # Build signal net map: net_name -> list of component uids
    net_members: Dict[str, List[str]] = {}
    comp_map: Dict[str, Any] = {}

    for c in components:
        comp_map[c.uid] = c
        pins = getattr(c, "pins", {}) or {}
        for net in pins.values():
            if net and net not in POWER_NETS:
                net_members.setdefault(net, []).append(c.uid)

    # Find the primary anchor (MCU preferred, else IC with most signal nets)
    primary = None
    for c in components:
        if c.etype == "MCU":
            primary = c
            break

    if primary is None:
        # Pick the IC with the most signal-net connections
        best, best_count = None, -1
        for c in components:
            if c.etype in ("IC", "V") or len(getattr(c, "pins", {}) or {}) >= 3:
                pins = getattr(c, "pins", {}) or {}
                sig_count = sum(1 for n in pins.values() if n and n not in POWER_NETS)
                if sig_count > best_count:
                    best, best_count = c, sig_count
        primary = best

    if primary is None:
        # No anchor at all — just return everything as one island
        return [components]

    # Collect all signal nets owned by the primary anchor
    primary_pins = getattr(primary, "pins", {}) or {}
    primary_nets = {n for n in primary_pins.values() if n and n not in POWER_NETS}

    # Assign components to islands
    primary_island = [primary]
    secondary_islands: Dict[str, List[Any]] = {}   # secondary IC uid -> members
    standalone: List[Any] = []

    for c in components:
        if c.uid == primary.uid:
            continue

        c_pins = getattr(c, "pins", {}) or {}
        c_signal_nets = {n for n in c_pins.values() if n and n not in POWER_NETS}

        # Does this component share signal nets with the primary?
        shared_with_primary = c_signal_nets & primary_nets

        if shared_with_primary:
            primary_island.append(c)
        elif c.etype in ("IC", "MCU") or len(c_pins) >= 3:
            # Secondary IC with its own signal domain
            secondary_islands[c.uid] = [c]
        elif c_signal_nets:
            # Try to attach to a secondary IC
            attached = False
            for sec_uid, sec_members in secondary_islands.items():
                sec_c = comp_map[sec_uid]
                sec_pins = getattr(sec_c, "pins", {}) or {}
                sec_nets = {n for n in sec_pins.values() if n and n not in POWER_NETS}
                if c_signal_nets & sec_nets:
                    sec_members.append(c)
                    attached = True
                    break
            if not attached:
                standalone.append(c)
        else:
            standalone.append(c)

    # Group standalone by shared nets
    standalone_islands: List[List[Any]] = []
    visited = set()
    for c in standalone:
        if c.uid in visited:
            continue
        cluster = [c]
        visited.add(c.uid)
        queue = [c]
        while queue:
            curr = queue.pop(0)
            curr_pins = getattr(curr, "pins", {}) or {}
            curr_nets = {n for n in curr_pins.values() if n and n not in POWER_NETS}
            for other in standalone:
                if other.uid in visited:
                    continue
                other_pins = getattr(other, "pins", {}) or {}
                other_nets = {n for n in other_pins.values() if n and n not in POWER_NETS}
                if curr_nets & other_nets:
                    cluster.append(other)
                    visited.add(other.uid)
                    queue.append(other)
        standalone_islands.append(cluster)

    all_islands = [primary_island]
    all_islands.extend(v for v in secondary_islands.values() if v)
    all_islands.extend(standalone_islands)
    return all_islands


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _layout_island(
    island: List[Any],
    mode: str,
    dep_spacing: float,
) -> Tuple[Dict[str, Tuple[float, float]], float, float]:
    """
    Arrange components within a single island.
    Returns (local_positions, island_width, island_height).
    The anchor is centered at (0, 0).
    """
    anchor = island[0]
    aw, ah = estimate_size(anchor, mode)
    local_pos: Dict[str, Tuple[float, float]] = {anchor.uid: (0.0, 0.0)}

    deps = island[1:]
    if not deps:
        return local_pos, aw, ah

    # Measure all dependents
    dep_sizes = [(d, *estimate_size(d, mode)) for d in deps]
    max_dw = max(s[1] for s in dep_sizes)
    max_dh = max(s[2] for s in dep_sizes)

    cell_w = max_dw + dep_spacing
    cell_h = max_dh + dep_spacing

    # Arrange dependents in a grid to the right of the anchor
    # Use more columns for large islands to stay compact
    if len(deps) > 12:
        dep_cols = min(6, len(deps))
    elif len(deps) > 6:
        dep_cols = min(4, len(deps))
    else:
        dep_cols = min(3, len(deps))
    dep_rows = math.ceil(len(deps) / dep_cols)

    grid_w = dep_cols * cell_w
    grid_h = dep_rows * cell_h

    # Start position: right of anchor, vertically centered
    start_x = aw / 2.0 + dep_spacing + max_dw / 2.0
    start_y = -(grid_h - cell_h) / 2.0

    for idx, (d, dw, dh) in enumerate(dep_sizes):
        r = idx // dep_cols
        c = idx % dep_cols
        px = start_x + c * cell_w
        py = start_y + r * cell_h
        local_pos[d.uid] = (px, py)

    # Compute bounding box
    all_x = []
    all_y = []
    for comp in island:
        cx, cy = local_pos[comp.uid]
        cw, ch = estimate_size(comp, mode)
        all_x.extend([cx - cw / 2, cx + cw / 2])
        all_y.extend([cy - ch / 2, cy + ch / 2])

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    # Normalize so top-left is (0, 0)
    for uid in local_pos:
        ox, oy = local_pos[uid]
        local_pos[uid] = (ox - min_x, oy - min_y)

    return local_pos, max_x - min_x, max_y - min_y


def compute_layout(
    components: List[Any],
    mode: str = "pcb",
    spacing: float = 4.0,
    island_spacing: float = 8.0,
    margin: float = 8.0,
    max_width: float = 0.0,
    max_height: float = 0.0,
) -> Tuple[Dict[str, Tuple[float, float]], float, float]:
    """
    Compute global (x, y) positions for all components.

    Args:
        mode:           'pcb' (mm) or 'schematic' (grid units)
        spacing:        gap between components within an island
        island_spacing: gap between islands
        margin:         board/page margin
        max_width:      if > 0, constrain total width (e.g. A4=297mm for sch)
        max_height:     if > 0, constrain total height

    Returns:
        (positions_dict, total_width, total_height)
    """
    # Defaults for schematic: fit on A4 with grid_scale=5.08, offset=50
    # Usable area: (297-50)/5.08 ≈ 48 grid cols, (210-50)/5.08 ≈ 31 grid rows
    if mode == "schematic":
        spacing = 1.5
        island_spacing = 3.0
        margin = 2.0
        if max_width <= 0:
            max_width = 46.0    # grid units — fits (46*5.08+50=284mm) on A4
        if max_height <= 0:
            max_height = 30.0   # grid units

    islands = group_into_islands(components)
    if not islands:
        return {}, 0.0, 0.0

    # Layout each island locally
    laid_out = []
    for island in islands:
        lp, iw, ih = _layout_island(island, mode, spacing)
        laid_out.append({"island": island, "local": lp, "w": iw, "h": ih})

    # Sort: largest island first for better packing
    laid_out.sort(key=lambda x: x["w"] * x["h"], reverse=True)

    # Pack islands in rows (shelf packing with height constraint)
    shelf_width = max_width - 2 * margin if max_width > 0 else float("inf")
    shelf_height = max_height - 2 * margin if max_height > 0 else float("inf")

    rows: List[List[dict]] = [[]]
    row_w = 0.0
    total_rows_h = 0.0

    for cell in laid_out:
        needed = cell["w"] + (island_spacing if row_w > 0 else 0)
        candidate_row_h = max((c["h"] for c in rows[-1]), default=0)
        candidate_row_h = max(candidate_row_h, cell["h"])

        # Check if adding to current row would overflow width
        width_overflow = row_w > 0 and row_w + needed > shelf_width
        # Check if starting a new row would overflow page height
        height_overflow = total_rows_h + candidate_row_h + island_spacing > shelf_height

        if width_overflow and not height_overflow:
            # Start a new row
            total_rows_h += max(c["h"] for c in rows[-1]) + island_spacing
            rows.append([])
            row_w = 0.0

        rows[-1].append(cell)
        row_w += cell["w"] + island_spacing

    # Assign global positions
    global_pos: Dict[str, Tuple[float, float]] = {}
    cursor_y = margin

    for row in rows:
        row_h = max(c["h"] for c in row)
        cursor_x = margin

        for cell in row:
            # Center the island vertically within the row
            y_offset = (row_h - cell["h"]) / 2.0

            for comp in cell["island"]:
                lx, ly = cell["local"][comp.uid]
                gx = cursor_x + lx
                gy = cursor_y + y_offset + ly
                global_pos[comp.uid] = (round(gx, 2), round(gy, 2))

            cursor_x += cell["w"] + island_spacing

        cursor_y += row_h + island_spacing

    total_w = max(pos[0] for pos in global_pos.values()) + margin if global_pos else 0
    total_h = max(pos[1] for pos in global_pos.values()) + margin if global_pos else 0

    # Add component sizes to total
    for c in components:
        if c.uid in global_pos:
            cw, ch = estimate_size(c, mode)
            total_w = max(total_w, global_pos[c.uid][0] + cw / 2 + margin)
            total_h = max(total_h, global_pos[c.uid][1] + ch / 2 + margin)

    return global_pos, total_w, total_h
