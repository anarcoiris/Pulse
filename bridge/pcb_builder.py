"""
bridge/pcb_builder.py
=====================
Builder unificado para generación de PCBs.

Centraliza la lógica de generación que antes estaba duplicada entre
``forge_api.generate_pcb()`` y ``mcp_server/server.py::create_pcb_layout()``.

Dos entry-points:
  - ``from_circuit_graph(graph)`` — usado por la GUI y forge_api.
  - ``from_component_dicts(components, traces, ...)`` — usado por el MCP server / LLMs.

Ambos producen un ``PCBLayout`` con las mismas mejoras profesionales:
  - Auto-sizing de placa
  - Decoupling caps para ICs
  - Keepout zones para antenas ESP32
  - Copper pour GND
  - Auto-routing A*
  - Generación automática de esquemático (.kicad_sch)
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph

from bridge.pcb_layout import PCBLayout, Footprint
from knowledge.pulse_config import cfg as pulse_cfg
from core.logger import logger


def _pcb(key: str, default=None):
    return pulse_cfg(f"pcb.{key}", default)


class PCBBuilder:
    """Builder que produce un PCBLayout completo listo para exportar."""

    def __init__(
        self,
        board_width: Optional[float] = None,
        board_height: Optional[float] = None,
        project_name: str | None = None,
        corner_radius: float | None = None,
        trace_width: float | None = None,
        mounting_holes: bool | None = None,
        output_dir: str | None = None,
        net_classes: dict | None = None,
        skip_routing: bool = False,
    ):
        self.board_width = board_width
        self.board_height = board_height
        self.project_name = project_name or _pcb("project_name", "PulseLab Design")
        self.corner_radius = float(corner_radius if corner_radius is not None else _pcb("corner_radius_mm", 1.5))
        self.trace_width = float(trace_width if trace_width is not None else _pcb("trace_width_mm", 0.25))
        self.mounting_holes = mounting_holes if mounting_holes is not None else bool(_pcb("mounting_holes", True))
        self.output_dir = output_dir or _pcb("output_dir", "output")
        self.net_classes = net_classes or {}
        self.skip_routing = skip_routing
        self._pcb: Optional[PCBLayout] = None
        self._graph: Optional[CircuitGraph] = None

    # ── Builders ──────────────────────────────────────────────

    @classmethod
    def from_circuit_graph(
        cls,
        graph: "CircuitGraph",
        out_dir: str = "output",
        **kwargs,
    ) -> "PCBBuilder":
        """Construye un PCB a partir de un CircuitGraph completo."""
        builder = cls(output_dir=out_dir, **kwargs)
        builder._graph = graph
        builder._build_from_graph(graph)
        return builder

    @classmethod
    def from_component_dicts(
        cls,
        components: list[dict],
        traces: list[dict] | None = None,
        board_width_mm: float | None = None,
        board_height_mm: float | None = None,
        **kwargs,
    ) -> "PCBBuilder":
        """Construye un PCB convirtiendo primero a CircuitGraph para mantener el SSOT."""
        from core.circuit_graph import CircuitGraph
        graph = CircuitGraph.from_component_dicts(components)
        builder = cls.from_circuit_graph(
            graph,
            out_dir=kwargs.get("output_dir", "output"),
            board_width=board_width_mm,
            board_height=board_height_mm,
            **{k: v for k, v in kwargs.items() if k != "output_dir"}
        )
        if traces and builder._pcb:
            fp_map = {fp.ref: fp for fp in builder._pcb._footprints}
            for t in traces:
                fr = t.get("from_ref", "")
                fp1 = t.get("from_pad", "1")
                tr = t.get("to_ref", "")
                tp1 = t.get("to_pad", "1")
                net = t.get("net", "")
                tw = float(t.get("width", builder.trace_width))
                if fr in fp_map and tr in fp_map:
                    builder._pcb.trace(fp_map[fr], fp1, fp_map[tr], tp1, width=tw, net=net)
        return builder


    # ── Output ────────────────────────────────────────────────

    @property
    def pcb(self) -> PCBLayout:
        if self._pcb is None:
            raise RuntimeError("PCBBuilder: no se ha construido aún. Usa from_circuit_graph() o from_component_dicts().")
        return self._pcb

    def save(self, sub_dir: str = "pulselab_pcb") -> dict:
        """Guarda el PCB y devuelve un dict con rutas y stats."""
        pcb = self.pcb
        safe_name = "".join(
            c if c.isalnum() or c in "_-" else "_" for c in self.project_name
        )
        base_dir = Path(self.output_dir) / sub_dir
        out_path = base_dir / "board.kicad_pcb"
        pcb.save(out_path)

        result = {
            "path": str(out_path),
            "stats": pcb.stats(),
            "pcb": pcb,
            "success": True,
        }

        # Generar esquemático si tenemos el graph
        if self._graph is not None:
            from bridge.schematic_generator import SchematicGenerator
            sch_path = base_dir / "board.kicad_sch"
            SchematicGenerator(self._graph).save(str(sch_path))
            result["sch_path"] = str(sch_path)

        return result

    # ── Internal: Build from CircuitGraph ─────────────────────

    def _build_from_graph(self, graph: "CircuitGraph") -> None:
        comps = graph.components
        n = len(comps)

        # Calculate island-based spatial layout
        from bridge.island_layout import compute_layout
        positions, total_w, total_h = compute_layout(comps, mode='pcb')

        graph_meta = getattr(graph, 'meta', {}) if hasattr(graph, 'meta') and isinstance(graph.meta, dict) else {}
        graph_w = getattr(graph, 'board_width', None) or graph_meta.get('board_width') or graph_meta.get('board_width_mm')
        graph_h = getattr(graph, 'board_height', None) or graph_meta.get('board_height') or graph_meta.get('board_height_mm')

        w = self.board_width or graph_w or total_w
        h = self.board_height or graph_h or total_h

        pcb = PCBLayout(
            board_width=w, board_height=h,
            corner_radius=self.corner_radius,
            trace_width=self.trace_width,
            project_name=self.project_name,
            net_classes=self.net_classes,
        )
        
        # Center the board on an A4 sheet (297x210mm)
        offset_x = (297.0 - w) / 2.0
        offset_y = (210.0 - h) / 2.0
        pcb.board.origin_x = offset_x
        pcb.board.origin_y = offset_y

        # Continual Visual Inspection & Auto-Placement Optimization
        from core.auto_placement import AutoPlacementEngine
        comp_dicts = []
        for c in comps:
            c_pos = None
            if hasattr(c, 'position') and isinstance(c.position, (tuple, list, dict)):
                if isinstance(c.position, dict):
                    c_pos = [c.position.get('x', 0.0), c.position.get('y', 0.0)]
                else:
                    c_pos = list(c.position)
            comp_dicts.append({
                "etype": getattr(c, "etype", ""),
                "label": getattr(c, "label", c.uid),
                "value": str(getattr(c, "value", "")),
                "symbol": str(getattr(c, "symbol_id", "") or getattr(c, "symbol", "")),
                "symbol_id": str(getattr(c, "symbol_id", "") or getattr(c, "symbol", "")),
                "footprint": str(getattr(c, "footprint_id", "") or getattr(c, "footprint", "")),
                "footprint_id": str(getattr(c, "footprint_id", "") or getattr(c, "footprint", "")),
                "rotation": float(getattr(c, "rotation", 0.0)),
                "pins": getattr(c, "pins", {}),
                "n1": getattr(c, "n1", ""),
                "n2": getattr(c, "n2", ""),
                "position": c_pos
            })

        engine = AutoPlacementEngine(w, h)
        placed_dicts = engine.compute_placement(comp_dicts)
        pos_map = {d["label"]: d["position"] for d in placed_dicts if "position" in d}
        rot_map = {d["label"]: d.get("rotation", 0.0) for d in placed_dicts if "rotation" in d}

        for c in comps:
            label = getattr(c, 'label', c.uid)
            pos = pos_map.get(label)
            if not pos and hasattr(c, 'position') and isinstance(c.position, (tuple, list, dict)):
                if isinstance(c.position, dict):
                    pos = (c.position.get('x', 0.0), c.position.get('y', 0.0))
                else:
                    pos = c.position
            if not pos:
                pos = positions.get(c.uid) or positions.get(label) or (0.0, 0.0)

            x, y = pos[0], pos[1]
            x += offset_x + w / 2.0
            y += offset_y + h / 2.0
            etype = c.etype
            ref = getattr(c, "label", None) or c.uid
            val = f"{c.value:.6g}" if isinstance(c.value, float) else str(c.value)

            fp = None
            fp_added = False
            f_id = getattr(c, 'footprint_id', None) or getattr(c, 'footprint', None) or getattr(c, 'kicad_footprint', None)
            
            if f_id:
                if ':' in f_id:
                    lib, name = f_id.split(':', 1)
                    if pcb.add_raw_footprint(ref, lib, name, x, y, value=val):
                        fp_added = True
                        fp = pcb._footprints[-1]
                elif f_id == 'tactile_switch_6x6':
                    from bridge.pcb_layout import FootprintPresets
                    fp_sw = FootprintPresets.tactile_switch_6x6(
                        ref, val, net1_name=c.n1, net2_name=c.n2
                    )
                    fp = pcb.add_footprint(fp_sw, x, y)
                    fp_added = True
                elif f_id == 'sot223':
                    from bridge.pcb_layout import FootprintPresets
                    net1, net2, net3 = "", "", ""
                    if hasattr(c, "pins"):
                        net1 = c.pins.get("1", "")
                        net2 = c.pins.get("2", "")
                        net3 = c.pins.get("3", "")
                    fp_sot = FootprintPresets.sot223(
                        ref, val,
                        net1_id=pcb._get_net_id(net1), net1_name=net1,
                        net2_id=pcb._get_net_id(net2), net2_name=net2,
                        net3_id=pcb._get_net_id(net3), net3_name=net3,
                        net4_id=pcb._get_net_id(net2), net4_name=net2
                    )
                    fp = pcb.add_footprint(fp_sot, x, y)
                    fp_added = True
                elif f_id == 'flipper_zero_gpio':
                    fp = pcb.add_flipper_zero_gpio(ref, val, x, y)
                    fp_added = True

            if not fp_added:
                if etype == 'R':
                    fp = pcb.add_resistor(ref, val, x, y, net1=c.n1, net2=c.n2)
                elif etype == 'C':
                    fp = pcb.add_capacitor(ref, val, x, y, net1=c.n1, net2=c.n2)
                elif etype == 'L':
                    fp = pcb.add_inductor(ref, val, x, y, net1=c.n1, net2=c.n2)
                elif etype == 'V':
                    fp = pcb.add_pin_header(ref, 2, x, y, value=f"{val}V")
                elif etype in ('IC', 'MCU'):
                    fp = self._place_ic(pcb, c, ref, val, x, y)
                elif etype in ('Header', 'Conn', 'Connector'):
                    if 'USB' in val.upper() or 'USB' in str(getattr(c, 'symbol', '')).upper():
                        from bridge.pcb_layout import FootprintPresets
                        fp_usb = FootprintPresets.usb_c(ref, val)
                        fp = pcb.add_footprint(fp_usb, x, y)
                        fp_added = True
                    else:
                        num_pins = len(c.pins) if getattr(c, 'pins', None) else 2
                        fp = pcb.add_pin_header(ref, num_pins, x, y, value=val)
                else:
                    fp = pcb.add_pin_header(ref, 2, x, y, value=etype)

            if fp_added and etype in ('IC', 'MCU'):
                self._apply_ic_extras(pcb, c, ref, val, x, y)

            # Bind pin nets from component definition to footprint pads
            if fp and getattr(c, "pins", None):
                c_pins = dict(c.pins)
                # USB-C fallback mapping: shorthand pin 1 -> VBUS (A4,A9,B4,B9) and pin 4 -> GND (A1,A12,B1,B12)
                if ("USB" in val.upper() or "TYPE-C" in str(getattr(fp, "lib_id", "")).upper()):
                    vbus_net = c_pins.get("1") or c_pins.get("VBUS") or c_pins.get("5V")
                    gnd_net = c_pins.get("4") or c_pins.get("GND")
                    if vbus_net:
                        for p_id in ("A4", "A9", "B4", "B9"):
                            if p_id not in c_pins: c_pins[p_id] = vbus_net
                    if gnd_net:
                        for p_id in ("A1", "A12", "B1", "B12", "SH"):
                            if p_id not in c_pins: c_pins[p_id] = gnd_net

                for pad in fp.pads:
                    if pad.number in c_pins:
                        net_name = c_pins[pad.number]
                        pad.net_name = net_name
                        pad.net_id = pcb._get_net_id(net_name)
                    elif not pad.net_name:
                        net_name = f"NC_{ref}_{pad.number}"
                        pad.net_name = net_name
                        pad.net_id = pcb._get_net_id(net_name)

            # Apply component rotation if specified
            if fp:
                fp.rotation = float(rot_map.get(ref, getattr(c, "rotation", 0.0)))

            # Check and resolve courtyard overlaps using full package-spec + pad-aware AABB
            if fp:
                from core.visual_inference import get_package_spec as _gps
                for _ in range(12):
                    min_x, max_x, min_y, max_y = self._get_courtyard_aabb(fp, _gps)

                    has_collision = False
                    colliding_ref = ""
                    for other_fp in pcb._footprints:
                        if fp == other_fp:
                            continue
                        o_min_x, o_max_x, o_min_y, o_max_y = self._get_courtyard_aabb(other_fp, _gps)

                        if (min_x < o_max_x and max_x > o_min_x and
                            min_y < o_max_y and max_y > o_min_y):
                            has_collision = True
                            colliding_ref = other_fp.ref
                            break

                    if has_collision:
                        new_x, new_y = self._find_non_overlapping_position(pcb, fp, fp.x, fp.y)
                        if (new_x, new_y) != (fp.x, fp.y):
                            fp.x = new_x
                            fp.y = new_y
                        else:
                            logger.warning(
                                "pcb_builder",
                                f"COLLISION UNRESOLVED: {fp.ref} overlaps with {colliding_ref} "
                                f"near ({fp.x:.1f}, {fp.y:.1f})"
                            )
                            break
                    else:
                        break

        # Post-processing
        self._finalize(pcb, graph.all_nodes, n)
        self._pcb = pcb

    @staticmethod
    def _get_courtyard_aabb(fp: Any, gps_fn: Any) -> tuple[float, float, float, float]:
        """Returns (min_x, max_x, min_y, max_y) courtyard AABB matching VisualInferenceEngine geometry.
        Computes from package spec, pad extent, and rotation envelope (identical to CourtyardBox.rotated_bounds)."""
        if fp is None:
            # Default to standard 0805 passive AABB
            return -1.25, 1.25, -0.875, 0.875

        spec = gps_fn(footprint_id=getattr(fp, 'lib_id', ''), ref=getattr(fp, 'ref', ''), etype=getattr(fp, 'value', ''))
        w = float(spec.get('width', 3.0))
        h = float(spec.get('height', 3.0))
        m = float(spec.get('courtyard_margin', 0.25))
        pads = getattr(fp, 'pads', [])
        rot_rad = math.radians(getattr(fp, 'rotation', 0.0))
        cos_r, sin_r = math.cos(rot_rad), math.sin(rot_rad)
        comp_cx, comp_cy = getattr(fp, 'x', 0.0), getattr(fp, 'y', 0.0)

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
            comp_cx = getattr(fp, 'x', 0.0) + local_cx * cos_r - local_cy * sin_r
            comp_cy = getattr(fp, 'y', 0.0) + local_cx * sin_r + local_cy * cos_r

        tot_w = w + 2 * m
        tot_h = h + 2 * m
        cos_t = abs(math.cos(rot_rad))
        sin_t = abs(math.sin(rot_rad))
        eff_w = tot_w * cos_t + tot_h * sin_t
        eff_h = tot_w * sin_t + tot_h * cos_t
        hw = eff_w / 2.0
        hh = eff_h / 2.0
        return comp_cx - hw, comp_cx + hw, comp_cy - hh, comp_cy + hh


    def _find_non_overlapping_position(
        self,
        pcb: PCBLayout,
        current_fp_or_x: Any = None,
        start_x_or_y: float = 0.0,
        start_y: Optional[float] = None
    ) -> tuple[float, float]:
        """Finds a position near (start_x, start_y) that does not overlap existing footprints using spiral search.
        Supports both (pcb, fp, x, y) and (pcb, x, y) calling conventions."""
        from core.visual_inference import get_package_spec as _gps

        if start_y is None:
            current_fp = None
            start_x = float(current_fp_or_x if current_fp_or_x is not None else 0.0)
            start_y_val = float(start_x_or_y)
        else:
            current_fp = current_fp_or_x
            start_x = float(start_x_or_y)
            start_y_val = float(start_y)

        ox = getattr(pcb.board, "origin_x", 0.0) if hasattr(pcb, "board") and pcb.board else 0.0
        oy = getattr(pcb.board, "origin_y", 0.0) if hasattr(pcb, "board") and pcb.board else 0.0
        bw = getattr(pcb.board, "width_mm", 200.0) if hasattr(pcb, "board") and pcb.board else 200.0
        bh = getattr(pcb.board, "height_mm", 200.0) if hasattr(pcb, "board") and pcb.board else 200.0

        # Compute current footprint half-extents (same as _get_courtyard_aabb, offset-agnostic)
        if current_fp is not None:
            c_min_x, c_max_x, c_min_y, c_max_y = self._get_courtyard_aabb(current_fp, _gps)
            cur_hw = (c_max_x - c_min_x) / 2.0
            cur_hh = (c_max_y - c_min_y) / 2.0
        else:
            cur_hw = 1.25
            cur_hh = 0.875

        # Spiral search: 1.5mm step up to 18mm radius
        offsets = [(0, 0)]
        for r_step in range(1, 12):
            dist = r_step * 1.5
            for angle_deg in range(0, 360, 30):
                ang_rad = math.radians(angle_deg)
                offsets.append((round(dist * math.cos(ang_rad), 2), round(dist * math.sin(ang_rad), 2)))

        for ddx, ddy in offsets:
            cx, cy = start_x + ddx, start_y_val + ddy
            min_x, max_x = cx - cur_hw, cx + cur_hw
            min_y, max_y = cy - cur_hh, cy + cur_hh

            # Keep inside board WITH 2.5mm IPC visual keepout from edges (same as VisualInferenceEngine.edge_margin_mm)
            edge_keepout = 2.5
            if min_x < ox + edge_keepout or max_x > ox + bw - edge_keepout or min_y < oy + edge_keepout or max_y > oy + bh - edge_keepout:
                continue

            collision = False
            for fp in pcb._footprints:
                if fp == current_fp:
                    continue
                o_min_x, o_max_x, o_min_y, o_max_y = self._get_courtyard_aabb(fp, _gps)
                if (min_x < o_max_x and max_x > o_min_x and min_y < o_max_y and max_y > o_min_y):
                    collision = True
                    break
            if not collision:
                return cx, cy
        return start_x, start_y_val



    def _apply_ic_extras(self, pcb: PCBLayout, comp, ref: str, val: str, x: float, y: float) -> None:
        """Decoupling caps and antenna keepout for IC/MCU (including raw footprints)."""
        pkg = getattr(comp, 'pkg_type', None) or ""
        is_esp = ("ESP" in val.upper() or "NODE" in val.upper() or pkg == "ESP32")
        is_rf = ("CC1101" in val.upper() or "NRF" in val.upper() or "MODULE" in pkg.upper())

        # Si venimos de un CircuitGraph explícito, los desacoplos ya existen en el grafo (SSOT).
        if self._graph is None:
            power_nets = [
                n for n in getattr(comp, 'pins', {}).values()
                if n in ('3V3', 'VCC33', 'VCC', 'VBUS', '5V', '3.3V', '3.3V_ESP', '3.3V_FLIPPER', '5V_USB', '+5V', '+3V3', 'VDD', 'V_IN')
            ]
            dec = _pcb("ic_decoupling", {})
            high_val = dec.get("high_value", "10uF")
            low_val = dec.get("low_value", "100nF")
            if power_nets:
                p_net = power_nets[0]
                if is_esp:
                    init_cx1, init_cx2 = x - 16, x - 16
                    init_cy1, init_cy2 = y - 5, y + 5
                elif "MODULE" in pkg.upper() or "2x4" in pkg or "1x" in pkg:
                    init_cx1, init_cx2 = x - 8, x + 8
                    init_cy1, init_cy2 = y - 6, y - 6
                else:
                    init_cx1, init_cx2 = x - 6, x + 6
                    init_cy1, init_cy2 = y - 8, y - 8
                cx1, cy1 = self._find_non_overlapping_position(pcb, init_cx1, init_cy1)
                cx2, cy2 = self._find_non_overlapping_position(pcb, init_cx2, init_cy2)
                pcb.add_capacitor(f"C_{ref}_H", high_val, cx1, cy1, net1=p_net, net2="GND")
                pcb.add_capacitor(f"C_{ref}_L", low_val, cx2, cy2, net1=p_net, net2="GND")

        if is_esp:
            is_1u = ("1U" in val.upper() or "1U" in str(getattr(comp, 'symbol', '')).upper() or "1U" in str(getattr(comp, 'footprint_id', '')).upper())
            if not is_1u:
                # ESP32-S3-WROOM-1 (PCB antenna variant) keepout zone:
                # Antenna extends above top pad row (pads 39,40 at y=-11.0 local).
                # Keepout covers y=-11.8 to y=-18.0 from MCU center, 18mm wide.
                pcb.add_keepout([
                    (x - 9, y - 18.0), (x + 9, y - 18.0),
                    (x + 9, y - 11.8), (x - 9, y - 11.8),
                ])
            # ESP32-S3-WROOM EPAD 6x6mm thermal ground via array (3x3 grid centered at x, y)
            gnd_net = "PWR_GND" if "PWR_GND" in pcb._nets else "GND"
            for dx in (-1.5, 0.0, 1.5):
                for dy in (-1.5, 0.0, 1.5):
                    pcb.add_via(x + dx, y + dy, size=0.6, drill=0.3, net=gnd_net)
        # Note: RF breakout connector modules (Conn_02x04) don't need keepout zones
        # since they are just pin headers. The actual RF modules (CC1101, nRF24) are
        # external boards connected via these headers.


    def _place_ic(self, pcb: PCBLayout, comp, ref: str, val: str, x: float, y: float) -> Footprint:
        """Coloca un IC multipin parametrizado con extras de soporte."""
        pkg = getattr(comp, 'pkg_type', None)
        if not pkg:
            pkg = "SOP16"
            is_esp = ("ESP" in val.upper() or "NODE" in val.upper())
            if is_esp:
                pkg = "ESP32"
            if "CH340" in val.upper() or "SOP8" in val.upper():
                pkg = "SOP8"

        fp = pcb.add_ic(ref, val, x, y, pins=getattr(comp, 'pins', {}), pkg_type=pkg)
        self._apply_ic_extras(pcb, comp, ref, val, x, y)
        return fp

    def _finalize(self, pcb: PCBLayout, all_nodes: list, n_comps: int) -> None:
        """Pasos finales comunes a ambos builders."""
        if self.mounting_holes and n_comps >= int(_pcb("mounting_holes_min_components", 4)):
            pcb.add_mounting_holes_corners(margin=float(_pcb("mounting_holes_margin_mm", 3.5)))

        pcb.add_text(
            self.project_name, pcb.board.center_x,
            pcb.board.origin_y + pcb.board.height_mm + 2,
            size=float(_pcb("silkscreen.text_size_mm", 0.8)),
        )

        gnd_net = "PWR_GND" if "PWR_GND" in all_nodes else ("GND" if "GND" in all_nodes else None)
        if gnd_net and not pcb._zones:
            margin = float(_pcb("copper_pour.margin_mm", 0.5))
            pcb.add_copper_pour(gnd_net, layer="F.Cu", margin=margin)
            pcb.add_copper_pour(gnd_net, layer="B.Cu", margin=margin)

        # Inject ground via stitching matrix to bridge F.Cu and B.Cu copper pour zones
        if gnd_net:
            pcb.add_gnd_via_stitching(spacing_mm=6.0, net=gnd_net)

        if not self.skip_routing:
            self._route_usb_nets(pcb)
            pcb.autoroute(
                width=self.trace_width,
                grid_size=0.125,
            )

    def _route_usb_nets(self, pcb: PCBLayout) -> None:
        """Apply USB diff-pair geometry when D+/D- nets and pads exist."""
        from core.rf_tools import usb_diff_pair_dimensions

        net_names = {p.net_name for fp in pcb._footprints for p in fp.pads if p.net_name}
        usb_aliases = ({"USB_D+", "USB_D-"}, {"USB_DP", "USB_DM"}, {"D+", "D-"})
        pair = None
        for a, b in usb_aliases:
            if a in net_names and b in net_names:
                pair = (a, b)
                break
        if not pair:
            return

        dims = usb_diff_pair_dimensions()
        usb_cfg = _pcb("usb_diff_pair", {})
        spacing = float(dims.get("S_mm", usb_cfg.get("spacing_mm", 0.2)))
        width = float(dims.get("W_mm", usb_cfg.get("width_mm", 0.25)))

        pads_pos = []
        pads_neg = []
        for fp in pcb._footprints:
            for p in fp.pads:
                if p.net_name == pair[0]:
                    pads_pos.append((fp, p.number))
                elif p.net_name == pair[1]:
                    pads_neg.append((fp, p.number))

        if len(pads_pos) >= 2 and len(pads_neg) >= 2:
            pcb.trace_diff_pair(
                pads_pos[0][0], pads_pos[0][1],
                pads_pos[1][0], pads_pos[1][1],
                pads_neg[0][0], pads_neg[0][1],
                pads_neg[1][0], pads_neg[1][1],
                spacing_mm=spacing,
                width=width,
                net_pos=pair[0],
                net_neg=pair[1],
            )

    # ── Internal: Build from dicts (MCP server) ──────────────

    def _build_from_dicts(self, components: list[dict], traces: list[dict]) -> None:
        n = len(components)
        cols = max(2, int(n ** 0.5) + 1)
        auto = _pcb("auto_size", {})
        w = self.board_width or max(
            float(auto.get("min_width_mm", 30)),
            cols * float(auto.get("col_width_mm", 15)),
        )
        h = self.board_height or max(
            float(auto.get("min_height_mm", 20)),
            (n // cols + 2) * float(auto.get("row_height_mm", 12)),
        )

        pcb = PCBLayout(
            board_width=w, board_height=h,
            corner_radius=self.corner_radius,
            trace_width=self.trace_width,
            project_name=self.project_name,
            net_classes=self.net_classes,
        )
        
        # Center the board on an A4 sheet (297x210mm)
        offset_x = (297.0 - w) / 2.0
        offset_y = (210.0 - h) / 2.0
        pcb.board.origin_x = offset_x
        pcb.board.origin_y = offset_y

        fp_map = {}
        all_nets: set[str] = set()

        for c in components:
            ctype = c.get("type", "resistor")
            ref   = c.get("ref", "X1")
            value = c.get("value", "?")
            pos = c.get("position", {})
            x     = float(c.get("x", pos.get("x", 0))) + offset_x
            y     = float(c.get("y", pos.get("y", 0))) + offset_y
            rot   = float(c.get("rotation", 0))
            net1  = c.get("net1", "")
            net2  = c.get("net2", "")
            pkg   = c.get("package", _pcb("default_smd_package", "0805"))
            
            pins_data = c.get("pins", 2)
            if isinstance(pins_data, (dict, list)):
                pins = len(pins_data)
            else:
                try:
                    pins = int(pins_data)
                except (ValueError, TypeError):
                    pins = 2

            if net1: all_nets.add(net1)
            if net2: all_nets.add(net2)

            if ctype == "resistor":
                fp = pcb.add_resistor(ref, value, x, y, rot, net1, net2, pkg)
            elif ctype == "capacitor":
                fp = pcb.add_capacitor(ref, value, x, y, rot, net1, net2, pkg)
            elif ctype == "inductor":
                fp = pcb.add_inductor(ref, value, x, y, rot, net1, net2, pkg)
            elif ctype == "pin_header":
                fp = pcb.add_pin_header(ref, pins, x, y, rot, value)
            elif ctype == "dip_ic":
                fp = pcb.add_dip_ic(ref, pins, x, y, rot, value)
            elif ctype == "raw_footprint":
                lib = c.get("lib", "Package_QFP")
                name = c.get("name", "LQFP-48_7x7mm_P0.5mm")
                fp = pcb.add_raw_footprint(ref, lib, name, x, y, rot, value)
            else:
                fp = pcb.add_resistor(ref, value, x, y, rot, net1, net2, pkg)

            fp_map[ref] = fp

        # Traces manuales
        for t in traces:
            fr = t.get("from_ref", "")
            fp1 = t.get("from_pad", "1")
            tr = t.get("to_ref", "")
            tp1 = t.get("to_pad", "1")
            net = t.get("net", "")
            tw = float(t.get("width", self.trace_width))

            if fr in fp_map and tr in fp_map:
                pcb.trace(fp_map[fr], fp1, fp_map[tr], tp1, width=tw, net=net)

        # Finalize con las mismas mejoras que el graph builder
        self._finalize(pcb, sorted(all_nets), n)
        self._pcb = pcb
