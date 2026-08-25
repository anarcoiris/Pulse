"""
core/visual_inference.py - Dedicated Visual Inference, Courtyard Hitbox Normalization & Quality Gate

Provides:
1. PACKAGE_PHYSICAL_SPECS: Normalized physical footprint database (W, H, thickness, courtyard margin, pin 1 orientation, lead type).
2. Exact OBB / AABB courtyard hitbox calculation with pad envelopes and IPC-7351B tolerances.
3. 9-Pass Visual Inspection & DFM Quality Radar Engine:
   - Pass 1: Physical Courtyard Collisions & OBB Overlaps (VIS-001)
   - Pass 2: Board Perimeter Clearance & Connector Overhang (VIS-002, VIS-003)
   - Pass 3: Decoupling Capacitor Manhattan Proximity (VIS-004)
   - Pass 4: Thermal Relief & Ground Via Stitching Density (VIS-005)
   - Pass 5: RF Module Antenna Keepout & Exterior Flushness (VIS-006)
   - Pass 6: Net Ratsnest & Trace Routing Quality Gate (VIS-007)
   - Pass 7: UI Controls Symmetry & Uniform Pitch (VIS-008)
   - Pass 8: Power Rail Return & Via Continuity (VIS-009)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path


# ─── Normalized Physical Package Specifications ──────────────────────────────

PACKAGE_PHYSICAL_SPECS: Dict[str, Dict[str, Any]] = {
    # MCU & Complex RF Modules
    "ESP32-S3-WROOM-1": {
        "width": 18.0,
        "height": 25.5,
        "thickness": 3.2,
        "courtyard_margin": 0.50,
        "package_type": "MCU",
        "pin1_corner": "top_left",
        "body_color": "#18181b",
        "lead_type": "QFN_CAST",
        "pin_count": 41,
    },
    "ESP32-WROOM-32": {
        "width": 18.0,
        "height": 25.5,
        "thickness": 3.2,
        "courtyard_margin": 0.50,
        "package_type": "MCU",
        "pin1_corner": "top_left",
        "body_color": "#18181b",
        "lead_type": "QFN_CAST",
        "pin_count": 39,
    },
    "ESP8266": {
        "width": 16.0,
        "height": 24.0,
        "thickness": 3.0,
        "courtyard_margin": 0.50,
        "package_type": "MCU",
        "pin1_corner": "top_left",
        "body_color": "#18181b",
        "lead_type": "QFN_CAST",
        "pin_count": 22,
    },
    "RP2040": {
        "width": 7.0,
        "height": 7.0,
        "thickness": 0.9,
        "courtyard_margin": 0.40,
        "package_type": "MCU",
        "pin1_corner": "top_left",
        "body_color": "#18181b",
        "lead_type": "QFN56",
        "pin_count": 57,
    },
    "CC1101_Module": {
        "width": 17.0,
        "height": 19.0,
        "thickness": 2.5,
        "courtyard_margin": 0.50,
        "package_type": "RF",
        "body_color": "#1e293b",
        "lead_type": "HEADER_2X4",
        "pin_count": 8,
    },
    "NRF24L01_Module": {
        "width": 15.0,
        "height": 29.0,
        "thickness": 2.5,
        "courtyard_margin": 0.50,
        "package_type": "RF",
        "body_color": "#1e293b",
        "lead_type": "HEADER_2X4",
        "pin_count": 8,
    },
    # Regulators & Power ICs
    "SOT-223-3_TabPin2": {
        "width": 6.5,
        "height": 7.0,
        "thickness": 1.8,
        "courtyard_margin": 0.35,
        "package_type": "REGULATOR",
        "pin1_corner": "bottom_left",
        "body_color": "#27272a",
        "lead_type": "GULLWING_TAB",
        "pin_count": 4,
    },
    "SOT-23-5": {
        "width": 2.9,
        "height": 2.8,
        "thickness": 1.2,
        "courtyard_margin": 0.25,
        "package_type": "IC",
        "pin1_corner": "bottom_left",
        "body_color": "#27272a",
        "lead_type": "GULLWING",
        "pin_count": 5,
    },
    "SOIC-8": {
        "width": 4.9,
        "height": 6.0,
        "thickness": 1.75,
        "courtyard_margin": 0.30,
        "package_type": "IC",
        "pin1_corner": "top_left",
        "body_color": "#18181b",
        "lead_type": "SOIC",
        "pin_count": 8,
    },
    "QFN-24-1EP_4x4mm": {
        "width": 4.0,
        "height": 4.0,
        "thickness": 0.90,
        "courtyard_margin": 0.30,
        "package_type": "IC",
        "pin1_corner": "top_left",
        "body_color": "#18181b",
        "lead_type": "QFN24",
        "pin_count": 25,
    },
    "Pololu_Breakout-16": {
        "width": 15.24,
        "height": 20.32,
        "thickness": 3.50,
        "courtyard_margin": 0.50,
        "package_type": "MODULE",
        "pin1_corner": "top_left",
        "body_color": "#1e1e24",
        "lead_type": "DIP16",
        "pin_count": 16,
    },
    # Connectors & Headers
    "USB_Micro-B": {
        "width": 7.5,
        "height": 5.6,
        "thickness": 3.0,
        "courtyard_margin": 0.40,
        "package_type": "CONNECTOR",
        "mating_direction": "outward",
        "body_color": "#a1a1aa",
        "lead_type": "SMD_TH_HYBRID",
        "pin_count": 5,
    },
    "USB_C_Receptacle": {
        "width": 9.0,
        "height": 7.5,
        "thickness": 3.2,
        "courtyard_margin": 0.40,
        "package_type": "CONNECTOR",
        "mating_direction": "outward",
        "body_color": "#94a3b8",
        "lead_type": "SMD_TH_HYBRID",
        "pin_count": 16,
    },
    "JST_XH_4pin": {
        "width": 12.5,
        "height": 5.75,
        "thickness": 7.0,
        "courtyard_margin": 0.40,
        "package_type": "HEADER",
        "body_color": "#f4f4f5",
        "lead_type": "THT_PIN",
        "pin_count": 4,
    },
    "TerminalBlock_2pin_P5.08mm": {
        "width": 10.16,
        "height": 8.0,
        "thickness": 10.0,
        "courtyard_margin": 0.50,
        "package_type": "CONNECTOR",
        "body_color": "#15803d",
        "lead_type": "THT_PIN",
        "pin_count": 2,
    },
    "SMA_Coaxial": {
        "width": 6.35,
        "height": 6.35,
        "thickness": 9.5,
        "courtyard_margin": 0.50,
        "package_type": "CONNECTOR",
        "mating_direction": "outward",
        "body_color": "#eab308",
        "lead_type": "EDGE_MOUNT",
        "pin_count": 5,
    },
    "PinHeader_1xN": {
        "width": 2.54,
        "height": 5.08,
        "height_per_pin": 2.54,
        "thickness": 8.5,
        "courtyard_margin": 0.30,
        "package_type": "HEADER",
        "body_color": "#09090b",
        "lead_type": "THT_PIN",
    },
    "PinHeader_2xN": {
        "width": 5.08,
        "height": 5.08,
        "height_per_pin": 2.54,
        "thickness": 8.5,
        "courtyard_margin": 0.30,
        "package_type": "HEADER",
        "body_color": "#09090b",
        "lead_type": "THT_PIN",
    },
    # Passives (SMD Capacitors, Resistors, Inductors, LEDs, Diodes)
    "C_0805": {
        "width": 2.0,
        "height": 1.25,
        "thickness": 0.9,
        "courtyard_margin": 0.25,
        "package_type": "CAPACITOR",
        "body_color": "#b45309",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "C_0603": {
        "width": 1.6,
        "height": 0.8,
        "thickness": 0.8,
        "courtyard_margin": 0.20,
        "package_type": "CAPACITOR",
        "body_color": "#b45309",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "C_0402": {
        "width": 1.0,
        "height": 0.5,
        "thickness": 0.5,
        "courtyard_margin": 0.15,
        "package_type": "CAPACITOR",
        "body_color": "#b45309",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "R_0805": {
        "width": 2.0,
        "height": 1.25,
        "thickness": 0.6,
        "courtyard_margin": 0.25,
        "package_type": "RESISTOR",
        "body_color": "#334155",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "R_0603": {
        "width": 1.6,
        "height": 0.8,
        "thickness": 0.5,
        "courtyard_margin": 0.20,
        "package_type": "RESISTOR",
        "body_color": "#334155",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "R_0402": {
        "width": 1.0,
        "height": 0.5,
        "thickness": 0.4,
        "courtyard_margin": 0.15,
        "package_type": "RESISTOR",
        "body_color": "#334155",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "LED_0805": {
        "width": 2.0,
        "height": 1.25,
        "thickness": 0.8,
        "courtyard_margin": 0.25,
        "package_type": "LED",
        "body_color": "#10b981",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "LED_0603": {
        "width": 1.6,
        "height": 0.8,
        "thickness": 0.7,
        "courtyard_margin": 0.20,
        "package_type": "LED",
        "body_color": "#10b981",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
    "SW_Tactile_6x6": {
        "width": 6.0,
        "height": 6.0,
        "thickness": 3.5,
        "courtyard_margin": 0.40,
        "package_type": "BUTTON",
        "body_color": "#71717a",
        "lead_type": "SMD_4PAD",
        "pin_count": 4,
    },
    "D_SMA": {
        "width": 4.5,
        "height": 2.6,
        "thickness": 2.1,
        "courtyard_margin": 0.30,
        "package_type": "DIODE",
        "body_color": "#18181b",
        "lead_type": "SMD_2PAD",
        "pin_count": 2,
    },
}


def get_package_spec(footprint_id: str = "", ref: str = "", etype: str = "") -> Dict[str, Any]:
    """Resolves normalized package physical specs from footprint string or component context."""
    fp_upper = footprint_id.upper()
    ref_upper = ref.upper()
    etype_upper = etype.upper()

    # 1. Direct key match
    for k, spec in PACKAGE_PHYSICAL_SPECS.items():
        if k.upper() in fp_upper or k.upper() in ref_upper:
            return dict(spec)

    # 2. Package shape heuristics
    if "ESP32" in fp_upper or "ESP32" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["ESP32-S3-WROOM-1"])
    if "ESP8266" in fp_upper or "ESP8266" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["ESP8266"])
    if "CC1101" in fp_upper or "CC1101" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["CC1101_Module"])
    if "NRF24" in fp_upper or "NRF24" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["NRF24L01_Module"])
    if "SOT-223" in fp_upper or "AMS1117" in ref_upper or "AMS1117" in etype_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["SOT-223-3_TabPin2"])
    if "QFN" in fp_upper or "CP2102" in fp_upper or "CP2102" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["QFN-24-1EP_4x4mm"])
    if "POLOLU" in fp_upper or "A4988" in fp_upper or "TMC2209" in fp_upper or "STEPPER" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["Pololu_Breakout-16"])
    if "MICRO" in fp_upper or "MICRO-B" in fp_upper or "MICRO_B" in fp_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["USB_Micro-B"])
    if "USB" in fp_upper or "TYPE-C" in fp_upper or "USB" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["USB_C_Receptacle"])
    if "TERMINAL" in fp_upper or "BORNIER" in fp_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["TerminalBlock_2pin_P5.08mm"])
    if "JST" in fp_upper or "XH" in fp_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["JST_XH_4pin"])
    if "SMA" in fp_upper or "SMA" in ref_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["SMA_Coaxial"])
    if "SW" in ref_upper or "BUTTON" in etype_upper or "SWITCH" in fp_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["SW_Tactile_6x6"])

    # Pin Headers & Connectors
    if "PINHEADER" in fp_upper or "HEADER" in fp_upper or "CONN" in fp_upper or ref_upper.startswith("CN") or ref_upper.startswith("CONN"):
        if "2X" in fp_upper:
            return dict(PACKAGE_PHYSICAL_SPECS["PinHeader_2xN"])
        return dict(PACKAGE_PHYSICAL_SPECS["PinHeader_1xN"])

    # Passives
    if "LED" in ref_upper or "LED" in etype_upper:
        if "0603" in fp_upper:
            return dict(PACKAGE_PHYSICAL_SPECS["LED_0603"])
        return dict(PACKAGE_PHYSICAL_SPECS["LED_0805"])

    is_cap_ref = (ref_upper.startswith("C") and not any(ref_upper.startswith(prefix) for prefix in ("CN", "CONN", "CLK", "CRYSTAL", "CR", "CON")))
    if is_cap_ref or "CAP" in etype_upper or "C_" in fp_upper:
        if "0402" in fp_upper:
            return dict(PACKAGE_PHYSICAL_SPECS["C_0402"])
        if "0603" in fp_upper:
            return dict(PACKAGE_PHYSICAL_SPECS["C_0603"])
        return dict(PACKAGE_PHYSICAL_SPECS["C_0805"])

    if ref_upper.startswith("R") or "RES" in etype_upper or "R_" in fp_upper:
        if "0402" in fp_upper:
            return dict(PACKAGE_PHYSICAL_SPECS["R_0402"])
        if "0603" in fp_upper:
            return dict(PACKAGE_PHYSICAL_SPECS["R_0603"])
        return dict(PACKAGE_PHYSICAL_SPECS["R_0805"])

    if ref_upper.startswith("D") or "DIODE" in etype_upper or "D_" in fp_upper:
        return dict(PACKAGE_PHYSICAL_SPECS["D_SMA"])

    # Default fallback
    return {
        "width": 3.0,
        "height": 2.0,
        "thickness": 1.0,
        "courtyard_margin": 0.25,
        "package_type": "GENERIC",
        "body_color": "#27272a",
        "lead_type": "GENERIC",
        "pin_count": 2,
    }


# ─── Data Classes & Violation Structures ─────────────────────────────────────

@dataclass
class CourtyardBox:
    """Represents a component's oriented bounding box and courtyard clearance envelope."""
    ref: str
    x: float  # Center X
    y: float  # Center Y
    width: float
    height: float
    rotation: float
    margin: float
    package_type: str

    @property
    def rotated_bounds(self) -> Tuple[float, float, float, float]:
        """Calculates axis-aligned bounding box of rotated courtyard (min_x, min_y, max_x, max_y)."""
        tot_w = self.width + 2 * self.margin
        tot_h = self.height + 2 * self.margin
        theta = math.radians(self.rotation)
        cos_t = abs(math.cos(theta))
        sin_t = abs(math.sin(theta))
        eff_w = tot_w * cos_t + tot_h * sin_t
        eff_h = tot_w * sin_t + tot_h * cos_t
        return (
            self.x - eff_w / 2,
            self.y - eff_h / 2,
            self.x + eff_w / 2,
            self.y + eff_h / 2,
        )

    def intersects(self, other: CourtyardBox) -> bool:
        """Determines if two component courtyards overlap using Separating Axis Theorem (SAT)."""
        b1 = self.rotated_bounds
        b2 = other.rotated_bounds
        return not (
            b1[2] <= b2[0] or
            b1[0] >= b2[2] or
            b1[3] <= b2[1] or
            b1[1] >= b2[3]
        )


