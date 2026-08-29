"""
bridge/pcb_layout.py
====================
Generador programático de archivos .kicad_pcb (KiCad 10.0 S-expression format).

Formato de archivo: KiCad 10.0 S-expression (.kicad_pcb)
Ref: https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/

Nota de diseño:
  No importamos pcbnew — generamos el S-expression directamente.
  Esto significa que NO necesitamos KiCad instalado para generar el .kicad_pcb.
  kicad-cli (KiCad 10.0+) se utiliza para DRC y exportación de fabricación.
"""

from __future__ import annotations
import math
import uuid
import datetime
import heapq
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logger import logger


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Pad:
    """Un pad físico de un footprint."""
    number: str             # "1", "2", etc.
    pad_type: str = "smd"   # "smd", "thru_hole"
    shape: str = "rect"     # "rect", "circle", "oval", "roundrect"
    x: float = 0.0          # offset desde centro del footprint (mm)
    y: float = 0.0
    w: float = 1.2          # tamaño del pad (mm)
    h: float = 1.2
    drill: float = 0.0      # diámetro del taladro (mm), 0 = SMD
    net_id: int = 0
    net_name: str = ""
    layers: list = None  # list of layer strings
    zone_connect: Optional[int] = None  # 0=none, 1=thermal_relief, 2=solid

    def __post_init__(self):
        if self.layers is None:
            if self.pad_type == "thru_hole":
                self.layers = ["*.Cu", "*.Mask"]
            else:
                self.layers = ["F.Cu", "F.Paste", "F.Mask"]

    def to_sexpr(self) -> str:
        drill_str = f" (drill {self.drill})" if self.drill > 0 else ""
        layers_str = " ".join(f'"{ly}"' for ly in self.layers)
        zone_conn_str = f" (zone_connect {self.zone_connect})" if self.zone_connect is not None else ""
        uid = str(uuid.uuid4())
        return (
            f'    (pad "{self.number}" {self.pad_type} {self.shape} '
            f'(at {self.x:.4f} {self.y:.4f}) '
            f'(size {self.w:.4f} {self.h:.4f}){drill_str} '
            f'(layers {layers_str}){zone_conn_str} '
            f'(net {self.net_id} "{self.net_name}") (uuid "{uid}"))'
        )


@dataclass
class Footprint:
    """Un footprint posicionado en el PCB."""
    ref: str               # "R1", "C3", "U1"
    lib_id: str            # "Resistor_SMD:R_0805_2012Metric"
    value: str             # "10kΩ"
    x: float = 0.0         # posición en el PCB (mm)
    y: float = 0.0
    rotation: float = 0.0  # grados (0, 90, 180, 270)
    layer: str = "F.Cu"    # "F.Cu" o "B.Cu"
    pads: list = field(default_factory=list)
    uuid_str: str = ""

    def __post_init__(self):
        if not self.uuid_str:
            self.uuid_str = str(uuid.uuid4())

    def bounding_box(self) -> tuple[float, float, float, float]:
        """Devuelve (min_x, min_y, max_x, max_y) global del footprint, basado en sus pads."""
        if not self.pads:
            return (self.x, self.y, self.x, self.y)
            
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        # Rotación en radianes
        theta = math.radians(self.rotation)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        
        for p in self.pads:
            # Calcular esquinas del pad relativo a su propio centro
            half_w = p.w / 2.0
            half_h = p.h / 2.0
            
            # 4 esquinas locales del pad
            corners = [
                (p.x - half_w, p.y - half_h),
                (p.x + half_w, p.y - half_h),
                (p.x - half_w, p.y + half_h),
                (p.x + half_w, p.y + half_h)
            ]
            
            for cx, cy in corners:
                # Rotar la esquina alrededor del origen del footprint
                rot_x = cx * cos_t + cy * sin_t
                rot_y = -cx * sin_t + cy * cos_t
                
                # Coordenada global
                gx = self.x + rot_x
                gy = self.y + rot_y
                
                if gx < min_x: min_x = gx
                if gx > max_x: max_x = gx
                if gy < min_y: min_y = gy
                if gy > max_y: max_y = gy
                
        # Padding extra de 1mm (seda, holgura)
        return (min_x - 1.0, min_y - 1.0, max_x + 1.0, max_y + 1.0)

    def to_sexpr(self) -> str:
        rotation_str = f" {self.rotation:.1f}" if self.rotation != 0 else ""
        pad_lines = "\n".join(p.to_sexpr() for p in self.pads)
        silk = self.layer.replace('Cu', 'SilkS')
        fab  = self.layer.replace('Cu', 'Fab')

        # Dynamic offset for reference & value text based on pad extent
        local_min_y = min((p.y - p.h / 2.0 for p in self.pads), default=-1.5)
        local_max_y = max((p.y + p.h / 2.0 for p in self.pads), default=1.5)
        ref_y = min(-2.2, local_min_y - 1.2)
        val_y = max(2.2, local_max_y + 1.2)

        return (
            f'  (footprint "{self.lib_id}"\n'
            f'    (layer "{self.layer}")\n'
            f'    (uuid "{self.uuid_str}")\n'
            f'    (at {self.x:.4f} {self.y:.4f}{rotation_str})\n'
            f'    (property "Reference" "{self.ref}"\n'
            f'      (at 0 {ref_y:.2f})\n'
            f'      (layer "{silk}")\n'
            f'      (uuid "{uuid.uuid4()}")\n'
            f'      (effects (font (size 1 1) (thickness 0.15)) hide)\n'
            f'    )\n'
            f'    (property "Value" "{self.value}"\n'
            f'      (at 0 {val_y:.2f})\n'
            f'      (layer "{fab}")\n'
            f'      (uuid "{uuid.uuid4()}")\n'
            f'      (effects (font (size 1 1) (thickness 0.15)))\n'
            f'    )\n'
            f'{pad_lines}\n'
            f'  )'
        )


@dataclass
class RawFootprint(Footprint):
    """
    Representa un footprint cargado directamente de un archivo .kicad_mod.
    Sobrescribe to_sexpr para usar el contenido original con coordenadas actualizadas.
    """
    raw_sexpr: str = ""

    def to_sexpr(self) -> str:
        if not self.raw_sexpr:
            return super().to_sexpr()
            
        import re
        body = self.raw_sexpr
        
        # Replace Reference property
        body = re.sub(r'\(property\s+"Reference"\s+"[^"]+"', f'(property "Reference" "{self.ref}"', body, count=1)
        # Replace Value property
        body = re.sub(r'\(property\s+"Value"\s+"[^"]+"', f'(property "Value" "{self.value}"', body, count=1)
        
        for pad in self.pads:
            if pad.net_name:
                p_num = str(pad.number)
                nid = pad.net_id
                nname = pad.net_name
                # Inject (net ID "NAME") right after (layers "...") for exact pad number
                pattern = r'(\(pad\s+"' + re.escape(p_num) + r'"\s+[\s\S]*?\(\s*layers\s+(?:"[^"]+"\s*)+\))'
                replacement = r'\1 (net ' + str(nid) + r' "' + nname + r'")'
                body = re.sub(pattern, replacement, body, count=1)

        lines = body.splitlines()

        if lines and lines[0].startswith('(footprint'):
            rotation_str = f" {self.rotation:.1f}" if self.rotation != 0 else ""
            new_at = f'  (at {self.x:.4f} {self.y:.4f}{rotation_str})'
            
            for i in range(1, min(10, len(lines))):
                if lines[i].strip().startswith('(at '):
                    lines.pop(i)
                    break
                    
            lines.insert(1, new_at)
            
            lines[0] = '  ' + lines[0]
            for i in range(1, len(lines)):
                if lines[i].startswith(')'):
                    lines[i] = '  )'
                else:
                    lines[i] = '  ' + lines[i]
            body = "\n".join(lines)
            
        return body


@dataclass
class Trace:
    """Una pista (trace) en el PCB."""
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    width: float = 0.25     # mm
    layer: str = "F.Cu"
    net_id: int = 0

    def to_sexpr(self) -> str:
        uid = str(uuid.uuid4())
        return (
            f'  (segment (start {self.start_x:.4f} {self.start_y:.4f}) '
            f'(end {self.end_x:.4f} {self.end_y:.4f}) '
            f'(width {self.width:.4f}) (layer "{self.layer}") '
            f'(net {self.net_id}) (uuid "{uid}"))'
        )


@dataclass
class Via:
    """Una vía (via) entre capas."""
    x: float
    y: float
    size: float = 0.6
    drill: float = 0.3
    net_id: int = 0

    def to_sexpr(self) -> str:
        uid = str(uuid.uuid4())
        return (
            f'  (via (at {self.x:.4f} {self.y:.4f}) '
            f'(size {self.size:.4f}) (drill {self.drill:.4f}) '
            f'(layers "F.Cu" "B.Cu") (net {self.net_id}) (uuid "{uid}"))'
        )


