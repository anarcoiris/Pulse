"""
bridge/pcb_layout.py
====================
Generador programático de archivos .kicad_pcb (KiCad 8 S-expression format).

Permite crear PCBs completos desde Python con control espacial:
  - Posición (x, y) en mm
  - Rotación (0°, 90°, 180°, 270°)
  - Alineación por ejes de simetría
  - Distribución automática (grid, circular, lineal)
  - Trazas (traces) entre pads con rutas ortogonales
  - Zonas de cobre (copper pours) para GND
  - Outline del PCB (Edge.Cuts)

Formato de archivo: KiCad 8.0 S-expression (.kicad_pcb)
Ref: https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/

Nota de diseño:
  No importamos pcbnew — generamos el S-expression directamente.
  Esto significa que NO necesitamos KiCad instalado para generar el .kicad_pcb.
  Solo necesitamos kicad-cli para el paso final de exportación a Gerber.
"""

from __future__ import annotations
import math
import uuid
import datetime
import heapq
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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

    def __post_init__(self):
        if self.layers is None:
            if self.pad_type == "thru_hole":
                self.layers = ["*.Cu", "*.Mask"]
            else:
                self.layers = ["F.Cu", "F.Paste", "F.Mask"]

    def to_sexpr(self) -> str:
        drill_str = f" (drill {self.drill})" if self.drill > 0 else ""
        layers_str = " ".join(f'"{ly}"' for ly in self.layers)
        uid = str(uuid.uuid4())
        return (
            f'    (pad "{self.number}" {self.pad_type} {self.shape} '
            f'(at {self.x:.4f} {self.y:.4f}) '
            f'(size {self.w:.4f} {self.h:.4f}){drill_str} '
            f'(layers {layers_str}) '
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

    def to_sexpr(self) -> str:
        rotation_str = f" {self.rotation:.1f}" if self.rotation != 0 else ""
        pad_lines = "\n".join(p.to_sexpr() for p in self.pads)
        silk = self.layer.replace('Cu', 'SilkS')
        fab  = self.layer.replace('Cu', 'Fab')
        return (
            f'  (footprint "{self.lib_id}"\n'
            f'    (layer "{self.layer}")\n'
            f'    (uuid "{self.uuid_str}")\n'
            f'    (at {self.x:.4f} {self.y:.4f}{rotation_str})\n'
            f'    (property "Reference" "{self.ref}"\n'
            f'      (at 0 -2.5)\n'
            f'      (layer "{silk}")\n'
            f'      (uuid "{uuid.uuid4()}")\n'
            f'      (effects (font (size 1 1) (thickness 0.15)))\n'
            f'    )\n'
            f'    (property "Value" "{self.value}"\n'
            f'      (at 0 2.5)\n'
            f'      (layer "{fab}")\n'
            f'      (uuid "{uuid.uuid4()}")\n'
            f'      (effects (font (size 1 1) (thickness 0.15)))\n'
            f'    )\n'
            f'{pad_lines}\n'
            f'  )'
        )


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
        if r < 0.1:
            # Esquinas cuadradas — 4 líneas
            return "\n".join([
                f'  (gr_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y0:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
                f'  (gr_line (start {x1:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
                f'  (gr_line (start {x1:.3f} {y1:.3f}) (end {x0:.3f} {y1:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
                f'  (gr_line (start {x0:.3f} {y1:.3f}) (end {x0:.3f} {y0:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))',
            ])
        else:
            # Esquinas redondeadas — líneas + arcos
            lines = []
            # Top edge
            lines.append(f'  (gr_line (start {x0+r:.3f} {y0:.3f}) (end {x1-r:.3f} {y0:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Top-right arc
            lines.append(f'  (gr_arc (start {x1-r:.3f} {y0:.3f}) (mid {x1-r+r*0.707:.3f} {y0+r-r*0.707:.3f}) (end {x1:.3f} {y0+r:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Right edge
            lines.append(f'  (gr_line (start {x1:.3f} {y0+r:.3f}) (end {x1:.3f} {y1-r:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Bottom-right arc
            lines.append(f'  (gr_arc (start {x1:.3f} {y1-r:.3f}) (mid {x1-r+r*0.707:.3f} {y1-r+r*0.707:.3f}) (end {x1-r:.3f} {y1:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Bottom edge
            lines.append(f'  (gr_line (start {x1-r:.3f} {y1:.3f}) (end {x0+r:.3f} {y1:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Bottom-left arc
            lines.append(f'  (gr_arc (start {x0+r:.3f} {y1:.3f}) (mid {x0+r-r*0.707:.3f} {y1-r+r*0.707:.3f}) (end {x0:.3f} {y1-r:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Left edge
            lines.append(f'  (gr_line (start {x0:.3f} {y1-r:.3f}) (end {x0:.3f} {y0+r:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            # Top-left arc
            lines.append(f'  (gr_arc (start {x0:.3f} {y0+r:.3f}) (mid {x0+r-r*0.707:.3f} {y0+r-r*0.707:.3f}) (end {x0+r:.3f} {y0:.3f}) (layer "Edge.Cuts") (stroke (width 0.1)))')
            return "\n".join(lines)


@dataclass
class MountingHole:
    """Agujero de montaje."""
    x: float
    y: float
    drill_mm: float = 3.2
    pad_mm: float = 6.0

    def to_sexpr(self) -> str:
        uid  = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        uid3 = str(uuid.uuid4())
        return (
            f'  (footprint "MountingHole:MountingHole_{self.drill_mm:.1f}mm_M3"\n'
            f'    (layer "F.Cu")\n'
            f'    (uuid "{uid}")\n'
            f'    (at {self.x:.4f} {self.y:.4f})\n'
            f'    (property "Reference" "H"\n'
            f'      (at 0 -4)\n'
            f'      (layer "F.SilkS")\n'
            f'      (uuid "{uid2}")\n'
            f'      (effects (font (size 1 1) (thickness 0.15)))\n'
            f'    )\n'
            f'    (pad "" thru_hole circle (at 0 0) (size {self.pad_mm:.2f} {self.pad_mm:.2f})\n'
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

    def to_sexpr(self) -> str:
        uid = str(uuid.uuid4())
        pts_str = "\n          ".join(f"(xy {x:.4f} {y:.4f})" for x, y in self.points)
        return (
            f'  (zone (net {self.net_id}) (net_name "{self.net_name}") (layer "{self.layer}") '
            f'(uuid "{uid}")\n'
            f'    (hatch edge 0.5)\n'
            f'    (connect_pads (clearance 0.2))\n'
            f'    (min_thickness 0.25)\n'
            f'    (fill (yes) (thermal_gap 0.508) (thermal_bridge_width 0.508))\n'
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
        for i in range(pins):
            fp.pads.append(Pad(
                str(i + 1), "thru_hole",
                "rect" if i == 0 else "circle",
                x=0, y=i * pitch,
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
        # Fila izquierda (pines 1..half, de arriba a abajo)
        for i in range(half):
            fp.pads.append(Pad(
                str(i + 1), "thru_hole",
                "rect" if i == 0 else "oval",
                x=-row_width / 2, y=i * pitch,
                w=1.6, h=1.6, drill=0.8,
            ))
        # Fila derecha (pines pins..half+1, de abajo a arriba)
        for i in range(half):
            fp.pads.append(Pad(
                str(pins - i), "thru_hole", "oval",
                x=+row_width / 2, y=i * pitch,
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
    def sot223(ref: str, value: str, net1_id: int = 0, net1_name: str = "",
               net2_id: int = 0, net2_name: str = "", net3_id: int = 0, net3_name: str = "") -> Footprint:
        """SOT-223-3_TabPin2: Pin1(GND/Adj), Pin2(Vout), Pin3(Vin), Pin4(Tab=Vout)"""
        fp = Footprint(ref=ref, lib_id="Package_TO_SOT_SMD:SOT-223-3_TabPin2", value=value)
        fp.pads = [
            Pad("1", "smd", "rect", x=-2.3, y=3.1, w=1.2, h=1.5, net_id=net1_id, net_name=net1_name),
            Pad("2", "smd", "rect", x=0.0,  y=3.1, w=1.2, h=1.5, net_id=net2_id, net_name=net2_name),
            Pad("3", "smd", "rect", x=2.3,  y=3.1, w=1.2, h=1.5, net_id=net3_id, net_name=net3_name),
            Pad("2", "smd", "rect", x=0.0,  y=-3.1, w=3.3, h=1.5, net_id=net2_id, net_name=net2_name), # Tab
        ]
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
                 project_name: str = "PulseLab Design"):
        self.board = BoardOutline(
            width_mm=board_width, height_mm=board_height,
            corner_radius_mm=corner_radius,
        )
        self.layers = layers
        self.default_trace_width = trace_width
        self.clearance = clearance
        self.project_name = project_name

        self._footprints: list[Footprint] = []
        self._traces: list[Trace] = []
        self._vias: list[Via] = []
        self._mounting_holes: list[MountingHole] = []
        self._zones: list[Zone] = []
        self._nets: dict[str, int] = {"": 0}  # net_name → net_id
        self._net_counter = 0
        self._text_items: list[str] = []

    # ── Net management ────────────────────────────────────────────

    def _get_net_id(self, name: str) -> int:
        if name not in self._nets:
            self._net_counter += 1
            self._nets[name] = self._net_counter
        return self._nets[name]

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

    def add_mounting_hole(self, x: float, y: float,
                          drill: float = 3.2) -> MountingHole:
        """Coloca un agujero de montaje M3."""
        hole = MountingHole(x=x, y=y, drill_mm=drill)
        self._mounting_holes.append(hole)
        return hole

    def add_text(self, text: str, x: float, y: float,
                 size: float = 1.5, layer: str = "F.SilkS") -> None:
        """Coloca texto en el PCB (silkscreen)."""
        uid = str(uuid.uuid4())
        self._text_items.append(
            f'  (gr_text "{text}" (at {x:.3f} {y:.3f}) (layer "{layer}") '
            f'(uuid "{uid}") '
            f'(effects (font (size {size:.1f} {size:.1f}) (thickness 0.15))))'
        )

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
            width = self.default_trace_width
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
            width = self.default_trace_width
        net_id = self._get_net_id(net) if net else 0
        traces = []
        for i in range(len(points) - 1):
            t = Trace(points[i][0], points[i][1],
                      points[i+1][0], points[i+1][1],
                      width, layer, net_id)
            traces.append(t)
            self._traces.append(t)
        return traces

    def add_via(self, x: float, y: float,
                size: float = 0.6, drill: float = 0.3,
                net: str = "") -> Via:
        """Coloca una vía."""
        v = Via(x, y, size, drill, self._get_net_id(net) if net else 0)
        self._vias.append(v)
        return v

    def add_copper_pour(self, net: str = "GND", layer: str = "F.Cu", margin: float = 1.0):
        """Añade plano de masa envolviendo toda el área de diseño."""
        nid = self._get_net_id(net)
        x0 = self.board.origin_x + margin
        y0 = self.board.origin_y + margin
        x1 = self.board.origin_x + self.board.width_mm - margin
        y1 = self.board.origin_y + self.board.height_mm - margin
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        self._zones.append(Zone(net_id=nid, net_name=net, layer=layer, points=pts))

    # ── Auto-Router ───────────────────────────────────────────────

    def autoroute(self, layer: str = "F.Cu", width: float = 0.25, grid_size: float = 0.25):
        """Enruta usando A* todas las nets no ruteadas en 2 capas (F.Cu y B.Cu)."""
        net_pads = {} # net_name -> list of (x, y, net_id, pad_layer)
        layers = ["F.Cu", "B.Cu"]
        
        for fp in self._footprints:
            for p in fp.pads:
                if p.net_name and p.net_name != "GND":  # GND se asume en zone
                    rad = math.radians(fp.rotation)
                    px = fp.x + p.x * math.cos(rad) - p.y * math.sin(rad)
                    py = fp.y + p.x * math.sin(rad) + p.y * math.cos(rad)
                    if p.net_name not in net_pads:
                        net_pads[p.net_name] = []
                    
                    pad_layer = 0 # F.Cu por defecto
                    if "thru_hole" in p.pad_type or "*.Cu" in p.layers:
                        pad_layer = -1 # ambas
                    elif "B.Cu" in p.layers or fp.layer == "B.Cu":
                        pad_layer = 1
                        
                    net_pads[p.net_name].append((px, py, p.net_id, pad_layer))

        if not net_pads:
            return

        occupied = set() # (layer_idx, x, y)
        for fp in self._footprints:
            for p in fp.pads:
                rad = math.radians(fp.rotation)
                px = fp.x + p.x * math.cos(rad) - p.y * math.sin(rad)
                py = fp.y + p.x * math.sin(rad) + p.y * math.cos(rad)
                gx, gy = int(px / grid_size), int(py / grid_size)
                
                pad_layers = []
                if p.pad_type == "thru_hole" or "*.Cu" in p.layers:
                    pad_layers = [0, 1]
                elif "B.Cu" in p.layers or fp.layer == "B.Cu":
                    pad_layers = [1]
                else:
                    pad_layers = [0]
                    
                # Espacio libre alrededor del pad
                pad_w_c = max(1, int(p.w / 2 / grid_size))
                pad_h_c = max(1, int(p.h / 2 / grid_size))
                for dx in range(-pad_w_c, pad_w_c + 1):
                    for dy in range(-pad_h_c, pad_h_c + 1):
                        for l_idx in pad_layers:
                            occupied.add((l_idx, gx+dx, gy+dy))

        def astar(start_px, start_py, start_l, end_px, end_py, end_l):
            start_l_act = 0 if start_l == -1 else start_l
            end_l_act = 0 if end_l == -1 else end_l
            
            start_g = (start_l_act, int(start_px/grid_size), int(start_py/grid_size))
            end_loc = (int(end_px/grid_size), int(end_py/grid_size))
            
            open_set = [(0, start_g)]
            came_from = {}
            g_score = {start_g: 0}
            directions = [(0, 1, 0), (1, 0, 0), (0, -1, 0), (-1, 0, 0), (0, 0, 1)]
            
            max_x = int(self.board.width_mm / grid_size)
            max_y = int(self.board.height_mm / grid_size)
            
            while open_set:
                _, current = heapq.heappop(open_set)
                c_l, cx, cy = current
                
                if (cx, cy) == end_loc and (end_l == -1 or c_l == end_l):
                    pths = [current]
                    while current in came_from:
                        current = came_from[current]
                        pths.append(current)
                    return pths[::-1]

                for dl, dx, dy in directions:
                    nb_l = c_l if dl == 0 else 1 - c_l
                    nb_x, nb_y = cx + dx, cy + dy
                    nb = (nb_l, nb_x, nb_y)
                    
                    if nb_x < 0 or nb_x > max_x or nb_y < 0 or nb_y > max_y:
                        continue
                        
                    is_occupied = False
                    if nb in occupied:
                        if (nb_x, nb_y) != end_loc and (nb_x, nb_y) != (start_g[1], start_g[2]):
                            is_occupied = True
                            
                    cost = 1
                    if dl != 0:
                        cost = 15  # Via cost penalty
                    if is_occupied:
                        cost = 1000  # Cruces prohibitivos
                        
                    tentative_g = g_score[current] + cost
                    if nb not in g_score or tentative_g < g_score[nb]:
                        came_from[nb] = current
                        g_score[nb] = tentative_g
                        h = abs(nb_x - end_loc[0]) + abs(nb_y - end_loc[1]) + (0 if dl == 0 else 5)
                        heapq.heappush(open_set, (tentative_g + h, nb))
            return None

        for net_name, pads in net_pads.items():
            if len(pads) < 2: continue
            nid = pads[0][2]
            for i in range(len(pads) - 1):
                p1, p2 = pads[i], pads[i+1]
                path_grid = astar(p1[0], p1[1], p1[3], p2[0], p2[1], p2[3])
                if path_grid:
                    start_pt = path_grid[0]
                    for gp in path_grid[1:]:
                        if start_pt != gp:
                            if start_pt[0] != gp[0]:
                                self.add_via(start_pt[1] * grid_size, start_pt[2] * grid_size, net=net_name)
                                occupied.add((gp[0], gp[1], gp[2]))
                            else:
                                self._traces.append(Trace(
                                    start_pt[1] * grid_size, start_pt[2] * grid_size,
                                    gp[1] * grid_size, gp[2] * grid_size,
                                    width=width, layer=layers[start_pt[0]], net_id=nid
                                ))
                            start_pt = gp
                    self._traces.append(Trace(start_pt[1] * grid_size, start_pt[2] * grid_size,
                                             p2[0], p2[1], width=width, layer=layers[start_pt[0]], net_id=nid))
                    for pt in path_grid:
                        occupied.add(pt)

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
        lines.append('    (pcbplotparams')
        lines.append('      (layerselection 0x00010fc_ffffffff)')
        lines.append('      (outputdirectory "gerbers/")')
        lines.append('    )')
        lines.append('  )')
        lines.append('')

        # Nets
        lines.append('  (net 0 "")')
        for name, nid in self._nets.items():
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

        lines.append(')')
        return "\n".join(lines)

    def save(self, path: str | Path) -> Path:
        """Guarda el PCB como archivo .kicad_pcb."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_kicad_pcb(), encoding="utf-8")
        return path

    def stats(self) -> dict:
        return {
            "board_mm": f"{self.board.width_mm}×{self.board.height_mm}",
            "footprints": len(self._footprints),
            "traces": len(self._traces),
            "vias": len(self._vias),
            "nets": len(self._nets) - 1,
            "mounting_holes": len(self._mounting_holes),
        }