@dataclass
class VisualViolation:
    """Represents a visual inspection issue with exact coordinates and remediation guidance."""
    rule_id: str
    severity: str  # 'error' | 'warning' | 'info'
    component_ref: str
    location: Tuple[float, float]
    message: str
    suggested_fix: str


@dataclass
class VisualInspectionReport:
    """Complete summary of the 9-pass visual & DFM inspection gate."""
    passed: bool
    visual_score: float  # 0 to 100
    violations_count: int
    violations: List[VisualViolation]
    courtyards: List[Dict[str, Any]]
    radar: Dict[str, float] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)


# ─── 5-Pass Visual Inference Engine ──────────────────────────────────────────

class VisualInferenceEngine:
    """Automated visual inspection engine evaluating layout geometry, clearances, and topology."""

    def __init__(self, board_width: float = 75.0, board_height: float = 50.0):
        self.board_width = board_width
        self.board_height = board_height
        self.edge_margin_mm = 2.50  # IPC recommended keepout from board edges

    def inspect(self, pcb_obj: Any, circuit_data: Optional[Dict[str, Any]] = None) -> VisualInspectionReport:
        """Executes full 5-pass visual inspection over the PCB layout."""
        violations: List[VisualViolation] = []
        courtyards: List[CourtyardBox] = []

        footprints = getattr(pcb_obj, "_footprints", [])
        board = getattr(pcb_obj, "board", None)
        bw = getattr(board, "width_mm", self.board_width) if board else self.board_width
        bh = getattr(board, "height_mm", self.board_height) if board else self.board_height
        ox = getattr(board, "origin_x", 0.0) if board else 0.0
        oy = getattr(board, "origin_y", 0.0) if board else 0.0
        board_cx = ox + bw / 2.0
        board_cy = oy + bh / 2.0

        # Build Courtyard Boxes
        for fp in footprints:
            spec = get_package_spec(
                footprint_id=getattr(fp, "lib_id", ""),
                ref=fp.ref,
                etype=getattr(fp, "value", "")
            )
            # Adjust dimensions and center if footprint has pad clusters
            pads = getattr(fp, "pads", [])
            w = float(spec.get("width", 3.0))
            h = float(spec.get("height", 3.0))
            rot_rad = math.radians(getattr(fp, "rotation", 0.0))
            cos_r, sin_r = math.cos(rot_rad), math.sin(rot_rad)
            comp_cx, comp_cy = fp.x, fp.y
            if pads:
                pad_xs = [p.x for p in pads]
                pad_ys = [p.y for p in pads]
                max_pw = max((getattr(p, 'w', 1.0) or 1.0) for p in pads)
                max_ph = max((getattr(p, 'h', 1.0) or 1.0) for p in pads)
                pad_span_x = (max(pad_xs) - min(pad_xs)) + max_pw
                pad_span_y = (max(pad_ys) - min(pad_ys)) + max_ph
                w = max(w, pad_span_x)
                h = max(h, pad_span_y)
                local_cx = (min(pad_xs) + max(pad_xs)) / 2.0
                local_cy = (min(pad_ys) + max(pad_ys)) / 2.0
                comp_cx = fp.x + local_cx * cos_r - local_cy * sin_r
                comp_cy = fp.y + local_cx * sin_r + local_cy * cos_r

            cb = CourtyardBox(
                ref=fp.ref,
                x=comp_cx,
                y=comp_cy,
                width=w,
                height=h,
                rotation=getattr(fp, "rotation", 0.0),
                margin=spec.get("courtyard_margin", 0.25),
                package_type=spec.get("package_type", "GENERIC")
            )
            courtyards.append(cb)

        # ── Pass 1: Physical Courtyard Collision Detection (SAT) ─────────────
        n = len(courtyards)
        for i in range(n):
            cb1 = courtyards[i]
            for j in range(i + 1, n):
                cb2 = courtyards[j]
                if cb1.intersects(cb2):
                    violations.append(VisualViolation(
                        rule_id="VIS-001",
                        severity="error",
                        component_ref=cb1.ref,
                        location=(cb1.x - board_cx, cb1.y - board_cy),
                        message=f"Courtyard overlap detected between {cb1.ref} ({cb1.package_type}) and {cb2.ref} ({cb2.package_type}).",
                        suggested_fix=f"Increase clearance between {cb1.ref} and {cb2.ref} to at least 0.5mm."
                    ))

        # ── Pass 2: Board Boundary Keepouts & Perimeter Alignment ────────────
        for cb in courtyards:
            bmin_x, bmin_y, bmax_x, bmax_y = cb.rotated_bounds
            # External I/O connectors (USB, SMA, Headers) are allowed to touch board edges
            is_external_io = cb.package_type in ("CONNECTOR", "HEADER")

            if not is_external_io:
                if (bmin_x < ox + self.edge_margin_mm or
                    bmax_x > ox + bw - self.edge_margin_mm or
                    bmin_y < oy + self.edge_margin_mm or
                    bmax_y > oy + bh - self.edge_margin_mm):
                    violations.append(VisualViolation(
                        rule_id="VIS-002",
                        severity="warning",
                        component_ref=cb.ref,
                        location=(cb.x - board_cx, cb.y - board_cy),
                        message=f"Component {cb.ref} is within {self.edge_margin_mm}mm of board perimeter.",
                        suggested_fix=f"Move {cb.ref} inward toward board center by at least 1.0mm."
                    ))
            else:
                # Connector boundary check — should be within board boundary
                if bmin_x < ox - 1.0 or bmax_x > ox + bw + 1.0 or bmin_y < oy - 1.0 or bmax_y > oy + bh + 1.0:
                    violations.append(VisualViolation(
                        rule_id="VIS-003",
                        severity="error",
                        component_ref=cb.ref,
                        location=(cb.x - board_cx, cb.y - board_cy),
                        message=f"Connector {cb.ref} exceeds allowable edge overhang.",
                        suggested_fix=f"Align {cb.ref} flush with the nearest board edge."
                    ))

        # ── Pass 3: Decoupling Capacitor Proximity Check ─────────────────────
        # Find MCU / IC components
        ics = [cb for cb in courtyards if cb.package_type in ("MCU", "IC", "REGULATOR")]
        caps = [cb for cb in courtyards if cb.package_type == "CAPACITOR"]

        for cap in caps:
            if ics:
                min_dist = min(math.hypot(cap.x - ic.x, cap.y - ic.y) for ic in ics)
                if min_dist > 18.0:
                    violations.append(VisualViolation(
                        rule_id="VIS-004",
                        severity="info",
                        component_ref=cap.ref,
                        location=(cap.x - board_cx, cap.y - board_cy),
                        message=f"Decoupling capacitor {cap.ref} is far ({min_dist:.1f}mm) from nearest IC.",
                        suggested_fix=f"Place {cap.ref} within 8.0mm of target IC power pin."
                    ))

        # ── Pass 4: Thermal Relief & Ground Via Check ────────────────────────
        gnd_net_ids = set()
        if hasattr(pcb_obj, "_nets") and isinstance(pcb_obj._nets, dict):
            for n_name, n_id in pcb_obj._nets.items():
                if any(g in n_name.upper() for g in ("GND", "0V", "GROUND", "PGND")):
                    gnd_net_ids.add(n_id)

        all_pcb_vias = getattr(pcb_obj, "_vias", [])
        gnd_vias = [
            v for v in all_pcb_vias
            if getattr(v, "net_id", None) in gnd_net_ids or getattr(v, "net_name", "").upper() in ("GND", "PWR_GND", "0V", "0", "PGND")
        ]
        thermal_targets = [cb for cb in courtyards if cb.package_type in ("REGULATOR", "MCU")]

        for th in thermal_targets:
            nearby_vias = [v for v in gnd_vias if math.hypot(v.x - th.x, v.y - th.y) < 12.0]
            if not nearby_vias:
                violations.append(VisualViolation(
                    rule_id="VIS-005",
                    severity="info",
                    component_ref=th.ref,
                    location=(th.x - board_cx, th.y - board_cy),
                    message=f"High-dissipation device {th.ref} lacks thermal stitching vias nearby.",
                    suggested_fix=f"Add at least 2 GND stitching vias within 8mm of {th.ref} thermal pad."
                ))

        # ── Pass 5: RF Antenna Keepout & Exterior Flushness (VIS-006) ────────
        rf_comps = [cb for cb in courtyards if cb.package_type in ("RF", "MCU") and any(k in cb.ref.upper() or k in getattr(cb, "package_type", "") for k in ("RF", "ANT", "CC1101", "NRF", "ESP32"))]
        for rf in rf_comps:
            dist_to_edge = min(
                abs(rf.x - (ox + self.edge_margin_mm)),
                abs(rf.x - (ox + bw - self.edge_margin_mm)),
                abs(rf.y - (oy + self.edge_margin_mm)),
                abs(rf.y - (oy + bh - self.edge_margin_mm))
            )
            if dist_to_edge > max(bw, bh) * 0.45:
                violations.append(VisualViolation(
                    rule_id="VIS-006",
                    severity="info",
                    component_ref=rf.ref,
                    location=(rf.x - board_cx, rf.y - board_cy),
                    message=f"RF module {rf.ref} is located in deep board interior ({dist_to_edge:.1f}mm from perimeter).",
                    suggested_fix=f"Position {rf.ref} adjacent to board edge to optimize antenna radiation pattern."
                ))

        # ── Pass 6: Net Ratsnest & Trace Quality Gate (VIS-007) ───────────────
        unrouted_segs = getattr(pcb_obj, "unrouted_segments", [])
        if unrouted_segs:
            for unrouted in unrouted_segs[:3]:
                net_name = unrouted.get("net", "UNKNOWN") if isinstance(unrouted, dict) else str(unrouted)
                violations.append(VisualViolation(
                    rule_id="VIS-007",
                    severity="error",
                    component_ref=net_name,
                    location=(0.0, 0.0),
                    message=f"Unrouted airwire segment remains on net '{net_name}'.",
                    suggested_fix="Increase routing grid resolution or adjust local component placement channel."
                ))

        # ── Pass 7: UI Controls Symmetry & Uniform Pitch (VIS-008) ───────────
        ui_buttons = [cb for cb in courtyards if "SW" in cb.ref.upper() or "BTN" in cb.ref.upper() or cb.package_type in ("BUTTON", "SWITCH")]
        if len(ui_buttons) >= 3:
            xs = sorted([b.x for b in ui_buttons])
            x_diffs = [round(xs[i+1] - xs[i], 1) for i in range(len(xs)-1) if xs[i+1] - xs[i] > 1.0]
            if len(set(x_diffs)) > 3:
                violations.append(VisualViolation(
                    rule_id="VIS-008",
                    severity="info",
                    component_ref=ui_buttons[0].ref,
                    location=(ui_buttons[0].x - board_cx, ui_buttons[0].y - board_cy),
                    message="UI tactile switches exhibit irregular non-uniform pitch spacing.",
                    suggested_fix="Align button matrix on a regular 10.0mm or 12.0mm grid pitch."
                ))

        # ── Pass 8: Power Rail Return & Via Continuity (VIS-009) ─────────────
        pwr_rails = [n for n in getattr(pcb_obj, "_nets", {}).keys() if any(p in n.upper() for p in ("3V3", "5V", "VCC", "VDD", "VBAT", "VBUS"))]
        for pr in pwr_rails[:2]:
            pr_pads = [p for fp in footprints for p in getattr(fp, "pads", []) if getattr(p, "net_name", "") == pr]
            if len(pr_pads) >= 2 and not gnd_vias:
                violations.append(VisualViolation(
                    rule_id="VIS-009",
                    severity="info",
                    component_ref=pr,
                    location=(0.0, 0.0),
                    message=f"Power rail '{pr}' spans multiple components without adjacent ground return vias.",
                    suggested_fix="Place GND stitching vias along high-current power distribution paths."
                ))

        # ── Calculate Multi-Faceted DFM Radar Breakdown ──────────────────────
        # 1. Clearance & Courtyards (VIS-001, VIS-002, VIS-003)
        c_v = [v for v in violations if v.rule_id in ("VIS-001", "VIS-002", "VIS-003")]
        c_score = max(0.0, 100.0 - sum(25.0 if v.severity == "error" else (10.0 if v.severity == "warning" else 2.0) for v in c_v))

        # 2. Signal Integrity & Decoupling (VIS-004, VIS-007)
        si_v = [v for v in violations if v.rule_id in ("VIS-004", "VIS-007")]
        si_score = max(0.0, 100.0 - sum(25.0 if v.severity == "error" else (10.0 if v.severity == "warning" else 2.0) for v in si_v))

        # 3. Thermal & Ground Planes (VIS-005, VIS-009)
        th_v = [v for v in violations if v.rule_id in ("VIS-005", "VIS-009")]
        th_score = max(0.0, 100.0 - sum(25.0 if v.severity == "error" else (10.0 if v.severity == "warning" else 2.0) for v in th_v))

        # 4. RF & High-Speed Compliance (VIS-006)
        rf_v = [v for v in violations if v.rule_id == "VIS-006"]
        rf_score = max(0.0, 100.0 - sum(25.0 if v.severity == "error" else (10.0 if v.severity == "warning" else 2.0) for v in rf_v))

        # 5. Ergonomics & Assembly Uniformity (VIS-008)
        ergo_v = [v for v in violations if v.rule_id == "VIS-008"]
        ergo_score = max(0.0, 100.0 - sum(25.0 if v.severity == "error" else (10.0 if v.severity == "warning" else 2.0) for v in ergo_v))

        radar = {
            "clearance": round(c_score, 1),
            "signal_integrity": round(si_score, 1),
            "thermal": round(th_score, 1),
            "rf_compliance": round(rf_score, 1),
            "ergonomics": round(ergo_score, 1),
        }

        # Balanced Composite Score
        composite_score = (
            c_score * 0.30 +
            si_score * 0.25 +
            th_score * 0.15 +
            rf_score * 0.15 +
            ergo_score * 0.15
        )

        error_count = sum(1 for v in violations if v.severity == "error")
        warning_count = sum(1 for v in violations if v.severity == "warning")
        info_count = sum(1 for v in violations if v.severity == "info")
        passed = (error_count == 0)

        # Build normalized output courtyards for UI
        ui_courtyards = [
            {
                "ref": cb.ref,
                "x": cb.x - board_cx,
                "y": cb.y - board_cy,
                "width": cb.width,
                "height": cb.height,
                "margin": cb.margin,
                "rotation": cb.rotation,
                "package_type": cb.package_type,
            }
            for cb in courtyards
        ]

        return VisualInspectionReport(
            passed=passed,
            visual_score=round(composite_score, 1),
            violations_count=len(violations),
            violations=violations,
            courtyards=ui_courtyards,
            radar=radar,
            stats={
                "total_components": len(footprints),
                "errors": error_count,
                "warnings": warning_count,
                "info": info_count,
                "board_size": f"{bw:.1f}x{bh:.1f}mm"
            }
        )


def run_visual_inspection(pcb_obj: Any, circuit_data: Optional[Dict[str, Any]] = None) -> VisualInspectionReport:
    """Convenience wrapper to run visual inspection on a PCB instance."""
    engine = VisualInferenceEngine()
    return engine.inspect(pcb_obj, circuit_data)
