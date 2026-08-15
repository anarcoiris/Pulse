"""
copper_zone_manager.py
======================
Copper Pour & 0V Reference Plane Manager for PulseLab EDA Platform.

Provides:
- 0V Reference plane generation for F.Cu and B.Cu layers.
- Ground via stitching grid generator for EMI reduction and low ground impedance.
- Split-plane ground isolation zone management.
- KiCad S-expression zone generator.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class CopperZone:
    net_name: str = "PWR_GND"
    net_id: int = 1
    layer: str = "F.Cu"
    points: List[Tuple[float, float]] = field(default_factory=list)
    clearance: float = 0.15
    min_thickness: float = 0.12
    hatch_style: str = "edge"
    hatch_pitch: float = 0.5
    connect_pads: str = "thermal_relief"
    thermal_bridge_width: float = 0.5
    thermal_gap: float = 0.5

def generate_ground_pour_zones(
    bounds: Tuple[float, float, float, float], # (min_x, min_y, max_x, max_y)
    layers: List[str] = None,
    net_name: str = "PWR_GND",
    net_id: int = 1,
    margin: float = 0.2,
    clearance: float = 0.15,
    thermal_bridge_width: float = 0.5
) -> List[CopperZone]:
    """
    Generates double-sided (or multi-layer) ground pour zones fitting within board bounds.
    """
    if layers is None:
        layers = ["F.Cu", "B.Cu"]

    min_x, min_y, max_x, max_y = bounds
    # Shrink/Expand zone polygon slightly based on edge margin
    pts = [
        (round(min_x + margin, 4), round(min_y + margin, 4)),
        (round(max_x - margin, 4), round(min_y + margin, 4)),
        (round(max_x - margin, 4), round(max_y - margin, 4)),
        (round(min_x + margin, 4), round(max_y - margin, 4)),
    ]

    zones = []
    for layer in layers:
        zones.append(
            CopperZone(
                net_name=net_name,
                net_id=net_id,
                layer=layer,
                points=pts,
                clearance=clearance,
                thermal_bridge_width=thermal_bridge_width
            )
        )
    return zones

def generate_stitching_vias(
    bounds: Tuple[float, float, float, float],
    grid_step: float = 2.5,
    margin: float = 1.5,
    via_size: float = 0.6,
    drill: float = 0.3,
    net_name: str = "PWR_GND",
    net_id: int = 1,
    keepout_boxes: Optional[List[Tuple[float, float, float, float]]] = None
) -> List[Dict]:
    """
    Generates a grid of ground stitching vias across board bounds.
    Skips vias that land inside keepout boxes (e.g. signal pads/connectors).
    """
    min_x, min_y, max_x, max_y = bounds
    if keepout_boxes is None:
        keepout_boxes = []

    vias = []
    curr_x = min_x + margin
    while curr_x <= max_x - margin:
        curr_y = min_y + margin
        while curr_y <= max_y - margin:
            # Check keepouts
            inside_keepout = False
            for kx1, ky1, kx2, ky2 in keepout_boxes:
                if kx1 <= curr_x <= kx2 and ky1 <= curr_y <= ky2:
                    inside_keepout = True
                    break
            
            if not inside_keepout:
                vias.append({
                    "x": round(curr_x, 4),
                    "y": round(curr_y, 4),
                    "size": via_size,
                    "drill": drill,
                    "net_name": net_name,
                    "net_id": net_id
                })
            curr_y += grid_step
        curr_x += grid_step

    return vias

def format_zone_sexpr(zone: CopperZone) -> str:
    """Formats a CopperZone into KiCad S-expression string block."""
    pts_str = " ".join([f"(xy {x:.4f} {y:.4f})" for x, y in zone.points])
    return (
        f'  (zone (net {zone.net_id}) (net_name "{zone.net_name}") (layer "{zone.layer}")\n'
        f'    (hatch {zone.hatch_style} {zone.hatch_pitch:.2f})\n'
        f'    (connect_pads (clearance {zone.clearance:.2f}))\n'
        f'    (min_thickness {zone.min_thickness:.2f})\n'
        f'    (filled_polygon\n'
        f'      (pts {pts_str})\n'
        f'    )\n'
        f'  )'
    )