@dataclass
class BoardOutline:
    """Perímetro del PCB (Edge.Cuts)."""
    width_mm: float = 50.0
    height_mm: float = 30.0
    corner_radius_mm: float = 1.0
    origin_x: float = 0.0     # esquina superior izquierda
    origin_y: float = 0.0
    # List of (cx, half_width, depth) for top-edge notches (for edge-mount connectors)
    top_cutouts: list = field(default_factory=list)

    @property
    def center_x(self) -> float:
        return self.origin_x + self.width_mm / 2

    @property
    def center_y(self) -> float:
        return self.origin_y + self.height_mm / 2

    def to_sexpr(self) -> str:
        x0, y0 = self.origin_x, self.origin_y
        x1, y1 = x0 + self.width_mm, y0 + self.height_mm
        r = min(self.corner_radius_mm, self.width_mm / 4, self.height_mm / 4)

        def top_edge_segments(start_x: float, end_x: float) -> list:
            """Generate top edge lines, including notch walls and bottom, forming a continuous path."""
            segs = []
            cuts = sorted(self.top_cutouts, key=lambda c: c[0])
            cur = start_x
            for cx, hw, depth in cuts:
                nl, nr = cx - hw, cx + hw
                if nl >= cur and nr <= end_x:
                    if nl > cur:
                        segs.append(f'  (gr_line (start {cur:.4f} {y0:.4f}) (end {nl:.4f} {y0:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
                    # Notch down
                    segs.append(f'  (gr_line (start {nl:.4f} {y0:.4f}) (end {nl:.4f} {y0+depth:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
                    # Notch bottom
                    segs.append(f'  (gr_line (start {nl:.4f} {y0+depth:.4f}) (end {nr:.4f} {y0+depth:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
                    # Notch up
                    segs.append(f'  (gr_line (start {nr:.4f} {y0+depth:.4f}) (end {nr:.4f} {y0:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
                    cur = nr
            if cur < end_x:
                segs.append(f'  (gr_line (start {cur:.4f} {y0:.4f}) (end {end_x:.4f} {y0:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            return segs

        if r < 0.1:
            lines = top_edge_segments(x0, x1)
            lines += [
                f'  (gr_line (start {x1:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
                f'  (gr_line (start {x1:.3f} {y1:.3f}) (end {x0:.3f} {y1:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
                f'  (gr_line (start {x0:.3f} {y1:.3f}) (end {x0:.3f} {y0:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
            ]
            return "\n".join(lines)
        else:
            # Esquinas redondeadas — líneas + arcos
            c = 0.70710678118
            lines = []
            # Top edge (with possible cutouts)
            lines.extend(top_edge_segments(x0 + r, x1 - r))
            # Top-right arc
            lines.append(f'  (gr_arc (start {x1-r:.4f} {y0:.4f}) (mid {x1-r+r*c:.4f} {y0+r-r*c:.4f}) (end {x1:.4f} {y0+r:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Right edge
            lines.append(f'  (gr_line (start {x1:.4f} {y0+r:.4f}) (end {x1:.4f} {y1-r:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Bottom-right arc
            lines.append(f'  (gr_arc (start {x1:.4f} {y1-r:.4f}) (mid {x1-r+r*c:.4f} {y1-r+r*c:.4f}) (end {x1-r:.4f} {y1:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Bottom edge
            lines.append(f'  (gr_line (start {x1-r:.4f} {y1:.4f}) (end {x0+r:.4f} {y1:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Bottom-left arc
            lines.append(f'  (gr_arc (start {x0+r:.4f} {y1:.4f}) (mid {x0+r-r*c:.4f} {y1-r+r*c:.4f}) (end {x0:.4f} {y1-r:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Left edge
            lines.append(f'  (gr_line (start {x0:.4f} {y1-r:.4f}) (end {x0:.4f} {y0+r:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Top-left arc
            lines.append(f'  (gr_arc (start {x0:.4f} {y0+r:.4f}) (mid {x0+r-r*c:.4f} {y0+r-r*c:.4f}) (end {x0+r:.4f} {y0:.4f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            return "\n".join(lines)


@dataclass
class MountingHole:
    """Agujero de montaje."""
    x: float
    y: float
    drill_mm: float = 3.2
    pad_mm: float = 6.0
    ref: str = "H1"

    def to_sexpr(self) -> str:
        uid  = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        uid3 = str(uuid.uuid4())
        return (
            f'  (footprint "MountingHole:MountingHole_{self.drill_mm:.1f}mm_M3"\n'
            f'    (layer "F.Cu")\n'
            f'    (uuid "{uid}")\n'
            f'    (at {self.x:.4f} {self.y:.4f})\n'
            f'    (property "Reference" "{self.ref}"\n'
            f'      (at 0 -4)\n'
            f'      (layer "F.SilkS")\n'
            f'      (uuid "{uid2}")\n'
            f'      (effects (font (size 1 1) (thickness 0.15)))\n'
            f'    )\n'
            f'    (pad "" np_thru_hole circle (at 0 0) (size {self.drill_mm:.2f} {self.drill_mm:.2f})\n'
            f'      (drill {self.drill_mm:.2f}) (layers "*.Cu" "*.Mask") (uuid "{uid3}"))\n'
            f'  )'
        )


@dataclass
class Zone:
    """Plano de cobre (Copper fill)."""
    net_id: int
    net_name: str
    layer: str = "F.Cu"
    points: list[tuple[float, float]] = field(default_factory=list)
    priority: int = 0
    connect_pads_mode: str = "thermal_relief"  # "thermal_relief", "solid", "none"
    clearance: float = 0.15
    min_thickness: float = 0.20
    thermal_bridge_width: float = 0.50
    thermal_gap: float = 0.50

    def to_sexpr(self) -> str:
        uid = str(uuid.uuid4())
        pts_str = "\n          ".join(f"(xy {x:.4f} {y:.4f})" for x, y in self.points)
        if self.connect_pads_mode == "solid":
            conn_str = f"(connect_pads yes (clearance {self.clearance:.2f}))"
        elif self.connect_pads_mode == "none":
            conn_str = f"(connect_pads no (clearance {self.clearance:.2f}))"
        else:
            conn_str = f"(connect_pads (clearance {self.clearance:.2f}))"

        return (
            f'  (zone (net {self.net_id}) (net_name "{self.net_name}") (layer "{self.layer}") '
            f'(uuid "{uid}")\n'
            f'    (hatch edge 0.5)\n'
            f'    (priority {self.priority})\n'
            f'    {conn_str}\n'
            f'    (min_thickness {self.min_thickness:.2f})\n'
            f'    (fill yes (thermal_gap {self.thermal_gap:.2f}) (thermal_bridge_width {self.thermal_bridge_width:.2f}))\n'
            f'    (polygon\n'
            f'      (pts\n          {pts_str}\n      )\n'
            f'    )\n'
            f'  )'
        )

@dataclass
class KeepoutZone:
    """Zona de exclusión (sin pistas o sin planos)."""
    points: list[tuple[float, float]] = field(default_factory=list)
    layers: list[str] = field(default_factory=lambda: ["F.Cu", "B.Cu"])
    tracks_allowed: bool = False
    vias_allowed: bool = False
    copperpour_allowed: bool = False

    def to_sexpr(self) -> str:
        pts_str = "\n          ".join(f"(xy {x:.4f} {y:.4f})" for x, y in self.points)
        uid = str(uuid.uuid4())
        layers_str = " ".join(f'"{ly}"' for ly in self.layers)
        t_allow = "allowed" if self.tracks_allowed else "not_allowed"
        v_allow = "allowed" if self.vias_allowed else "not_allowed"
        c_allow = "allowed" if self.copperpour_allowed else "not_allowed"
        
        return (
            f'  (zone (keepout (tracks {t_allow}) (vias {v_allow}) (pads allowed) (copperpour {c_allow}))\n'
            f'    (layers {layers_str}) (uuid "{uid}")\n'
            f'    (polygon\n'
            f'      (pts\n          {pts_str}\n      )\n'
            f'    )\n'
            f'  )'
        )

# ═══════════════════════════════════════════════════════════════════════════════
# FOOTPRINT PRESETS
# ═══════════════════════════════════════════════════════════════════════════════

class FootprintPresets:
    """Footprints predefinidos para componentes comunes."""

    @staticmethod
    def from_kicad_lib(ref: str, lib: str, name: str, value: str = "") -> Optional[Footprint]:
        """Carga un footprint real desde las bibliotecas oficiales de KiCad."""
        from bridge.kicad_footprint_parser import KiCadFootprintParser
        lib_id = f"{lib}:{name}"
        return KiCadFootprintParser.load_footprint(lib_id, ref=ref, value=value)

    @staticmethod
    def smd_resistor(ref: str, value: str, net1_id: int = 0,
                     net1_name: str = "", net2_id: int = 0,
                     net2_name: str = "",
                     package: str = "0805") -> Footprint:
        """Resistencia SMD (0402/0603/0805/1206)."""
        dims = {
            "0402": (0.5, 0.5, 0.6),   # pad_w, pad_h, center_dist
            "0603": (0.8, 0.8, 0.95),
            "0805": (1.0, 1.2, 1.1),
            "1206": (1.0, 1.6, 1.6),
        }
        pw, ph, cd = dims.get(package, dims["0805"])
        fp = Footprint(ref=ref, lib_id=f"Resistor_SMD:R_{package}_2012Metric",
                       value=value)
        fp.pads = [
            Pad("1", "smd", "roundrect", x=-cd, y=0, w=pw, h=ph,
                net_id=net1_id, net_name=net1_name),
            Pad("2", "smd", "roundrect", x=+cd, y=0, w=pw, h=ph,
                net_id=net2_id, net_name=net2_name),
        ]
        return fp

    @staticmethod
    def smd_capacitor(ref: str, value: str, net1_id: int = 0,
                      net1_name: str = "", net2_id: int = 0,
                      net2_name: str = "",
                      package: str = "0805") -> Footprint:
        """Condensador cerámico SMD."""
        fp = FootprintPresets.smd_resistor(ref, value, net1_id, net1_name,
                                           net2_id, net2_name, package)
        fp.lib_id = f"Capacitor_SMD:C_{package}_2012Metric"
        return fp

    @staticmethod
    def smd_inductor(ref: str, value: str, net1_id: int = 0,
                     net1_name: str = "", net2_id: int = 0,
                     net2_name: str = "",
                     package: str = "0805") -> Footprint:
        """Inductor SMD."""
        fp = FootprintPresets.smd_resistor(ref, value, net1_id, net1_name,
                                           net2_id, net2_name, package)
        fp.lib_id = f"Inductor_SMD:L_{package}_2012Metric"
        return fp

    @staticmethod
    def pin_header(ref: str, pins: int = 2, pitch: float = 2.54,
                   value: str = "Conn") -> Footprint:
        """Header de pines THT."""
        fp = Footprint(ref=ref,
                       lib_id=f"Connector_PinHeader_2.54mm:PinHeader_1x{pins:02d}_P2.54mm_Vertical",
                       value=value)
        fp.pads = []
        offset_y = ((pins - 1) * pitch) / 2.0
        for i in range(pins):
            fp.pads.append(Pad(
                str(i + 1), "thru_hole",
                "rect" if i == 0 else "circle",
                x=0, y=i * pitch - offset_y,
                w=1.7, h=1.7, drill=1.0,
            ))
        return fp

    @staticmethod
    def pin_header_2x(ref: str, rows: int = 4, pitch: float = 2.54,
                      value: str = "Conn") -> Footprint:
        """Header de pines THT 2xN."""
        pins = rows * 2
        fp = Footprint(ref=ref,
                       lib_id=f"Connector_PinHeader_2.54mm:PinHeader_2x{rows:02d}_P2.54mm_Vertical",
                       value=value)
        fp.pads = []
        offset_y = ((rows - 1) * pitch) / 2.0
        for i in range(rows):
            py = i * pitch - offset_y
            # Left column (odd pins)
            fp.pads.append(Pad(
                str(i * 2 + 1), "thru_hole",
                "rect" if i == 0 else "circle",
                x=-pitch/2, y=py,
                w=1.7, h=1.7, drill=1.0,
            ))
            # Right column (even pins)
            fp.pads.append(Pad(
                str(i * 2 + 2), "thru_hole",
                "circle",
                x=pitch/2, y=py,
                w=1.7, h=1.7, drill=1.0,
            ))
        return fp

    @staticmethod
    def dip_ic(ref: str, pins: int = 8, pitch: float = 2.54,
               row_width: float = 7.62, value: str = "IC") -> Footprint:
        """IC DIP (Dual In-line Package). `pins` debe ser par."""
        fp = Footprint(ref=ref,
                       lib_id=f"Package_DIP:DIP-{pins}_W{row_width:.2f}mm",
                       value=value)
        half = pins // 2
        fp.pads = []
        offset_y = ((half - 1) * pitch) / 2.0
        # Fila izquierda (pines 1..half, de arriba a abajo)
        for i in range(half):
            py = i * pitch - offset_y
            fp.pads.append(Pad(
                str(i + 1), "thru_hole",
                "rect" if i == 0 else "oval",
                x=-row_width / 2, y=py,
                w=1.6, h=1.6, drill=0.8,
            ))
        # Fila derecha (pines pins..half+1, de abajo a arriba)
        for i in range(half):
            py = i * pitch - offset_y
            fp.pads.append(Pad(
                str(pins - i), "thru_hole", "oval",
                x=+row_width / 2, y=py,
                w=1.6, h=1.6, drill=0.8,
            ))
        return fp

    @staticmethod
    def qfp_ic(ref: str, pins: int = 32, pitch: float = 0.8,
               body_mm: float = 7.0, value: str = "MCU") -> Footprint:
        """IC QFP/TQFP genérico."""
        fp = Footprint(ref=ref,
                       lib_id=f"Package_QFP:TQFP-{pins}_{body_mm:.0f}x{body_mm:.0f}mm_P{pitch:.2f}mm",
                       value=value)
        fp.pads = []
        per_side = pins // 4
        half_body = body_mm / 2 + 1.5  # pads outside body
        for side in range(4):
            for i in range(per_side):
                pin_num = side * per_side + i + 1
                offset = (i - (per_side - 1) / 2) * pitch
                if side == 0:     # Bottom
                    px, py = offset, half_body
                elif side == 1:   # Right
                    px, py = half_body, -offset
                elif side == 2:   # Top
                    px, py = -offset, -half_body
                else:             # Left
                    px, py = -half_body, offset
                fp.pads.append(Pad(
                    str(pin_num), "smd", "rect",
                    x=px, y=py, w=0.6, h=1.5 if side % 2 == 0 else 1.5,
                ))
        return fp

    @staticmethod
    def usb_c(ref: str, value: str = "USB-C") -> Footprint:
        """Puerto USB-C hembra (16 pads SMD / 4 de soporte)."""
        fp = Footprint(ref, "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", value)
        pads = [
            Pad("1", "smd", "rect", x=-2.4, y=-3.5, w=0.6, h=1.15),
            Pad("2", "smd", "rect", x=-0.8, y=-3.5, w=0.6, h=1.15),
            Pad("3", "smd", "rect", x=0.8, y=-3.5, w=0.6, h=1.15),
            Pad("4", "smd", "rect", x=2.4, y=-3.5, w=0.6, h=1.15),
            Pad("SH1", "thru_hole", "oval", x=-4.3, y=-2.5, w=1.0, h=1.6, drill=0.6),
            Pad("SH2", "thru_hole", "oval", x=4.3, y=-2.5, w=1.0, h=1.6, drill=0.6),
            Pad("SH3", "thru_hole", "oval", x=-4.3, y=2.5, w=1.0, h=1.6, drill=0.6),
            Pad("SH4", "thru_hole", "oval", x=4.3, y=2.5, w=1.0, h=1.6, drill=0.6),
        ]
        fp.pads = pads
        return fp

    @staticmethod
    def esp32_wroom(ref: str, value: str = "ESP32-S3") -> Footprint:
        """Modulo ESP32-S3-WROOM-1 con pads (41 pins incl. EPAD)."""
        fp = Footprint(ref, "RF_Module:ESP32-S3-WROOM-1", value)
        pitch = 1.27
        # Izquierda (1-14)
        for i in range(14):
            fp.pads.append(Pad(str(i+1), "smd", "rect", x=-9.0, y=-8.255 + i*pitch, w=2.0, h=0.9))
        # Abajo (15-24)
        for i in range(10):
            fp.pads.append(Pad(str(i+15), "smd", "rect", x=-5.715 + i*pitch, y=9.0, w=0.9, h=2.0))
        # Derecha (25-38)
        for i in range(14):
            fp.pads.append(Pad(str(38-i), "smd", "rect", x=9.0, y=-8.255 + i*pitch, w=2.0, h=0.9))
        # Arriba / Extras (39, 40)
        fp.pads.append(Pad("39", "smd", "rect", x=-2.0, y=-11.0, w=0.9, h=2.0))
        fp.pads.append(Pad("40", "smd", "rect", x=2.0, y=-11.0, w=0.9, h=2.0))
        # Central EPAD (41) - Thermal Ground Pad with Solid Zone Connection
        fp.pads.append(Pad("41", "smd", "rect", x=0.0, y=0.0, w=6.0, h=6.0, zone_connect=2))
        return fp

    @staticmethod
    def sop_ic(ref: str, pins: int = 16, pitch: float = 1.27,
               body_w: float = 3.9, body_h: float = 9.9, value: str = "IC") -> Footprint:
        """SOP/SOIC genérico de N pines (Dual In-Line)."""
        fp = Footprint(ref=ref,
                       lib_id=f"Package_SO:SOIC-{pins}_{body_w:.1f}x{body_h:.1f}mm_P{pitch:.2f}mm",
                       value=value)
        fp.pads = []
        per_side = pins // 2
        # Y offsets from center to each pin
        start_y = -((per_side - 1) * pitch) / 2
        # X offset is body_width/2 + pad_width/2 + small margin
        x_off = body_w / 2.0 + 1.2
        for i in range(per_side):
            py = start_y + i * pitch
            # Left side (1 to N/2), Y goes down (top to bottom)
            fp.pads.append(Pad(str(i + 1), "smd", "rect", x=-x_off, y=py, w=1.5, h=0.6))
            # Right side (N/2 + 1 to N), Y goes up (bottom to top)
            fp.pads.append(Pad(str(pins - i), "smd", "rect", x=x_off, y=py, w=1.5, h=0.6))
        return fp

    @staticmethod
    def sot223(ref: str, value: str, net1_id: int = 0, net1_name: str = "",
               net2_id: int = 0, net2_name: str = "", net3_id: int = 0, net3_name: str = "", net4_id: int = 0, net4_name: str = "") -> Footprint:
        """SOT-223-3_TabPin2: Pin1(GND/Adj), Pin2(Vout), Pin3(Vin), Pin4(Tab=Vout)"""
        fp = Footprint(ref=ref, lib_id="Package_TO_SOT_SMD:SOT-223-3_TabPin2", value=value)
        fp.pads = [
            Pad("1", "smd", "rect", x=-2.3, y=3.1, w=1.2, h=1.5, net_id=net1_id, net_name=net1_name),
            Pad("2", "smd", "rect", x=0.0,  y=3.1, w=1.2, h=1.5, net_id=net2_id, net_name=net2_name),
            Pad("3", "smd", "rect", x=2.3,  y=3.1, w=1.2, h=1.5, net_id=net3_id, net_name=net3_name),
            Pad("4", "smd", "rect", x=0.0,  y=-3.1, w=3.3, h=1.5, net_id=net4_id, net_name=net4_name, zone_connect=2), # Tab
        ]
        return fp

    @staticmethod
    def from_kicad_lib(ref: str, lib: str, name: str, value: str = "") -> Optional[RawFootprint]:
        """Carga un footprint desde las librerías de sistema de KiCad y parsea sus pads."""
        from bridge.kicad_bridge import get_kicad_footprint
        import re
        raw = get_kicad_footprint(lib, name)
        if not raw:
            return None
        rf = RawFootprint(ref=ref, lib_id=f"{lib}:{name}", value=value or name, raw_sexpr=raw)
        
        # Parse pads for autorouting & net binding
        pad_matches = re.findall(
            r'\(pad\s+"?([^"\s]+)"?\s+([^\s]+)\s+([^\s]+)\s+\(at\s+([\d\.-]+)\s+([\d\.-]+)[^\)]*\)\s+\(size\s+([\d\.-]+)\s+([\d\.-]+)\)',
            raw
        )
        for num, ptype, shape, x_str, y_str, w_str, h_str in pad_matches:
            px, py = float(x_str), float(y_str)
            w, h = float(w_str), float(h_str)
            drill_m = re.search(r'\(drill\s+([\d\.-]+)\)', raw)
            drill = float(drill_m.group(1)) if drill_m else 0.0
            rf.pads.append(Pad(num, ptype, shape, x=px, y=py, w=w, h=h, drill=drill))
            
        return rf

    @staticmethod
    def tactile_switch_6x6(ref: str, value: str = "Switch",
                           net1_id: int = 0, net1_name: str = "",
                           net2_id: int = 0, net2_name: str = "") -> Footprint:
        """Pulsador THT 6x6mm (4 pins, unidos 2 a 2)."""
        fp = Footprint(ref=ref, lib_id="Button_Switch_THT:SW_PUSH_6mm", value=value)
        # Pins 1 & 2 are connected internally, 3 & 4 are connected internally
        fp.pads = [
            Pad("1", "thru_hole", "circle", x=-3.25, y=-2.25, w=1.6, h=1.6, drill=1.0, net_id=net1_id, net_name=net1_name),
            Pad("2", "thru_hole", "circle", x=3.25,  y=-2.25, w=1.6, h=1.6, drill=1.0, net_id=net1_id, net_name=net1_name),
            Pad("3", "thru_hole", "circle", x=-3.25, y=2.25,  w=1.6, h=1.6, drill=1.0, net_id=net2_id, net_name=net2_name),
            Pad("4", "thru_hole", "circle", x=3.25,  y=2.25,  w=1.6, h=1.6, drill=1.0, net_id=net2_id, net_name=net2_name),
        ]
        return fp

    @staticmethod
    def flipper_zero_gpio(ref: str, value: str = "Flipper Zero") -> Footprint:
        """Header de Flipper Zero (18 pines) con separación de 4 pines (10.16mm) entre el 8 y el 9."""
        fp = Footprint(ref=ref, lib_id="Custom:Flipper_Zero_GPIO", value=value)
        fp.pads = []
        pitch = 2.54
        offset_y = (21 * pitch) / 2.0  # 26.67mm total span centered
        # Pines 1 a 8
        for i in range(8):
            fp.pads.append(Pad(
                str(i + 1), "thru_hole",
                "rect" if i == 0 else "circle",
                x=0, y=i * pitch - offset_y,
                w=1.7, h=1.7, drill=1.0,
            ))
        # Pines 9 a 18 (desplazados 4 posiciones extra)
        for i in range(8, 18):
            fp.pads.append(Pad(
                str(i + 1), "thru_hole", "circle",
                x=0, y=(i + 4) * pitch - offset_y,
                w=1.7, h=1.7, drill=1.0,
            ))
        return fp


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PCBLayout:
    """
    Motor de layout de PCB con controles espaciales.

    Metáfora: como un canvas 2D con unidades en mm, donde puedes:
      - Colocar componentes en posiciones exactas
      - Alinearlos por ejes de simetría
      - Distribuirlos automáticamente
      - Trazar pistas entre pads
      - Definir el contorno de la placa

    Uso::

        pcb = PCBLayout(board_width=50, board_height=30)
        r1 = pcb.add_resistor("R1", "10k", x=10, y=15)
        c1 = pcb.add_capacitor("C1", "100nF", x=20, y=15)
        pcb.trace(r1, "2", c1, "1", width=0.25)
        pcb.align_horizontal(r1, c1)
        pcb.save("output/my_board.kicad_pcb")
    """

    def __init__(self,
                 board_width: float = 50.0,
                 board_height: float = 30.0,
                 corner_radius: float = 1.5,
                 layers: int = 2,
                 trace_width: float = 0.25,
                 clearance: float = 0.2,
                 project_name: str = "PulseLab Design",
                 net_classes: dict = None):
        self.board = BoardOutline(
            width_mm=board_width, height_mm=board_height,
            corner_radius_mm=corner_radius,
        )
        self.layers = layers
        self.default_trace_width = trace_width
        self.clearance = clearance
        self.project_name = project_name
        self.net_classes = net_classes or {}

        self._footprints: list[Footprint] = []
        self._traces: list[Trace] = []
        self._vias: list[Via] = []
        self._mounting_holes: list[MountingHole] = []
        self._zones: list[Zone] = []
        self._keepouts: list[KeepoutZone] = []
        self._edge_cutouts: list[str] = []  # raw S-expr lines for Edge.Cuts cutouts
        self._nets: dict[str, int] = {"": 0}  # net_name → net_id
        self._net_counter = 0
        self._text_items: list[str] = []

    # ── Net management ────────────────────────────────────────────

    def _get_net_id(self, name: str) -> int:
        if name not in self._nets:
            self._net_counter += 1
            self._nets[name] = self._net_counter
        return self._nets[name]

    def get_net_width(self, net_name: str) -> float:
        """Determina el grosor de pista basado en las clases de nets (net_classes)."""
        if not net_name:
            return self.default_trace_width
        for cls_name, cls_data in self.net_classes.items():
            if net_name in cls_data.get("nets", []):
                return float(cls_data.get("width", self.default_trace_width))
        return self.default_trace_width

    # ── Component placement ───────────────────────────────────────

    def add_footprint(self, fp: Footprint,
                      x: float = None, y: float = None,
                      rotation: float = None) -> Footprint:
        """Añade un footprint al PCB."""
        if x is not None:
            fp.x = x
        if y is not None:
            fp.y = y
        if rotation is not None:
            fp.rotation = rotation
        self._footprints.append(fp)
        return fp

    def add_raw_footprint(self, ref: str, lib: str, name: str,
                          x: float = 0, y: float = 0, rotation: float = 0,
                          value: str = "") -> Optional[Footprint]:
        """Coloca un footprint extraído de la librería oficial de KiCad."""
        fp = FootprintPresets.from_kicad_lib(ref, lib, name, value)
        if fp:
            return self.add_footprint(fp, x, y, rotation)
        return None

    def add_resistor(self, ref: str, value: str,
                     x: float = 0, y: float = 0,
                     rotation: float = 0,
                     net1: str = "", net2: str = "",
                     package: str = "0805") -> Footprint:
        """Coloca una resistencia SMD."""
        fp = FootprintPresets.smd_resistor(
            ref, value,
            net1_id=self._get_net_id(net1), net1_name=net1,
            net2_id=self._get_net_id(net2), net2_name=net2,
            package=package,
        )
        return self.add_footprint(fp, x, y, rotation)

    def add_capacitor(self, ref: str, value: str,
                      x: float = 0, y: float = 0,
                      rotation: float = 0,
                      net1: str = "", net2: str = "",
                      package: str = "0805") -> Footprint:
        """Coloca un capacitor cerámico SMD."""
        fp = FootprintPresets.smd_capacitor(
            ref, value,
            net1_id=self._get_net_id(net1), net1_name=net1,
            net2_id=self._get_net_id(net2), net2_name=net2,
            package=package,
        )
        return self.add_footprint(fp, x, y, rotation)

    def add_inductor(self, ref: str, value: str,
                     x: float = 0, y: float = 0,
                     rotation: float = 0,
                     net1: str = "", net2: str = "",
                     package: str = "0805") -> Footprint:
        """Coloca un inductor SMD."""
        fp = FootprintPresets.smd_inductor(
            ref, value,
            net1_id=self._get_net_id(net1), net1_name=net1,
            net2_id=self._get_net_id(net2), net2_name=net2,
            package=package,
        )
        return self.add_footprint(fp, x, y, rotation)

    def add_pin_header(self, ref: str, pins: int,
                       x: float = 0, y: float = 0,
                       rotation: float = 0,
                       value: str = "Conn") -> Footprint:
        """Coloca un header de pines THT."""
        fp = FootprintPresets.pin_header(ref, pins, value=value)
        return self.add_footprint(fp, x, y, rotation)

    def add_dip_ic(self, ref: str, pins: int,
                   x: float = 0, y: float = 0,
                   rotation: float = 0,
                   value: str = "IC") -> Footprint:
        """Coloca un IC DIP."""
        fp = FootprintPresets.dip_ic(ref, pins, value=value)
        return self.add_footprint(fp, x, y, rotation)

    def add_sot223(self, ref: str, value: str, x: float = 0.0, y: float = 0.0,
                   net1: str = "", net2: str = "", net3: str = "", rotation: float = 0.0) -> Footprint:
        """Añade regulador / transistor en paquete SOT-223."""
        fp = FootprintPresets.sot223(
            ref, value,
            self._get_net_id(net1), net1,
            self._get_net_id(net2), net2,
            self._get_net_id(net3), net3
        )
        return self.add_footprint(fp, x, y, rotation)

    def add_switch(self, ref: str, value: str = "Switch", x: float = 0, y: float = 0,
                   rotation: float = 0, net1: str = "", net2: str = "") -> Footprint:
        """Añade un pulsador 6x6mm."""
        fp = FootprintPresets.tactile_switch_6x6(
            ref, value, self._get_net_id(net1), net1, self._get_net_id(net2), net2
        )
        return self.add_footprint(fp, x, y, rotation)

    def add_flipper_zero_gpio(self, ref: str, value: str = "Flipper Zero", x: float = 0, y: float = 0,
                              rotation: float = 0) -> Footprint:
        """Añade el header GPIO de Flipper Zero."""
        fp = FootprintPresets.flipper_zero_gpio(ref, value)
        return self.add_footprint(fp, x, y, rotation)

    def add_ic(self, ref: str, value: str, x: float = 0.0, y: float = 0.0,
               pins: dict = None, pkg_type: str = "SOP16", rotation: float = 0.0) -> Footprint:
        """Añade un IC multipin parametrizado."""
        if pins is None: pins = {}
        
        if pkg_type == "SOP16":
            fp = FootprintPresets.sop_ic(ref, pins=16, value=value)
        elif pkg_type in ("ESP12", "ESP32"):
            fp = FootprintPresets.esp32_wroom(ref, value=value)
        elif pkg_type == "MODULE_2x4":
            fp = FootprintPresets.pin_header_2x(ref, rows=4, value=value)
        else:
            fp = FootprintPresets.sop_ic(ref, pins=8, pitch=1.27, body_w=3.9, body_h=4.9, value=value)
            
        for p in fp.pads:
            net_name = pins.get(p.number)
            if net_name:
                p.net_id = self._get_net_id(net_name)
                p.net_name = net_name
                
        return self.add_footprint(fp, x, y, rotation)

    def add_mounting_hole(self, x: float, y: float,
                          drill: float = 3.2, ref: str = None) -> MountingHole:
        """Coloca un agujero de montaje M3."""
        if ref is None:
            ref = f"H{len(self._mounting_holes) + 1}"
        hole = MountingHole(x=x, y=y, drill_mm=drill, ref=ref)
        self._mounting_holes.append(hole)
        return hole

    def add_mounting_holes_corners(self, margin: float = 3.5,
                                   drill: float = 3.2) -> list[MountingHole]:
        """Coloca 4 agujeros de montaje M3 en las esquinas."""
        ox, oy = self.board.origin_x, self.board.origin_y
        w, h = self.board.width_mm, self.board.height_mm
        holes = [
            self.add_mounting_hole(ox + margin, oy + margin, drill, ref="H1"),
            self.add_mounting_hole(ox + w - margin, oy + margin, drill, ref="H2"),
            self.add_mounting_hole(ox + margin, oy + h - margin, drill, ref="H3"),
            self.add_mounting_hole(ox + w - margin, oy + h - margin, drill, ref="H4"),
        ]
        return holes

    def add_keepout(self, points: list[tuple[float, float]], layers: list[str] = None, tracks_allowed: bool = False, vias_allowed: bool = False, copperpour_allowed: bool = False) -> KeepoutZone:
        """Define una zona donde el motor no debe verter cobre ni opcionalmente trazar pistas/vías."""
        kz = KeepoutZone(points=points, layers=layers or ["F.Cu", "B.Cu"], tracks_allowed=tracks_allowed, vias_allowed=vias_allowed, copperpour_allowed=copperpour_allowed)
        self._keepouts.append(kz)
        return kz

    def add_text(self, text: str, x: float, y: float,
                 size: float = 1.5, layer: str = "F.SilkS") -> None:
        """Coloca texto en el PCB (silkscreen)."""
        uid = str(uuid.uuid4())
        # Enforce minimum size of 0.8mm for DRC compliance
        size = max(0.8, size)
        justify = " (justify mirror)" if layer.startswith("B.") else ""
        self._text_items.append(
            f'  (gr_text "{text}" (at {x:.3f} {y:.3f}) (layer "{layer}") '
            f'(uuid "{uid}") '
            f'(effects (font (size {size:.1f} {size:.1f}) (thickness 0.15)){justify}))'
        )

    def add_multiline_text(self, multiline_text: str, start_x: float, start_y: float,
                           line_height: float = 1.0, size: float = 0.8, layer: str = "F.SilkS") -> None:
        """Coloca texto multilínea (ej. Arte ASCII) en la serigrafía del PCB."""
        lines = multiline_text.strip("\r\n").splitlines()
        for idx, line in enumerate(lines):
            if line.strip():
                self.add_text(line, start_x, start_y + idx * line_height, size=size, layer=layer)

    # ── Traces ────────────────────────────────────────────────────

    def trace(self, fp1: Footprint, pad1: str,
              fp2: Footprint, pad2: str,
              width: float = None, layer: str = "F.Cu",
              net: str = "") -> list[Trace]:
        """
        Traza una pista entre dos pads con ruteo ortogonal (L-shape).

        Genera un segmento en L (horizontal + vertical) entre los
        centros absolutos de los dos pads.

        """
        if width is None:
            width = self.get_net_width(net)
        net_id = self._get_net_id(net) if net else 0

        # Posiciones absolutas de los pads
        p1 = self._pad_abs(fp1, pad1)
        p2 = self._pad_abs(fp2, pad2)
        if p1 is None or p2 is None:
            return []

        traces = []
        # L-route: horizontal primero, luego vertical
        if abs(p1[0] - p2[0]) > 0.01 and abs(p1[1] - p2[1]) > 0.01:
            mid_x, mid_y = p2[0], p1[1]
            traces.append(Trace(p1[0], p1[1], mid_x, mid_y, width, layer, net_id))
            traces.append(Trace(mid_x, mid_y, p2[0], p2[1], width, layer, net_id))
        else:
            traces.append(Trace(p1[0], p1[1], p2[0], p2[1], width, layer, net_id))

        self._traces.extend(traces)
        return traces

    def trace_bus(self, points: list[tuple[float, float]],
                  width: float = None, layer: str = "F.Cu",
                  net: str = "") -> list[Trace]:
        """Traza una línea de pistas por una serie de puntos."""
        if width is None:
            width = self.get_net_width(net)
        net_id = self._get_net_id(net) if net else 0
        traces = []
        for i in range(len(points) - 1):
            t = Trace(points[i][0], points[i][1],
                      points[i+1][0], points[i+1][1],
                      width, layer, net_id)
            traces.append(t)
            self._traces.append(t)
        return traces

    def trace_diff_pair(
        self,
        fp1: Footprint, pad1: str,
        fp2: Footprint, pad2: str,
        fp3: Footprint, pad3: str,
        fp4: Footprint, pad4: str,
        spacing_mm: float = 0.2,
        width: float = None,
        net_pos: str = "USB_D+",
        net_neg: str = "USB_D-",
    ) -> list[Trace]:
        """
        Route USB D+ and D- as parallel matched segments between two endpoint pairs.
        fp1/pad1 and fp2/pad2 are one side; fp3/pad3 and fp4/pad4 the other.
        """
        if width is None:
            width = self.default_trace_width
        p1p = self._pad_abs(fp1, pad1)
        p2p = self._pad_abs(fp2, pad2)
        p1n = self._pad_abs(fp3, pad3)
        p2n = self._pad_abs(fp4, pad4)
        if not all([p1p, p2p, p1n, p2n]):
            return []
        # Offset D- trace by spacing perpendicular to primary direction
        dx = p2p[0] - p1p[0]
        dy = p2p[1] - p1p[1]
        if abs(dx) >= abs(dy):
            off = (0, spacing_mm)
        else:
            off = (spacing_mm, 0)
        mid = ((p1p[0] + p2p[0]) / 2, (p1p[1] + p2p[1]) / 2)
        path_p = [p1p, (mid[0], p1p[1]), (mid[0], p2p[1]), p2p] if abs(dx) >= abs(dy) else [p1p, (p1p[0], mid[1]), (p2p[0], mid[1]), p2p]
        path_n = [(p[0] + off[0], p[1] + off[1]) for p in path_p]
        t1 = self.trace_bus(path_p, width=width, net=net_pos)
        t2 = self.trace_bus(path_n, width=width, net=net_neg)
        return t1 + t2

    def add_via(self, x: float, y: float,
                size: float = 0.6, drill: float = 0.3,
                net: str = "") -> Optional[Via]:
        """Coloca una vía evitando duplicados y colisiones con taladros NPTH/pads."""
        for v in self._vias:
            if math.hypot(v.x - x, v.y - y) < 0.3:
                return v
        for mh in self._mounting_holes:
            if math.hypot(mh.x - x, mh.y - y) < (mh.drill_mm / 2.0 + drill / 2.0 + 0.3):
                return None
        for fp in self._footprints:
            rad = math.radians(fp.rotation)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            for p in fp.pads:
                p_drill = getattr(p, "drill", 0.0) or (0.65 if ("thru_hole" in p.pad_type or not p.net_name) else 0.0)
                if p_drill > 0.0 or not p.net_name:
                    px = fp.x + p.x * cos_r - p.y * sin_r
                    py = fp.y + p.x * sin_r + p.y * cos_r
                    eff_drill = max(p_drill, 0.65)
                    if math.hypot(px - x, py - y) < (eff_drill / 2.0 + drill / 2.0 + 0.35):
                        return None
        v = Via(x, y, size, drill, self._get_net_id(net) if net else 0)
        self._vias.append(v)
        return v

    def add_copper_pour(self, net: str = "GND", layer: str = "F.Cu", margin: float = 1.0,
                        priority: int = 0,
                        x0: float = None, y0: float = None,
                        x1: float = None, y1: float = None):
        """Añade plano de masa envolviendo toda el área de diseño o un área personalizada."""
        nid = self._get_net_id(net)
        _x0 = (self.board.origin_x + margin) if x0 is None else x0
        _y0 = (self.board.origin_y + margin) if y0 is None else y0
        _x1 = (self.board.origin_x + self.board.width_mm - margin) if x1 is None else x1
        _y1 = (self.board.origin_y + self.board.height_mm - margin) if y1 is None else y1
        pts = [(_x0, _y0), (_x1, _y0), (_x1, _y1), (_x0, _y1)]
        self._zones.append(Zone(net_id=nid, net_name=net, layer=layer, points=pts, priority=priority))

    def add_edge_cutout(self, cx: float, width: float, depth: float, edge: str = "top"):
        """
        Añade un recorte rectangular en el borde de la placa (Edge.Cuts).
        Para montaje de conector en borde (edge-mount).
        cx: centro X del recorte (mm)
        width: anchura del recorte (mm)
        depth: profundidad del recorte hacia el interior (mm)
        edge: 'top', 'bottom', 'left', 'right'
        """
        hw = width / 2.0
        if edge == "top":
            self.board.top_cutouts.append((cx, hw, depth))

    def add_gnd_via_stitching(self, spacing_mm: float = 10.0, net: str = "GND", clearance_mm: float = 2.5):
        """
        Inyecta vías de cosido de plano de masa (GND via stitching) distribuidas en cuadrícula.
        Conecta las zonas de cobre superior e inferior evitando zonas de exclusión y pads/pistas de señal.
        """
        x0 = self.board.origin_x + 5.0
        y0 = self.board.origin_y + 5.0
        x1 = self.board.origin_x + self.board.width_mm - 5.0
        y1 = self.board.origin_y + self.board.height_mm - 5.0

        # Bloqueos de TODOS los pads para evitar colisiones taladro-pad o taladro-taladro
        avoid_points = []
        for fp in self._footprints:
            rad = math.radians(fp.rotation)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            for p in fp.pads:
                px = fp.x + p.x * cos_r - p.y * sin_r
                py = fp.y + p.x * sin_r + p.y * cos_r
                avoid_points.append((px, py))

        curr_x = x0
        vias_added = 0
        while curr_x <= x1:
            curr_y = y0
            while curr_y <= y1:
                # Comprobar si el punto está dentro de un keepout
                inside_keepout = False
                for kz in self._keepouts:
                    k_min_x = min(pt[0] for pt in kz.points)
                    k_max_x = max(pt[0] for pt in kz.points)
                    k_min_y = min(pt[1] for pt in kz.points)
                    k_max_y = max(pt[1] for pt in kz.points)
                    if k_min_x <= curr_x <= k_max_x and k_min_y <= curr_y <= k_max_y:
                        inside_keepout = True
                        break

                if not inside_keepout:
                    # Comprobar distancia a pads
                    safe = True
                    for ax, ay in avoid_points:
                        if math.hypot(curr_x - ax, curr_y - ay) < 2.5:
                            safe = False
                            break
                    
                    # Comprobar distancia a agujeros de montaje
                    if safe:
                        for mh in self._mounting_holes:
                            if math.hypot(curr_x - mh.x, curr_y - mh.y) < 3.5:
                                safe = False
                                break

                    # Comprobar distancia a vias existentes
                    if safe:
                        for v in self._vias:
                            if math.hypot(curr_x - v.x, curr_y - v.y) < 2.5:
                                safe = False
                                break

                    if safe:
                        self.add_via(curr_x, curr_y, size=0.6, drill=0.3, net=net)
                        vias_added += 1

                curr_y += spacing_mm
            curr_x += spacing_mm

        logger.info("pcb_layout", f"add_gnd_via_stitching(): {vias_added} vías de cosido GND colocadas con espaciado seguro.")

    # ── Auto-Router ───────────────────────────────────────────────

    def autoroute(self, layer: str = "F.Cu", width: float = 0.25, grid_size: float = 0.25, prefer_freerouting: bool = False):
        """Enruta todas las nets no ruteadas en 2 capas (F.Cu y B.Cu).
        Si prefer_freerouting=True y el binario FreeRouting está disponible, utiliza FreeRouting.
        De lo contrario o como fallback, utiliza el motor nativo A* octilineal a 45°."""
        if prefer_freerouting:
            try:
                from bridge.freerouting_bridge import FreeRoutingBridge
                import tempfile
                fr = FreeRoutingBridge()
                if fr.exe_path:
                    logger.info("pcb_layout", f"autoroute(): Ejecutando FreeRouting ({fr.exe_path})...")
                    with tempfile.TemporaryDirectory() as tmp_d:
                        tmp_pcb = Path(tmp_d) / "board.kicad_pcb"
                        self.save(str(tmp_pcb))
                        dsn_path = fr.export_dsn(tmp_pcb)
                        res = fr.run_freerouting(dsn_path, max_passes=5)
                        if res.success and res.ses_path and res.ses_path.exists():
                            out_routed = fr.import_ses(tmp_pcb, res.ses_path, tmp_pcb)
                            if out_routed.exists():
                                logger.info("pcb_layout", "autoroute(): FreeRouting completado con éxito.")
                                return
            except Exception as e:
                logger.warning("pcb_layout", f"FreeRouting falló ({e}), continuando con A* octilineal nativo.")

        logger.info("pcb_layout", f"autoroute() iniciado (A* octilineal 45°): {len(self._footprints)} footprints, grid={grid_size}mm")
        net_pads = {} # net_name -> list of (x, y, net_id, pad_layer)
        layers = ["F.Cu", "B.Cu"]
        
        seen_fp_net_pads = set()
        for fp in self._footprints:
            rad = math.radians(fp.rotation)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            for p in fp.pads:
                gnd_nets = {'GND', 'PWR_GND', 'PWR_GND_FLIPPER', 'PGND', 'AGND', 'DGND', 'SGND', '-'}
                if p.net_name and p.net_name not in gnd_nets:  # GND nets handled by copper fill-zone
                    # Skip secondary parallel pins on USB-C receptacles (use primary pins A9, A6, A7)
                    if getattr(p, "number", "") in ("A4", "B4", "B9", "A1", "B1", "B12", "B6", "B7"):
                        continue

                    # Avoid routing between redundant parallel pins on the same component
                    fp_key = (fp.ref, p.net_name)
                    if fp_key in seen_fp_net_pads:
                        continue
                    seen_fp_net_pads.add(fp_key)

                    px = fp.x + p.x * cos_r - p.y * sin_r
                    py = fp.y + p.x * sin_r + p.y * cos_r
                    if p.net_name not in net_pads:
                        net_pads[p.net_name] = []
                    
                    pad_layer = 0 # F.Cu por defecto
                    if "thru_hole" in p.pad_type or "*.Cu" in p.layers:
                        pad_layer = -1 # ambas
                    elif "B.Cu" in p.layers or fp.layer == "B.Cu":
                        pad_layer = 1
                        
                    net_pads[p.net_name].append((px, py, p.net_id, pad_layer))

        if not net_pads:
            logger.warning("pcb_layout", "autoroute() sin nets a rutear (net_pads vacio)")
            return

        occupied = {} # (layer_idx, x, y) -> net_name

        # 1. Keepout IC & MCU inner bodies so traces NEVER cross inside component bodies
        for fp in self._footprints:
            is_conn = any(k in fp.lib_id.upper() or k in fp.ref.upper() for k in ("CONN", "HEADER", "PINHEADER", "J", "TERMINAL", "SOCKET"))
            if not is_conn and len(fp.pads) > 4:
                rad = math.radians(fp.rotation)
                cos_r, sin_r = math.cos(rad), math.sin(rad)
                pad_xs, pad_ys = [], []
                for p in fp.pads:
                    px = fp.x + p.x * cos_r - p.y * sin_r
                    py = fp.y + p.x * sin_r + p.y * cos_r
                    pad_xs.append(px)
                    pad_ys.append(py)
                
                min_px, max_px = min(pad_xs), max(pad_xs)
                min_py, max_py = min(pad_ys), max(pad_ys)
                
                # Center core rectangle (shrunk by 1.2mm inward from outer pad tips)
                b_min_x = min_px + 1.2
                b_max_x = max_px - 1.2
                b_min_y = min_py + 1.2
                b_max_y = max_py - 1.2
                
                if b_max_x > b_min_x + 1.0 and b_max_y > b_min_y + 1.0:
                    min_gx = int(b_min_x / grid_size)
                    max_gx = int(b_max_x / grid_size)
                    min_gy = int(b_min_y / grid_size)
                    max_gy = int(b_max_y / grid_size)
                    for gx in range(min_gx, max_gx + 1):
                        for gy in range(min_gy, max_gy + 1):
                            for l_idx in [0, 1]:
                                occupied[(l_idx, gx, gy)] = "KEEPOUT_BODY"

        # 1b. Keepout mounting holes
        for mh in self._mounting_holes:
            rad = mh.drill_mm / 2.0 + 0.6  # drill radius + 0.6mm copper keepout margin
            min_gx = int((mh.x - rad) / grid_size)
            max_gx = int((mh.x + rad) / grid_size)
            min_gy = int((mh.y - rad) / grid_size)
            max_gy = int((mh.y + rad) / grid_size)
            for gx in range(min_gx, max_gx + 1):
                for gy in range(min_gy, max_gy + 1):
                    for l_idx in [0, 1]:
                        occupied[(l_idx, gx, gy)] = "KEEPOUT_BODY"

        # 1c. Keepout zones (antenna exclusion, RF shields, user-defined)
        for kz in self._keepouts:
            if not kz.points:
                continue
            kz_xs = [pt[0] for pt in kz.points]
            kz_ys = [pt[1] for pt in kz.points]
            kz_min_x, kz_max_x = min(kz_xs) - 0.5, max(kz_xs) + 0.5
            kz_min_y, kz_max_y = min(kz_ys) - 0.5, max(kz_ys) + 0.5
            min_gx = int(kz_min_x / grid_size)
            max_gx = int(kz_max_x / grid_size)
            min_gy = int(kz_min_y / grid_size)
            max_gy = int(kz_max_y / grid_size)
            for gx in range(min_gx, max_gx + 1):
                for gy in range(min_gy, max_gy + 1):
                    for l_idx in [0, 1]:
                        occupied[(l_idx, gx, gy)] = "KEEPOUT_BODY"

        # 2. Block pad copper cells AND clearance margin in occupied grid
        net_pad_cells_map = {} # net_name -> set of (l_idx, gx, gy)
        for fp in self._footprints:
            rad = math.radians(fp.rotation)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            for p in fp.pads:
                px = fp.x + p.x * cos_r - p.y * sin_r
                py = fp.y + p.x * sin_r + p.y * cos_r
                gx, gy = int(round(px / grid_size)), int(round(py / grid_size))
                is_npth = (not p.net_name or "np_thru_hole" in p.pad_type or p.number == "MP")
                pad_layers = [0, 1] if (is_npth or "thru_hole" in p.pad_type or "*.Cu" in p.layers) else ([1] if ("B.Cu" in p.layers or fp.layer == "B.Cu") else [0])
                
                if is_npth:
                    p_dr = getattr(p, "drill", 0.0) or 0.65
                    np_rad = p_dr / 2.0 + 0.55
                    search_r = int(math.ceil(np_rad / grid_size))
                    for dx in range(-search_r, search_r + 1):
                        for dy in range(-search_r, search_r + 1):
                            cx = (gx + dx) * grid_size
                            cy = (gy + dy) * grid_size
                            if math.hypot(cx - px, cy - py) <= np_rad:
                                for l_idx in (0, 1):
                                    occupied[(l_idx, gx + dx, gy + dy)] = "KEEPOUT_BODY"
                    continue

                eff_w = max(p.w, getattr(p, "drill", 0.0), 0.2)
                eff_h = max(p.h, getattr(p, "drill", 0.0), 0.2)
                half_w, half_h = eff_w / 2.0, eff_h / 2.0
                cl_margin = 0.18 if "thru_hole" in p.pad_type else 0.15
                
                search_rx = int(math.ceil((half_w + cl_margin) / grid_size)) + 1
                search_ry = int(math.ceil((half_h + cl_margin) / grid_size)) + 1
                
                for dx in range(-search_rx, search_rx + 1):
                    for dy in range(-search_ry, search_ry + 1):
                        cx = (gx + dx) * grid_size
                        cy = (gy + dy) * grid_size
                        
                        dist_x = abs(cx - px)
                        dist_y = abs(cy - py)
                        
                        is_copper = (dist_x <= half_w + 0.02) and (dist_y <= half_h + 0.02)
                        is_clearance = (dist_x <= half_w + cl_margin) and (dist_y <= half_h + cl_margin)
                        
                        for l_idx in pad_layers:
                            pt = (l_idx, gx + dx, gy + dy)
                            if is_copper:
                                occupied[pt] = p.net_name
                                if p.net_name:
                                    net_pad_cells_map.setdefault(p.net_name, set()).add(pt)
                            elif is_clearance:
                                if pt not in occupied:
                                    occupied[pt] = f"CLEARANCE_{p.net_name}"
                                else:
                                    occ = occupied[pt]
                                    if occ.startswith("CLEARANCE_") and occ != f"CLEARANCE_{p.net_name}":
                                        occupied[pt] = "CLEARANCE_CONFLICT"

        # 2b. Block all Mounting Holes with full pad/clearance envelope as KEEPOUT_BODY
        for mh in self._mounting_holes:
            mh_gx, mh_gy = int(mh.x / grid_size), int(mh.y / grid_size)
            mh_rad_cells = int(math.ceil((mh.pad_mm / 2.0 + 0.3) / grid_size))
            for l_idx in (0, 1):
                for dx in range(-mh_rad_cells, mh_rad_cells + 1):
                    for dy in range(-mh_rad_cells, mh_rad_cells + 1):
                        if dx*dx + dy*dy <= mh_rad_cells * mh_rad_cells:
                            occupied[(l_idx, mh_gx + dx, mh_gy + dy)] = "KEEPOUT_BODY"

        # 2c. Precompute via keepout envelope (mounting holes + all footprint pads)
        via_keepout_cells = set()
        for mh in self._mounting_holes:
            mh_gx, mh_gy = int(mh.x / grid_size), int(mh.y / grid_size)
            rad_cells = int(math.ceil((mh.drill_mm / 2.0 + 0.8) / grid_size))
            for dx in range(-rad_cells, rad_cells + 1):
                for dy in range(-rad_cells, rad_cells + 1):
                    if dx*dx + dy*dy <= rad_cells * rad_cells:
                        via_keepout_cells.add((mh_gx + dx, mh_gy + dy))
                        
        for fp in self._footprints:
            rad = math.radians(fp.rotation)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            for p in fp.pads:
                px = fp.x + p.x * cos_r - p.y * sin_r
                py = fp.y + p.x * sin_r + p.y * cos_r
                p_gx, p_gy = int(round(px / grid_size)), int(round(py / grid_size))
                is_np = (not p.net_name or "np_thru_hole" in p.pad_type or p.number == "MP")
                p_dr = getattr(p, "drill", 0.0) or (0.65 if is_np else 0.0)
                pad_span = max(p.w, p.h) / 2.0
                min_d = (p_dr / 2.0 + 0.70) if is_np else ((p_dr / 2.0 + 0.55) if p_dr > 0 else (pad_span + 0.50))
                rad_cells = int(math.ceil(min_d / grid_size))
                for dx in range(-rad_cells, rad_cells + 1):
                    for dy in range(-rad_cells, rad_cells + 1):
                        if dx*dx + dy*dy <= rad_cells * rad_cells:
                            via_keepout_cells.add((p_gx + dx, p_gy + dy))

        def astar(start_px, start_py, start_l, end_px, end_py, end_l, current_net_width, net_name):
            start_x_g, start_y_g = int(start_px/grid_size), int(start_py/grid_size)
            end_loc = (int(end_px/grid_size), int(end_py/grid_size))
            # Restrict allowed copper/clearance entry strictly to start and target endpoints
            target_net_cells = set()
            for l_idx in (0, 1):
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        target_net_cells.add((l_idx, start_x_g + dx, start_y_g + dy))
                        target_net_cells.add((l_idx, end_loc[0] + dx, end_loc[1] + dy))
            
            open_set = []
            heapq.heappush(open_set, (0, (start_l if start_l != -1 else 0, start_x_g, start_y_g)))
            came_from = {}
            g_score = {(start_l if start_l != -1 else 0, start_x_g, start_y_g): 0}
            
            margin_edge = 1.0 # mm
            min_x = int((self.board.origin_x + margin_edge) / grid_size)
            max_x = int((self.board.origin_x + self.board.width_mm - margin_edge) / grid_size)
            min_y = int((self.board.origin_y + margin_edge) / grid_size)
            max_y = int((self.board.origin_y + self.board.height_mm - margin_edge) / grid_size)
            
            nodes_explored = 0
            while open_set:
                if nodes_explored > 250000:
                    return None
                _, current = heapq.heappop(open_set)
                c_l, cx, cy = current
                nodes_explored += 1
                
                if (cx, cy) == end_loc and (end_l == -1 or c_l == end_l):
                    pths = [current]
                    while current in came_from:
                        current = came_from[current]
                        pths.append(current)
                    return pths[::-1]

                # 8 planar directions (4 orthogonal + 4 diagonal) + 1 layer change (via)
                directions = [
                    (0, 1, 0, 1.0), (0, -1, 0, 1.0), (0, 0, 1, 1.0), (0, 0, -1, 1.0),
                    (0, 1, 1, 1.4142), (0, 1, -1, 1.4142), (0, -1, 1, 1.4142), (0, -1, -1, 1.4142),
                    (1, 0, 0, 8.0)
                ]

                for dl, dx, dy, step_cost in directions:
                    nb_l = c_l if dl == 0 else 1 - c_l
                    nb_x, nb_y = cx + dx, cy + dy
                    nb = (nb_l, nb_x, nb_y)
                    
                    if nb_x < min_x or nb_x > max_x or nb_y < min_y or nb_y > max_y:
                        continue
                    
                    # For diagonal moves, ensure both adjacent cardinal cells are strictly clear of other nets
                    if dl == 0 and dx != 0 and dy != 0:
                        card1 = (c_l, cx + dx, cy)
                        card2 = (c_l, cx, cy + dy)
                        diag_corner_blocked = False
                        for c_pt in (card1, card2):
                            if c_pt in occupied:
                                c_occ = occupied[c_pt]
                                if c_occ == "KEEPOUT_BODY" or (c_occ != net_name and not c_occ.startswith(f"CLEARANCE_{net_name}")):
                                    if c_pt not in target_net_cells:
                                        diag_corner_blocked = True
                                        break
                        if diag_corner_blocked:
                            continue

                    cost = step_cost
                    if nb in occupied:
                        occ_val = occupied[nb]
                        if occ_val == "KEEPOUT_BODY":
                            continue  # Absolutely NEVER enter IC/MCU body interiors!
                        
                        if occ_val.startswith("CLEARANCE_") or occ_val == "CLEARANCE_CONFLICT":
                            cl_net = occ_val.replace("CLEARANCE_", "")
                            if cl_net != net_name:
                                if nb not in target_net_cells:
                                    continue # Hard block across board
                        elif occ_val != net_name:
                            # Hard block for different net's exact copper
                            if nb not in target_net_cells:
                                continue
                    if current_net_width > self.default_trace_width and dl == 0:
                        if nb not in target_net_cells:
                            thick_blocked = False
                            for vx, vy in ((1,0), (-1,0), (0,1), (0,-1)):
                                v_nb = (nb_l, nb_x + vx, nb_y + vy)
                                if v_nb in occupied:
                                    vocc = occupied[v_nb]
                                    if vocc.startswith("CLEARANCE_") and vocc != f"CLEARANCE_{net_name}":
                                        thick_blocked = True
                                        break
                                    elif vocc == "CLEARANCE_CONFLICT":
                                        thick_blocked = True
                                        break
                            if thick_blocked: continue
                        
                    if dl != 0:
                        if (nb_x, nb_y) in via_keepout_cells:
                            continue
                            
                        via_blocked = False
                        curr_via_x, curr_via_y = nb_x * grid_size, nb_y * grid_size
                                
                        # 3. Check distance to existing vias (min 0.8mm)
                        for ev in self._vias:
                            if math.hypot(curr_via_x - ev.x, curr_via_y - ev.y) < 0.8:
                                via_blocked = True
                                break
                                    
                        # 4. Check 3-cell keepout envelope on both layers (0.35mm radius)
                        if not via_blocked:
                            for l_check in (0, 1):
                                for vx in range(-3, 4):
                                    for vy in range(-3, 4):
                                        if vx*vx + vy*vy <= 8:
                                            v_nb = (l_check, nb_x + vx, nb_y + vy)
                                            if v_nb in occupied:
                                                vocc = occupied[v_nb]
                                                if vocc == "KEEPOUT_BODY" or (vocc != net_name and not vocc.startswith(f"CLEARANCE_{net_name}")):
                                                    via_blocked = True
                                                    break
                                    if via_blocked: break
                                if via_blocked: break
                                    
                        if via_blocked:
                            continue
                        
                        cost = 8.0  # Via cost penalty

                    tentative_g = g_score[current] + cost
                    if nb not in g_score or tentative_g < g_score[nb]:
                        came_from[nb] = current
                        g_score[nb] = tentative_g
                        # Euclidean distance heuristic
                        h = math.hypot(nb_x - end_loc[0], nb_y - end_loc[1]) + (0 if dl == 0 else 4.0)
                        heapq.heappush(open_set, (tentative_g + h, nb))
            return None

        def _chamfer_points(pts_mm, max_c=0.6):
            if len(pts_mm) < 3:
                return pts_mm
            res = [pts_mm[0]]
            for i in range(1, len(pts_mm) - 1):
                p_prev = res[-1]
                p_curr = pts_mm[i]
                p_next = pts_mm[i + 1]
                v1_x, v1_y = p_curr[0] - p_prev[0], p_curr[1] - p_prev[1]
                l1 = math.hypot(v1_x, v1_y)
                v2_x, v2_y = p_next[0] - p_curr[0], p_next[1] - p_curr[1]
                l2 = math.hypot(v2_x, v2_y)
                if l1 < 1e-4 or l2 < 1e-4:
                    continue
                u1_x, u1_y = v1_x / l1, v1_y / l1
                u2_x, u2_y = v2_x / l2, v2_y / l2
                dot = u1_x * u2_x + u1_y * u2_y
                if dot > 0.999:
                    continue
                c = min(max_c, l1 * 0.4, l2 * 0.4)
                if c > 0.05 and dot < 0.9:
                    p1a = (p_curr[0] - u1_x * c, p_curr[1] - u1_y * c)
                    p1b = (p_curr[0] + u2_x * c, p_curr[1] + u2_y * c)
                    res.append(p1a)
                    res.append(p1b)
                else:
                    res.append(p_curr)
            res.append(pts_mm[-1])
            return res

        routed_ok = 0
        routed_failed = 0
        
        # Sort nets: long-distance nets first (they need the most routing freedom),
        # then short local nets last
        def net_sort_key(item):
            n_name, p_list = item
            if len(p_list) >= 2:
                max_dist = 0
                for i in range(len(p_list)):
                    for j in range(i + 1, len(p_list)):
                        d = math.hypot(p_list[i][0] - p_list[j][0], p_list[i][1] - p_list[j][1])
                        if d > max_dist:
                            max_dist = d
                return (0, max_dist)
            return (1, 0)

        sorted_nets = sorted(net_pads.items(), key=net_sort_key, reverse=False)

        for net_name, pads in sorted_nets:
            if len(pads) < 2: continue
            
            nid = pads[0][2]
            net_w = self.get_net_width(net_name)

            # Minimum Spanning Tree / Net Expansion routing
            connected_pads = [pads[0]]
            unconnected_pads = list(pads[1:])
            net_tree_points = [(pads[0][0], pads[0][1], pads[0][3])]

            while unconnected_pads:
                # Find closest unconnected pad to any connected tree point
                best_u_idx = 0
                best_target_pt = net_tree_points[0]
                min_dist = float('inf')

                for u_idx, u_pad in enumerate(unconnected_pads):
                    for c_pt in net_tree_points:
                        d = math.hypot(u_pad[0] - c_pt[0], u_pad[1] - c_pt[1])
                        if d < min_dist:
                            min_dist = d
                            best_u_idx = u_idx
                            best_target_pt = c_pt

                target_u = unconnected_pads.pop(best_u_idx)

                # If pad is collocated/adjacent with already connected tree point (<1.5mm on same part), mark as connected
                if min_dist < 1.5:
                    connected_pads.append(target_u)
                    continue

                path_grid = astar(
                    target_u[0], target_u[1], target_u[3],
                    best_target_pt[0], best_target_pt[1], best_target_pt[2],
                    net_w, net_name
                )

                # Fallback: attempt connecting to any other connected pad
                if not path_grid and len(connected_pads) > 1:
                    for alt_pad in connected_pads:
                        path_grid = astar(
                            target_u[0], target_u[1], target_u[3],
                            alt_pad[0], alt_pad[1], alt_pad[3],
                            net_w, net_name
                        )
                        if path_grid:
                            break

                if path_grid:
                    routed_ok += 1
                    connected_pads.append(target_u)
                    # Sample points along route to expand net tree
                    step_skip = max(1, len(path_grid) // 8)
                    for gp in path_grid[::step_skip]:
                        net_tree_points.append((gp[1] * grid_size, gp[2] * grid_size, gp[0]))

                    # Raycast string-pulling along octilinear directions (0°, 90°, 45°)
                    def _simplify_octilinear(p_list):
                        if len(p_list) <= 2:
                            return p_list
                        res = [p_list[0]]
                        idx = 0
                        while idx < len(p_list) - 1:
                            best_j = idx + 1
                            l_curr = p_list[idx][0]
                            for j in range(len(p_list) - 1, idx, -1):
                                if p_list[j][0] != l_curr:
                                    continue
                                p1 = p_list[idx]
                                p2 = p_list[j]
                                dx = p2[1] - p1[1]
                                dy = p2[2] - p1[2]
                                if dx == 0 or dy == 0 or abs(dx) == abs(dy):
                                    steps = max(abs(dx), abs(dy))
                                    step_x = dx // steps
                                    step_y = dy // steps
                                    clear = True
                                    for s in range(0, steps + 1):
                                        cx = p1[1] + s * step_x
                                        cy = p1[2] + s * step_y
                                        for cdx in (-1, 0, 1):
                                            for cdy in (-1, 0, 1):
                                                t_pt = (l_curr, cx + cdx, cy + cdy)
                                                if t_pt in occupied:
                                                    occ = occupied[t_pt]
                                                    if occ == "KEEPOUT_BODY":
                                                        clear = False
                                                        break
                                                    if occ != net_name and not occ.startswith(f"CLEARANCE_{net_name}"):
                                                        clear = False
                                                        break
                                            if not clear: break
                                        if not clear: break
                                    if clear:
                                        best_j = j
                                        break
                            res.append(p_list[best_j])
                            idx = best_j
                        return res

                    simple_path = _simplify_octilinear(path_grid)

                    start_pt = simple_path[0]
                    for gp in simple_path[1:]:
                        if start_pt != gp:
                            if start_pt[0] != gp[0]:
                                self.add_via(start_pt[1] * grid_size, start_pt[2] * grid_size, net=net_name)
                                # Mark via keepout on both layers
                                for l_idx in (0, 1):
                                    for dx in range(-4, 5):
                                        for dy in range(-4, 5):
                                            if dx*dx + dy*dy <= 16:
                                                occ_pt = (l_idx, start_pt[1] + dx, start_pt[2] + dy)
                                                if dx == 0 and dy == 0:
                                                    occupied[occ_pt] = net_name
                                                    net_pad_cells_map.setdefault(net_name, set()).add(occ_pt)
                                                else:
                                                    occupied[occ_pt] = f"CLEARANCE_{net_name}"
                            else:
                                self._traces.append(Trace(
                                    start_pt[1] * grid_size, start_pt[2] * grid_size,
                                    gp[1] * grid_size, gp[2] * grid_size,
                                    width=net_w, layer=layers[start_pt[0]], net_id=nid
                                ))
                                # Mark trace and clearance corridor along actual physical segment
                                l_idx = start_pt[0]
                                dx = gp[1] - start_pt[1]
                                dy = gp[2] - start_pt[2]
                                steps = max(abs(dx), abs(dy), 1)
                                for s in range(0, steps + 1):
                                    cx = int(round(start_pt[1] + s * dx / steps))
                                    cy = int(round(start_pt[2] + s * dy / steps))
                                    for cdx in range(-2, 3):
                                        for cdy in range(-2, 3):
                                            occ_pt = (l_idx, cx + cdx, cy + cdy)
                                            if cdx == 0 and cdy == 0:
                                                occupied[occ_pt] = net_name
                                                net_pad_cells_map.setdefault(net_name, set()).add(occ_pt)
                                            else:
                                                if occ_pt not in occupied or occupied[occ_pt] != net_name:
                                                    occupied[occ_pt] = f"CLEARANCE_{net_name}"
                            start_pt = gp
                else:
                    routed_failed += 1
                    logger.warning("pcb_layout", f"Segmento sin rutear en net '{net_name}' para pad ({target_u[0]:.2f}, {target_u[1]:.2f})")

        level = logger.warning if routed_failed else logger.info
        level(
            "pcb_layout",
            f"autoroute() finalizado: {routed_ok} segmentos ruteados, {routed_failed} fallidos "
            f"sobre {len(net_pads)} nets",
        )

    def _pad_abs(self, fp: Footprint, pad_num: str) -> Optional[tuple]:
        """Calcula posición absoluta de un pad en el PCB."""
        for p in fp.pads:
            if p.number == pad_num:
                rad = math.radians(fp.rotation)
                cos_r, sin_r = math.cos(rad), math.sin(rad)
                abs_x = fp.x + p.x * cos_r - p.y * sin_r
                abs_y = fp.y + p.x * sin_r + p.y * cos_r
                return (abs_x, abs_y)
        return None

    # ── Spatial alignment helpers ─────────────────────────────────

    def align_horizontal(self, *footprints: Footprint,
                         y: float = None) -> None:
        """Alinea footprints en el mismo eje Y."""
        if y is None:
            y = sum(fp.y for fp in footprints) / len(footprints)
        for fp in footprints:
            fp.y = y

    def align_vertical(self, *footprints: Footprint,
                       x: float = None) -> None:
        """Alinea footprints en el mismo eje X."""
        if x is None:
            x = sum(fp.x for fp in footprints) / len(footprints)
        for fp in footprints:
            fp.x = x

    def distribute_horizontal(self, *footprints: Footprint,
                               start_x: float = None,
                               spacing: float = None,
                               y: float = None) -> None:
        """Distribuye footprints uniformemente en horizontal."""
        n = len(footprints)
        if n < 2:
            return
        if y is not None:
            self.align_horizontal(*footprints, y=y)
        if start_x is None:
            start_x = footprints[0].x
        if spacing is None:
            spacing = self.board.width_mm / (n + 1)
        for i, fp in enumerate(footprints):
            fp.x = start_x + i * spacing

    def distribute_vertical(self, *footprints: Footprint,
                             start_y: float = None,
                             spacing: float = None,
                             x: float = None) -> None:
        """Distribuye footprints uniformemente en vertical."""
        n = len(footprints)
        if n < 2:
            return
        if x is not None:
            self.align_vertical(*footprints, x=x)
        if start_y is None:
            start_y = footprints[0].y
        if spacing is None:
            spacing = self.board.height_mm / (n + 1)
        for i, fp in enumerate(footprints):
            fp.y = start_y + i * spacing

    def distribute_circular(self, *footprints: Footprint,
                             center_x: float = None,
                             center_y: float = None,
                             radius: float = 10.0,
                             start_angle: float = 0.0) -> None:
        """Distribuye footprints en círculo alrededor de un centro."""
        if center_x is None:
            center_x = self.board.center_x
        if center_y is None:
            center_y = self.board.center_y
        n = len(footprints)
        for i, fp in enumerate(footprints):
            angle = math.radians(start_angle + i * (360.0 / n))
            fp.x = center_x + radius * math.cos(angle)
            fp.y = center_y + radius * math.sin(angle)
            fp.rotation = math.degrees(angle) + 90  # orient radially

    def mirror_horizontal(self, source: Footprint,
                          axis_x: float = None) -> Footprint:
        """Crea un duplicado espejado en el eje X (simetría horizontal)."""
        if axis_x is None:
            axis_x = self.board.center_x
        import copy
        mirror = copy.deepcopy(source)
        mirror.x = 2 * axis_x - source.x
        mirror.ref = source.ref + "_M"
        mirror.uuid_str = str(uuid.uuid4())
        self._footprints.append(mirror)
        return mirror

    def mirror_vertical(self, source: Footprint,
                        axis_y: float = None) -> Footprint:
        """Crea un duplicado espejado en el eje Y (simetría vertical)."""
        if axis_y is None:
            axis_y = self.board.center_y
        import copy
        mirror = copy.deepcopy(source)
        mirror.y = 2 * axis_y - source.y
        mirror.ref = source.ref + "_M"
        mirror.uuid_str = str(uuid.uuid4())
        self._footprints.append(mirror)
        return mirror

    def center(self, fp: Footprint) -> None:
        """Centra un footprint en la placa."""
        fp.x = self.board.center_x
        fp.y = self.board.center_y

    def add_mounting_holes_corners(self, margin: float = 3.5,
                                    drill: float = 3.2) -> list[MountingHole]:
        """Coloca 4 agujeros de montaje M3 en las esquinas."""
        ox, oy = self.board.origin_x, self.board.origin_y
        w, h = self.board.width_mm, self.board.height_mm
        holes = [
            self.add_mounting_hole(ox + margin, oy + margin, drill),
            self.add_mounting_hole(ox + w - margin, oy + margin, drill),
            self.add_mounting_hole(ox + margin, oy + h - margin, drill),
            self.add_mounting_hole(ox + w - margin, oy + h - margin, drill),
        ]
        return holes

    # ── Export ─────────────────────────────────────────────────────

    def to_kicad_pcb(self) -> str:
        """Genera el archivo .kicad_pcb completo en formato S-expression."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Header
        lines = [
            '(kicad_pcb (version 20240108) (generator "PulseLab Forge")',
            '  (general',
            '    (thickness 1.6)',
            '    (legacy_teardrops no)',
            '  )',
            '',
            '  (paper "A4")',
            '',
            f'  (title_block',
            f'    (title "{self.project_name}")',
            f'    (date "{now}")',
            f'    (company "PulseLab Forge")',
            f'  )',
            '',
        ]

        # Layers
        lines.append('  (layers')
        lines.append('    (0 "F.Cu" signal)')
        lines.append('    (31 "B.Cu" signal)')
        lines.append('    (32 "B.Adhes" user "B.Adhesive")')
        lines.append('    (33 "F.Adhes" user "F.Adhesive")')
        lines.append('    (34 "B.Paste" user)')
        lines.append('    (35 "F.Paste" user)')
        lines.append('    (36 "B.SilkS" user "B.Silkscreen")')
        lines.append('    (37 "F.SilkS" user "F.Silkscreen")')
        lines.append('    (38 "B.Mask" user "B.Mask")')
        lines.append('    (39 "F.Mask" user "F.Mask")')
        lines.append('    (40 "Dwgs.User" user "User.Drawings")')
        lines.append('    (41 "Cmts.User" user "User.Comments")')
        lines.append('    (42 "Eco1.User" user "User.Eco1")')
        lines.append('    (43 "Eco2.User" user "User.Eco2")')
        lines.append('    (44 "Edge.Cuts" user)')
        lines.append('    (45 "Margin" user)')
        lines.append('    (46 "B.CrtYd" user "B.Courtyard")')
        lines.append('    (47 "F.CrtYd" user "F.Courtyard")')
        lines.append('    (48 "B.Fab" user "B.Fab")')
        lines.append('    (49 "F.Fab" user "F.Fab")')
        lines.append('  )')
        lines.append('')

        # Setup (design rules)
        lines.append('  (setup')
        lines.append('    (pad_to_mask_clearance 0.05)')
        lines.append('    (solder_mask_min_width 0.1)')
        lines.append('    (pcbplotparams')
        lines.append('      (layerselection 0x00010fc_ffffffff)')
        lines.append('      (outputdirectory "gerbers/")')
        lines.append('    )')
        lines.append('  )')
        lines.append('')

        # Ensure all used net names are registered in self._nets
        for fp in self._footprints:
            for p in fp.pads:
                if p.net_name:
                    p.net_id = self._get_net_id(p.net_name)
        for t in self._traces:
            if hasattr(t, 'net_name') and t.net_name:
                t.net_id = self._get_net_id(t.net_name)

        # Ensure GND copper pour zones exist for F.Cu and B.Cu
        if not self._zones:
            gnd_name = "PWR_GND" if "PWR_GND" in self._nets else ("GND" if "GND" in self._nets else "PWR_GND")
            self.add_copper_pour(net=gnd_name, layer="F.Cu", margin=0.5, priority=1)
            self.add_copper_pour(net=gnd_name, layer="B.Cu", margin=0.5, priority=1)
            if "PWR_GND_FLIPPER" in self._nets:
                self.add_copper_pour(net="PWR_GND_FLIPPER", layer="F.Cu", margin=0.5, priority=0)
                self.add_copper_pour(net="PWR_GND_FLIPPER", layer="B.Cu", margin=0.5, priority=0)

        # Netclasses — use configured default_trace_width instead of hardcoded 0.25
        lines.append('  (net_class "Default" "Default netclass"')
        lines.append('    (clearance 0.12)')
        lines.append(f'    (trace_width {self.default_trace_width:.4f})')
        lines.append('    (via_dia 0.6)')
        lines.append('    (via_drill 0.3)')
        lines.append('    (uvia_dia 0.3)')
        lines.append('    (uvia_drill 0.1)')
        lines.append('  )')
        lines.append('')

        # Nets
        lines.append('  (net 0 "")')
        for name, nid in sorted(self._nets.items(), key=lambda x: x[1]):
            if nid > 0:
                lines.append(f'  (net {nid} "{name}")')
        lines.append('')

        # Board outline
        lines.append(self.board.to_sexpr())
        lines.append('')

        # Title text
        cx = self.board.center_x
        cy = self.board.origin_y + self.board.height_mm + 3
        lines.append(
            f'  (gr_text "{self.project_name}" (at {cx:.3f} {cy:.3f}) '
            f'(layer "F.SilkS") (uuid "{uuid.uuid4()}") '
            f'(effects (font (size 1.5 1.5) (thickness 0.15))))'
        )

        # User text items
        for t in self._text_items:
            lines.append(t)
        lines.append('')

        # Footprints
        for fp in self._footprints:
            lines.append(fp.to_sexpr())

        # Mounting holes
        for hole in self._mounting_holes:
            lines.append(hole.to_sexpr())
        lines.append('')

        # Traces
        for t in self._traces:
            lines.append(t.to_sexpr())
        lines.append('')

        # Vias
        for v in self._vias:
            lines.append(v.to_sexpr())

        # Zonas (Copper Pours)
        if self._zones:
            lines.append('')
            for z in self._zones:
                lines.append(z.to_sexpr())

        # Keepouts
        if self._keepouts:
            lines.append('')
            for kz in self._keepouts:
                lines.append(kz.to_sexpr())

        lines.append(')')
        return "\n".join(lines)

    def to_kicad_pro(self, filename: str) -> str:
        """Genera el JSON mínimo para cargar el entorno del proyecto (.kicad_pro)."""
        import json
        return json.dumps({
            "board": {},
            "cvpcb": {"equivalence_files": []},
            "erc": {"erc_exclusions": [], "meta": {"version": 0}, "pin_versions": []},
            "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
            "meta": {"filename": filename, "version": 1},
            "netlists": [],
            "pcbnew": {"last_paths": {"none": ""}, "page_layout_descr_file": ""},
            "schematic": {"annotate_start_num": 0, "drawing": {}, "legacy_lib_dir": "", "legacy_lib_list": []},
            "sheets": []
        }, indent=2)

    def save(self, path: str | Path) -> Path:
        """Guarda el PCB y el archivo de proyecto (.kicad_pro)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_kicad_pcb(), encoding="utf-8")
        
        # Guardar archivo de proyecto de KiCad adjunto
        pro_path = path.with_suffix('.kicad_pro')
        pro_path.write_text(self.to_kicad_pro(pro_path.name), encoding="utf-8")
        
        return path

    def export_enclosure(self, output_dir: Path) -> dict:
        """Exporta el encapsulado 3D de la placa."""
        from bridge.enclosure_engine import EnclosureGenerator
        eng = EnclosureGenerator(self)
        return eng.export(output_dir, basename=self.project_name.lower().replace(" ", "_"))

    def stats(self) -> dict:
        return {
            "board_mm": f"{self.board.width_mm}×{self.board.height_mm}",
            "footprints": len(self._footprints),
            "traces": len(self._traces),
            "vias": len(self._vias),
            "nets": len(self._nets) - 1,
            "mounting_holes": len(self._mounting_holes),
        }
