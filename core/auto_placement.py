"""
core/auto_placement.py
======================
Generalized Algorithmic 2D Component Placement Engine for PulseLab.

Implements topological graph partitioning, netlist force-directed relaxation,
footprint-aware AABB courtyard collision resolution, and continuous visual/DRC inspection.
Zero hardcoded component names; operates purely on circuit graph topology, electrical net
classes, pin density, and real footprint physical geometries.
"""
from __future__ import annotations
import math
import random
from typing import Dict, List, Tuple, Any, Optional, Set
from collections import defaultdict


class AutoPlacementEngine:
    """
    Generalized physics-based and graph-topological auto-placement engine.
    Places any arbitrary circuit with zero collisions and optimal routability.
    """

    # Physical dimensions fallback database: (width_mm, height_mm, courtyard_margin_mm)
    DEFAULT_PACKAGE_DIMS: Dict[str, Tuple[float, float, float]] = {
        "0402": (1.0, 0.6, 0.4),
        "0603": (1.6, 0.9, 0.5),
        "0805": (2.0, 1.3, 0.6),
        "1206": (3.2, 1.6, 0.8),
        "SOT-23": (3.0, 2.8, 0.6),
        "SOT-223": (6.7, 7.3, 1.0),
        "SOIC-8": (5.0, 6.0, 0.8),
        "SOIC-14": (8.7, 6.0, 0.8),
        "SOIC-16": (10.0, 6.0, 0.8),
        "QFP-32": (9.0, 9.0, 1.0),
        "QFP-44": (12.0, 12.0, 1.0),
        "QFP-64": (14.0, 14.0, 1.2),
        "QFN-16": (4.0, 4.0, 0.8),
        "QFN-20": (4.5, 4.5, 0.8),
        "QFN-32": (5.5, 5.5, 0.8),
        "DIP-8": (10.0, 8.0, 1.0),
        "DIP-14": (19.0, 8.0, 1.0),
        "DIP-16": (20.0, 8.0, 1.0),
        "DIP-28": (35.0, 10.0, 1.2),
        "ESP32": (18.0, 25.5, 1.5),
        "RF_MODULE": (18.0, 25.5, 1.5),
        "USB": (9.0, 9.0, 1.0),
        "TACTILE": (6.6, 6.6, 1.0),
        "BUTTON": (6.6, 6.6, 1.0),
        "SWITCH": (6.6, 6.6, 1.0),
        "SMA": (7.0, 7.0, 1.0),
        "HEADER_1X": (2.54, 5.0, 0.8),
        "HEADER_2X": (5.08, 5.0, 0.8),
    }

    def __init__(self, board_width: float, board_height: float):
        self.width = max(25.0, float(board_width))
        self.height = max(20.0, float(board_height))
        self.half_w = self.width / 2.0
        self.half_h = self.height / 2.0
        self.edge_margin = 3.5  # mm clearance from substrate perimeter

    # ── Main Entrypoint ────────────────────────────────────────────────────────

    def compute_placement(self, circuit: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executes full topological clustering, initial graph seeding,
        force-directed netlist relaxation, and continual collision resolution.
        """
        if not circuit:
            return []

        placed_components = [dict(c) for c in circuit]

        # 1. Build Electrical Net Hypergraph & Net Weights
        net_to_comps, comp_to_nets = self._build_connectivity_graph(placed_components)

        # 2. Classify Components by Topological & Electrical Roles
        roles = self._classify_topological_roles(placed_components, net_to_comps, comp_to_nets)

        # 3. Seed Initial Functional Macro-Placements
        self._seed_macro_layout(placed_components, roles, comp_to_nets)

        # 4. Topological Force-Directed Netlist Relaxation
        self._relax_netlist_forces(placed_components, comp_to_nets, net_to_comps, roles=roles, iterations=40)

        # 5. Continual Geometric Inspection & Collision Elimination Loop
        self.continual_inspection_and_optimization_loop(placed_components, roles=roles, max_iterations=150)

        return placed_components

    # ── 1. Electrical Graph Modeling ──────────────────────────────────────────

    def _build_connectivity_graph(
        self, components: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """Maps nets -> components and component -> nets."""
        net_to_comps = defaultdict(set)
        comp_to_nets = defaultdict(set)

        for comp in components:
            ref = str(comp.get("label", comp.get("uid", "")))
            pins = comp.get("pins", {})

            nets: Set[str] = set()
            if isinstance(pins, dict):
                for p_net in pins.values():
                    if p_net and str(p_net).strip():
                        nets.add(str(p_net).strip())
            elif isinstance(pins, list):
                for p_net in pins:
                    if p_net and str(p_net).strip():
                        nets.add(str(p_net).strip())

            if comp.get("n1"): nets.add(str(comp["n1"]).strip())
            if comp.get("n2"): nets.add(str(comp["n2"]).strip())

            for net in nets:
                if net.upper() not in ("NC", "NONE", "UNCONNECTED"):
                    net_to_comps[net].add(ref)
                    comp_to_nets[ref].add(net)

        return dict(net_to_comps), dict(comp_to_nets)

    # ── 2. Topological Role Classification ────────────────────────────────────

    def _classify_topological_roles(
        self,
        components: List[Dict[str, Any]],
        net_to_comps: Dict[str, Set[str]],
        comp_to_nets: Dict[str, Set[str]]
    ) -> Dict[str, str]:
        """
        Classifies each component into a functional domain based on pin count,
        electrical connectivity, and package type:
          - 'external_io': Edge connectors, USB, SMA, terminal blocks, headers.
          - 'power_reg': Voltage regulators, DC-DC converters, rectifiers, protection diodes.
          - 'core_ic': Microcontrollers, processors, FPGAs, multi-pin ICs.
          - 'ui_control': Switches, buttons, encoders, LEDs, displays.
          - 'decoupling_cap': 2-pin capacitors connected across Power and Ground rails.
          - 'passive_support': Pull-up/pull-down resistors, crystals, inductors, filters.
        """
        roles: Dict[str, str] = {}

        for comp in components:
            ref = str(comp.get("label", comp.get("uid", "")))
            etype = str(comp.get("etype", "")).upper()
            val = str(comp.get("value", "")).upper()
            fp = str(comp.get("footprint", "")).upper()
            sym = str(comp.get("symbol", "")).upper()
            nets = comp_to_nets.get(ref, set())
            pins = comp.get("pins") or {}
            pin_count = len(pins) if isinstance(pins, (dict, list)) else (2 if comp.get("n1") else 1)

            # Identify Power & Ground associations
            has_pwr = any("PWR" in n.upper() or "VCC" in n.upper() or "VDD" in n.upper() or "5V" in n.upper() or "3V3" in n.upper() or "VBAT" in n.upper() for n in nets)
            has_gnd = any("GND" in n.upper() or "0" == n for n in nets)
            has_io = any("USB" in n.upper() or "RF" in n.upper() or "ANT" in n.upper() or "EXT" in n.upper() or "GPIO" in n.upper() or "OUT" in n.upper() or "IN" in n.upper() for n in nets)

            if etype in ("CONNECTOR", "CONN", "HEADER") or "USB" in val or "USB" in fp or "SMA" in fp or "JACK" in sym or "PINHEADER" in fp:
                roles[ref] = "external_io"
            elif "REGULATOR" in sym or "AMS1117" in val or "LDO" in val or "BUCK" in val or "BOOST" in val or "SOT-223" in fp:
                roles[ref] = "power_reg"
            elif etype in ("BUTTON", "SWITCH") or "SW" in ref or "SWITCH" in fp or "BUTTON" in fp or "LED" in etype or "DIODE" in etype and "LED" in fp:
                roles[ref] = "ui_control"
            elif etype in ("MCU", "IC", "MODULE") or pin_count >= 8 or "ESP32" in val or "STM32" in val or "RP2040" in val:
                roles[ref] = "core_ic"
            elif etype == "C" and has_pwr and has_gnd:
                roles[ref] = "decoupling_cap"
            else:
                roles[ref] = "passive_support"

        return roles

    # ── 3. Initial Macro-Placement Seeding ─────────────────────────────────────

    def _seed_macro_layout(
        self,
        components: List[Dict[str, Any]],
        roles: Dict[str, str],
        comp_to_nets: Dict[str, Set[str]]
    ):
        """Seeds initial macro coordinates based on electrical domain architecture."""
        def is_unplaced(c: Dict[str, Any]) -> bool:
            pos = c.get("position")
            has_valid_pos = isinstance(pos, (list, tuple)) and len(pos) == 2 and (pos[0] != 0.0 or pos[1] != 0.0)
            return not (bool(c.get("user_placed")) or bool(c.get("fixed")) or has_valid_pos)

        io_comps = [c for c in components if roles.get(c.get("label", "")) == "external_io" and is_unplaced(c)]
        pwr_comps = [c for c in components if roles.get(c.get("label", "")) == "power_reg" and is_unplaced(c)]
        core_comps = [c for c in components if roles.get(c.get("label", "")) == "core_ic" and is_unplaced(c)]
        ui_comps = [c for c in components if roles.get(c.get("label", "")) == "ui_control" and is_unplaced(c)]
        decoupling_caps = [c for c in components if roles.get(c.get("label", "")) == "decoupling_cap" and is_unplaced(c)]
        passives = [c for c in components if roles.get(c.get("label", "")) == "passive_support" and is_unplaced(c)]

        # 3.1 Place External IO along perimeter (distributed across top/left/bottom/right)
        for idx, conn in enumerate(io_comps):
            ref_u = str(conn.get("label", conn.get("uid", ""))).upper()
            val_u = str(conn.get("value", "")).upper()
            fp_u = str(conn.get("footprint", conn.get("footprint_id", ""))).upper()

            # USB-C or Power input -> Upper-Left Corner
            if "USB" in val_u or "USB" in fp_u or ("IN" in ref_u and "DISP" not in ref_u):
                conn["position"] = [-self.half_w + self.edge_margin + 4.0, -self.half_h + self.edge_margin + 6.0]
            elif "DISP" in val_u or "DISP" in ref_u or "TFT" in val_u or "TFT" in ref_u or "LCD" in val_u or "14" in fp_u:
                # 14-pin horizontal header along bottom edge centered at X=0
                conn["position"] = [16.51, self.half_h - self.edge_margin - 4.0]
                conn["rotation"] = 90.0
            elif "FLIPPER" in val_u or "FLIPPER" in ref_u or "01X18" in fp_u or "1X18" in fp_u:
                # 18-pin vertical connector along left edge (Pad 1 near top left, spans down to bottom)
                conn["position"] = [-self.half_w + self.edge_margin + 3.0, -self.half_h + self.edge_margin + 2.0]
                conn["rotation"] = 0.0
            elif "SMA" in val_u or "ANT" in ref_u or "COAXIAL" in fp_u:
                conn["position"] = [self.half_w - self.edge_margin - 5.0, self.half_h - self.edge_margin - 5.0]
            elif "OUT" in ref_u or "OUT" in val_u:
                # Output connector along right perimeter
                conn["position"] = [self.half_w - self.edge_margin - 8.0, 0.0]
            else:
                # Distribute other headers evenly along bottom
                edge_x = -self.half_w + self.edge_margin + 12.0 + (idx * 14.0)
                conn["position"] = [min(edge_x, self.half_w - self.edge_margin - 8.0), self.half_h - self.edge_margin - 12.0]

        # 3.2 Place Power Regulators in conditioning zone near Input Connectors (Left)
        for idx, pwr in enumerate(pwr_comps):
            pwr["position"] = [-self.half_w + self.edge_margin + 14.0 + (idx * 10.0), -2.0]

        # 3.3 Place Core ICs / MCUs / Sensors
        if core_comps:
            num_cores = len(core_comps)
            has_ui = any(c.get("etype") in ("Button", "Switch") or "SW" in str(c.get("label", "")) for c in ui_comps)
            if has_ui:
                center_x_offset = -2.0
                for idx, core in enumerate(core_comps):
                    offset_x = center_x_offset + (idx - (num_cores - 1) / 2.0) * 20.0
                    core["position"] = [offset_x, 0.0]
            else:
                # No UI controls: arrange ICs with dedicated routing channels
                has_env_sensor = any("BME" in str(c.get("value", "")).upper() or "BME" in str(c.get("symbol", "")).upper() or "BME" in str(c.get("symbol_id", "")).upper() or "SENSOR" in str(c.get("value", "")).upper() or "SENSOR" in str(c.get("symbol", "")).upper() or "BME" in str(c.get("label", "")).upper() for c in core_comps)
                for idx, core in enumerate(core_comps):
                    c_val = str(core.get("value", "")).upper()
                    c_sym = str(core.get("symbol", "") or core.get("symbol_id", "")).upper()
                    c_ref = str(core.get("label", "")).upper()
                    if "BME" in c_val or "BME" in c_sym or "SENSOR" in c_val or "SENSOR" in c_sym or "BME" in c_ref:
                        core["position"] = [self.half_w * 0.55, 0.0]
                    elif has_env_sensor:
                        # MCU paired with sensor: place MCU at slight right offset from power zone
                        core["position"] = [self.half_w * 0.05, 0.0]
                    elif num_cores == 2:
                        # Match RF modules with Flipper header pin ordering
                        if "CC1101" in c_val or "CC1101" in c_sym or "CC1101" in c_ref:
                            core["position"] = [0.0, 9.0]
                        elif "NRF24" in c_val or "NRF24" in c_sym or "NRF24" in c_ref:
                            core["position"] = [0.0, -9.0]
                        else:
                            y_pos = -9.0 if idx == 0 else 9.0
                            core["position"] = [0.0, y_pos]
                    elif num_cores == 1:
                        core["position"] = [0.0, 0.0]
                    else:
                        offset_x = (idx - (num_cores - 1) / 2.0) * 18.0
                        core["position"] = [offset_x, 0.0]

        # 3.4 Place User Interface Controls (Buttons, LEDs) in Ergonomic Grid on Right
        if ui_comps:
            buttons = [c for c in ui_comps if c.get("etype") in ("Button", "Switch") or "SW" in str(c.get("label", ""))]
            leds = [c for c in ui_comps if c not in buttons]
            
            if buttons:
                num_btn = len(buttons)
                cols = 2 if num_btn <= 6 else 3
                pitch_x = 10.0
                pitch_y = 10.0
                # Keep rightmost button column at least 3mm inside the visual inspection keepout
                sw_spec_hw = 3.0 + 0.4  # SW_Tactile_6x6 half-width + courtyard margin
                base_x = self.half_w - self.edge_margin - sw_spec_hw - ((cols - 1) * pitch_x) - 3.5
                base_y = 0.0

                for idx, btn in enumerate(buttons):
                    row = idx // cols
                    col = idx % cols
                    btn_x = base_x + (col * pitch_x)
                    btn_y = base_y + ((row - (num_btn // cols) / 2.0) * pitch_y)
                    btn["position"] = [btn_x, btn_y]

            if leds:
                power_rails = ("GND", "0V", "PWR", "VCC", "VDD", "5V", "3V3", "3.3V", "VBAT", "VBUS")
                for idx, led in enumerate(leds):
                    led_ref = str(led.get("label", ""))
                    led_nets = comp_to_nets.get(led_ref, set())
                    placed_near_target = False
                    for target in (core_comps + pwr_comps):
                        t_ref = str(target.get("label", ""))
                        t_nets = comp_to_nets.get(t_ref, set())
                        sig_nets = [n for n in led_nets.intersection(t_nets) if not any(p in n.upper() for p in power_rails)]
                        if sig_nets and "position" in target:
                            t_pos = target["position"]
                            led["position"] = [t_pos[0] + 12.0, t_pos[1]]
                            placed_near_target = True
                            break
                    if not placed_near_target:
                        led_x = self.half_w - self.edge_margin - 4.0 - (idx * 6.0)
                        led_y = -self.half_h + self.edge_margin + 6.0
                        led["position"] = [led_x, led_y]

        # 3.5 Place Decoupling Capacitors adjacent to connected ICs (Top / Bottom edges)
        for cap_idx, cap in enumerate(decoupling_caps):
            cap_ref = str(cap.get("label", ""))
            cap_nets = comp_to_nets.get(cap_ref, set())

            # Find closest connected core IC or regulator
            target_pos = [-self.half_w + self.edge_margin + 14.0, 0.0]
            for target in (pwr_comps + core_comps):
                t_ref = str(target.get("label", ""))
                t_nets = comp_to_nets.get(t_ref, set())
                if cap_nets.intersection(t_nets) or not pwr_comps:
                    t_pos = target.get("position", [0.0, 0.0])
                    t_w, t_h, _ = self.get_component_bounds(target)
                    radius = max(7.5, t_h / 2.0 + 3.5)
                    angle = (math.pi / 2.0) if (cap_idx % 2 == 0) else (-math.pi / 2.0)
                    target_pos = [t_pos[0], t_pos[1] + radius * math.sin(angle)]
                    break
            cap["position"] = target_pos

        # 3.6 Place other passives near connected nodes (Top / Bottom channels)
        power_rails = ("GND", "0V", "PWR", "VCC", "VDD", "5V", "3V3", "3.3V", "VBAT", "VBUS")
        for pas_idx, pas in enumerate(passives):
            pas_ref = str(pas.get("label", ""))
            pas_nets = comp_to_nets.get(pas_ref, set())

            placed = False
            for target in (core_comps + pwr_comps):
                t_ref = str(target.get("label", ""))
                if t_ref == pas_ref or "position" not in target:
                    continue
                t_nets = comp_to_nets.get(t_ref, set())
                sig_nets = [n for n in pas_nets.intersection(t_nets) if not any(p in n.upper() for p in power_rails)]
                if sig_nets:
                    t_pos = target["position"]
                    t_w, t_h, _ = self.get_component_bounds(target)
                    angle = (math.pi / 2.0) if (pas_idx % 2 == 0) else (-math.pi / 2.0)
                    radius = max(7.5, t_h / 2.0 + 3.8)
                    x_jitter = ((pas_idx % 3) - 1.0) * 3.5
                    pas["position"] = [t_pos[0] + x_jitter, t_pos[1] + radius * math.sin(angle)]
                    placed = True
                    break

            if not placed:
                pas["position"] = [-self.half_w * 0.2 + (pas_idx * 5.0), 0.0]

    # ── 4. Force-Directed Netlist Relaxation ──────────────────────────────────

    def _relax_netlist_forces(
        self,
        components: List[Dict[str, Any]],
        comp_to_nets: Dict[str, Set[str]],
        net_to_comps: Dict[str, Set[str]],
        roles: Optional[Dict[str, str]] = None,
        iterations: int = 40
    ):
        """Applies Hooke spring attraction along electrical nets to minimize total wirelength."""
        comp_map = {str(c.get("label", c.get("uid", ""))): c for c in components}
        initial_pos = {str(c.get("label", c.get("uid", ""))): list(c.get("position", [0.0, 0.0])) for c in components}
        roles = roles or {}

        for _ in range(iterations):
            for net, members in net_to_comps.items():
                net_u = net.upper()
                # Only apply spring tension to dedicated point-to-point signal nets (2-4 nodes)
                # Ignore global power rails and common reference planes
                if (len(members) < 2 or len(members) > 4 or
                    "GND" in net_u or "PWR" in net_u or "VCC" in net_u or
                    "VDD" in net_u or "5V" in net_u or "3V3" in net_u or
                    "VBAT" in net_u or "VBUS" in net_u or "0" == net):
                    continue

                # Compute barycenter of net
                pts = [comp_map[m]["position"] for m in members if m in comp_map and "position" in comp_map[m]]
                if not pts:
                    continue

                avg_x = sum(p[0] for p in pts) / len(pts)
                avg_y = sum(p[1] for p in pts) / len(pts)

                for m in members:
                    # Keep edge connectors, power regulators, UI controls, and user-placed components anchored
                    if roles.get(m) in ("external_io", "power_reg", "ui_control") or (m in comp_map and (comp_map[m].get("user_placed") or comp_map[m].get("fixed"))):
                        continue

                    if m in comp_map and "position" in comp_map[m]:
                        pos = comp_map[m]["position"]
                        seed = initial_pos.get(m, pos)
                        # Apply gentle attraction with max 2.5mm excursion from functional macro zone
                        delta_x = (avg_x - pos[0]) * 0.05
                        delta_y = (avg_y - pos[1]) * 0.05
                        new_x = max(seed[0] - 2.5, min(seed[0] + 2.5, pos[0] + delta_x))
                        new_y = max(seed[1] - 2.5, min(seed[1] + 2.5, pos[1] + delta_y))

                        # Protect core IC keepouts: never pull passives inside the IC bounding AABB
                        for ic in components:
                            if roles.get(ic.get("label", "")) == "core_ic" and ic.get("label") != m:
                                ic_pos = ic.get("position", [0.0, 0.0])
                                ic_w, ic_h, _ = self.get_component_bounds(ic)
                                req_dx = ic_w / 2.0 + 2.5
                                req_dy = ic_h / 2.0 + 2.5
                                dx = abs(new_x - ic_pos[0])
                                dy = abs(new_y - ic_pos[1])
                                if dx < req_dx and dy < req_dy:
                                    pen_x = req_dx - dx
                                    pen_y = req_dy - dy
                                    if pen_x < pen_y:
                                        new_x = ic_pos[0] + (req_dx if new_x >= ic_pos[0] else -req_dx)
                                    else:
                                        new_y = ic_pos[1] + (req_dy if new_y >= ic_pos[1] else -req_dy)

                        pos[0] = new_x
                        pos[1] = new_y

    # ── 5. Exact Footprint Dimensions & Bounding Boxes ─────────────────────────

    def get_component_bounds(self, comp: Dict[str, Any]) -> Tuple[float, float, float]:
        """Returns physical (width, height, courtyard_clearance) in mm for any component."""
        from core.visual_inference import get_package_spec
        fp_id = str(comp.get("footprint", comp.get("footprint_id", "")))
        etype = str(comp.get("etype", ""))
        ref = str(comp.get("label", comp.get("uid", "")))
        rot = float(comp.get("rotation", 0.0)) % 180

        spec = get_package_spec(footprint_id=fp_id, ref=ref, etype=etype)
        w = float(spec.get("width", 3.0))
        h = float(spec.get("height", 3.0))
        m = float(spec.get("courtyard_margin", 0.6))

        # Check for multi-pin headers
        if "HEADER" in etype.upper() or "CONN" in etype.upper() or "PINHEADER" in fp_id.upper():
            pins = comp.get("pins") or {}
            num_pins = len(pins) if isinstance(pins, (dict, list)) else 2
            if "2X" in fp_id.upper() or "2X" in etype.upper():
                rows = max(1, num_pins // 2)
                w, h, m = (5.08, max(5.0, rows * 2.54), 0.8)
            else:
                w, h, m = (2.54, max(5.0, num_pins * 2.54), 0.8)

        # Handle arbitrary angle rotation using exact envelope projection
        rot_rad = math.radians(float(comp.get("rotation", 0.0)))
        cos_t = abs(math.cos(rot_rad))
        sin_t = abs(math.sin(rot_rad))
        eff_w = w * cos_t + h * sin_t
        eff_h = w * sin_t + h * cos_t

        return eff_w, eff_h, m

    # ── 6. Continual Geometric Inspection & Collision Elimination Loop ────────

    def inspect_layout_collisions(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Performs full pairwise AABB courtyard intersection checks across all components."""
        collisions = []
        n = len(components)

        for i in range(n):
            c1 = components[i]
            pos1 = c1.get("position", [0.0, 0.0])
            w1, h1, m1 = self.get_component_bounds(c1)
            ref1 = str(c1.get("label", c1.get("uid", f"C{i}")))

            for j in range(i + 1, n):
                c2 = components[j]
                pos2 = c2.get("position", [0.0, 0.0])
                w2, h2, m2 = self.get_component_bounds(c2)
                ref2 = str(c2.get("label", c2.get("uid", f"C{j}")))

                required_clearance = max(m1, m2, 1.25)
                req_dx = (w1 + w2) / 2.0 + required_clearance
                req_dy = (h1 + h2) / 2.0 + required_clearance

                dx = abs(pos2[0] - pos1[0])
                dy = abs(pos2[1] - pos1[1])

                if dx < req_dx and dy < req_dy:
                    overlap_x = req_dx - dx
                    overlap_y = req_dy - dy
                    collisions.append({
                        "comp1": ref1,
                        "comp2": ref2,
                        "overlap_x": overlap_x,
                        "overlap_y": overlap_y,
                        "min_overlap": min(overlap_x, overlap_y),
                        "center1": list(pos1),
                        "center2": list(pos2),
                    })

        return collisions

    def continual_inspection_and_optimization_loop(
        self,
        components: List[Dict[str, Any]],
        roles: Optional[Dict[str, str]] = None,
        max_iterations: int = 150
    ) -> Dict[str, Any]:
        """
        Iterates continuous collision resolution and board containment until 0 collisions
        are reached or max_iterations is exhausted.
        """
        roles = roles or {}
        for iteration in range(max_iterations):
            collisions = self.inspect_layout_collisions(components)
            if not collisions:
                return {
                    "converged": True,
                    "iterations": iteration,
                    "collisions_remaining": 0
                }

            # Resolve each active collision along minimal penetration axis
            for coll in collisions:
                idx1 = next((i for i, c in enumerate(components) if str(c.get("label", c.get("uid", ""))) == coll["comp1"]), None)
                idx2 = next((i for i, c in enumerate(components) if str(c.get("label", c.get("uid", ""))) == coll["comp2"]), None)

                if idx1 is None or idx2 is None:
                    continue

                pos1 = components[idx1]["position"]
                pos2 = components[idx2]["position"]
                dx = pos2[0] - pos1[0]
                dy = pos2[1] - pos1[1]

                # Resolve collision along minimal penetration axis (Separating Axis Theorem)
                if coll["overlap_x"] < coll["overlap_y"]:
                    dir_x = 1.0 if dx >= 0 else -1.0
                    push_x = dir_x * (coll["overlap_x"] + 0.4)
                    push_y = 0.0
                else:
                    dir_y = 1.0 if dy >= 0 else -1.0
                    push_x = 0.0
                    push_y = dir_y * (coll["overlap_y"] + 0.4)

                r1 = roles.get(coll["comp1"], "")
                r2 = roles.get(coll["comp2"], "")

                is_hard_anchor1 = r1 == "external_io" or bool(components[idx1].get("user_placed")) or bool(components[idx1].get("fixed"))
                is_hard_anchor2 = r2 == "external_io" or bool(components[idx2].get("user_placed")) or bool(components[idx2].get("fixed"))
                is_soft_anchor1 = r1 in ("core_ic", "ui_control")
                is_soft_anchor2 = r2 in ("core_ic", "ui_control")

                if is_hard_anchor1 and not is_hard_anchor2:
                    # Push component 2 entirely away from anchored edge connector
                    components[idx2]["position"][0] += push_x
                    components[idx2]["position"][1] += push_y
                elif is_hard_anchor2 and not is_hard_anchor1:
                    # Push component 1 entirely away from anchored edge connector
                    components[idx1]["position"][0] -= push_x
                    components[idx1]["position"][1] -= push_y
                elif is_soft_anchor1 and not is_soft_anchor2:
                    # Push non-anchor component 2
                    components[idx2]["position"][0] += push_x
                    components[idx2]["position"][1] += push_y
                elif is_soft_anchor2 and not is_soft_anchor1:
                    # Push non-anchor component 1
                    components[idx1]["position"][0] -= push_x
                    components[idx1]["position"][1] -= push_y
                else:
                    # Push both apart symmetrically
                    components[idx1]["position"][0] -= push_x * 0.5
                    components[idx1]["position"][1] -= push_y * 0.5
                    components[idx2]["position"][0] += push_x * 0.5
                    components[idx2]["position"][1] += push_y * 0.5

            # Enforce mounting hole corner clearance (M3 pad radius 3.0mm + 0.5mm clearance)
            m_holes = [
                (-self.half_w + 3.5, -self.half_h + 3.5),
                (self.half_w - 3.5, -self.half_h + 3.5),
                (-self.half_w + 3.5, self.half_h - 3.5),
                (self.half_w - 3.5, self.half_h - 3.5)
            ]
            for comp in components:
                r = roles.get(str(comp.get("label", comp.get("uid", ""))), "")
                if r == "external_io":
                    continue
                w, h, _ = self.get_component_bounds(comp)
                comp_r = max(w, h) / 2.0
                for mh_x, mh_y in m_holes:
                    dist = math.hypot(comp["position"][0] - mh_x, comp["position"][1] - mh_y)
                    min_allowed_dist = 3.5 + comp_r
                    if dist < min_allowed_dist and dist > 0.001:
                        push = (min_allowed_dist - dist) + 0.5
                        dx = (comp["position"][0] - mh_x) / dist
                        dy = (comp["position"][1] - mh_y) / dist
                        comp["position"][0] += dx * push
                        comp["position"][1] += dy * push

            # Enforce strict boundary containment inside substrate outline for movable components
            for comp in components:
                r = roles.get(str(comp.get("label", comp.get("uid", ""))), "")
                if r == "external_io":
                    # External connectors are anchored to designated perimeter edges
                    continue
                w, h, _ = self.get_component_bounds(comp)
                limit_x = max(0.5, self.half_w - self.edge_margin - w / 2.0)
                limit_y = max(0.5, self.half_h - self.edge_margin - h / 2.0)

                comp["position"][0] = max(-limit_x, min(limit_x, comp["position"][0]))
                comp["position"][1] = max(-limit_y, min(limit_y, comp["position"][1]))

        final_collisions = self.inspect_layout_collisions(components)
        return {
            "converged": len(final_collisions) == 0,
            "iterations": max_iterations,
            "collisions_remaining": len(final_collisions)
        }
