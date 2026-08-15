"""
thermal_engine.py
=================
Thermal Management Engine for KiCad PCB Design in PulseLab.

Provides:
- Thermal via grid generator for EPADs (exposed thermal pads, e.g. ESP32 MCU Pad 41).
- Thermal spoke and gap configuration formatting for zone copper pours.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class ThermalViaConfig:
    rows: int = 3
    cols: int = 3
    pitch: float = 1.2
    via_size: float = 0.6
    drill: float = 0.3
    net_name: str = "PWR_GND"
    net_id: int = 1

@dataclass
class ThermalZoneConfig:
    thermal_gap: float = 0.5
    thermal_bridge_width: float = 0.5
    connect_pads: str = "thermal_relief" # "thermal_relief", "solid", "none"

def generate_thermal_via_grid(
    center_x: float,
    center_y: float,
    rows: int = 3,
    cols: int = 3,
    pitch: float = 1.2,
    via_size: float = 0.6,
    drill: float = 0.3,
    net_name: str = "PWR_GND",
    net_id: int = 1
) -> List[Dict]:
    """
    Generates an N x M matrix of thermal vias centered around (center_x, center_y).
    Returns a list of via dictionaries with coordinates and parameters.
    """
    vias = []
    start_x = center_x - ((cols - 1) * pitch / 2.0)
    start_y = center_y - ((rows - 1) * pitch / 2.0)

    for r in range(rows):
        for c in range(cols):
            vx = round(start_x + c * pitch, 4)
            vy = round(start_y + r * pitch, 4)
            vias.append({
                "x": vx,
                "y": vy,
                "size": via_size,
                "drill": drill,
                "net_name": net_name,
                "net_id": net_id
            })
    return vias

def format_thermal_via_sexpr(via: Dict) -> str:
    """Formats a single thermal via into KiCad S-expression string."""
    return (
        f'  (via (at {via["x"]:.4f} {via["y"]:.4f}) '
        f'(size {via["size"]:.2f}) (drill {via["drill"]:.2f}) '
        f'(layers "F.Cu" "B.Cu") (net {via["net_id"]}))'
    )

def format_thermal_vias_sexpr(vias: List[Dict]) -> List[str]:
    """Formats a list of thermal vias into S-expression strings."""
    return [format_thermal_via_sexpr(v) for v in vias]
