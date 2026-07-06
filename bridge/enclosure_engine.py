"""
bridge/enclosure_engine.py
==========================
Generador de encapsulados 3D para placas diseñadas en PulseLab Forge.

Genera archivos OpenSCAD (.scad) basados en la geometría 
(dimensiones del PCB, agujeros de montaje) del objeto PCBLayout.
Éste es el enfoque CSG avanzado: paramétrico y fácil de previsualizar.
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bridge.pcb_layout import PCBLayout


class EnclosureGenerator:
    """ Generador paramétrico de cajas para un PCBLayout vía OpenSCAD. """

    def __init__(self, pcb: 'PCBLayout'):
        self.pcb = pcb
        self.w = pcb.board.width_mm
        self.h = pcb.board.height_mm
        self.rx = pcb.board.origin_x
        self.ry = pcb.board.origin_y
        
        # Parámetros de la caja
        self.wall = 2.0
        self.base_z = 2.0
        self.clearance = 0.5  # holgura entre PCB y paredes interiores
        
        self.standoff_h = 5.0 # altura de los pilares debajo de la placa
        self.lip_h = 2.0      # junta de ensamble
        
    def generate_scad(self) -> str:
        """Genera el código fuente de OpenSCAD."""
        scad = [
            f"// PulseLab Forge Enclosure for: {self.pcb.project_name}",
            f"// Auto-generated parametric model",
            "",
            "/* [Parámetros Generales] */",
            f"board_w = {self.w};",
            f"board_h = {self.h};",
            f"wall = {self.wall};",
            f"clearance = {self.clearance};",
            f"standoff_h = {self.standoff_h};",
            f"base_z = {self.base_z};",
            f"lip_h = {self.lip_h};",
            f"total_inner_h = standoff_h + 15; // Altura interior total aproximada",
            "",
            "$fn = 50;",
            "",
            "// Cálculos derivados",
            "inner_w = board_w + clearance * 2;",
            "inner_h = board_h + clearance * 2;",
            "outer_w = inner_w + wall * 2;",
            "outer_h = inner_h + wall * 2;",
            "",
            "module rounded_rect(w, h, r, height) {",
            "    hull() {",
            "        translate([r, r, 0]) cylinder(r=r, h=height);",
            "        translate([w-r, r, 0]) cylinder(r=r, h=height);",
            "        translate([w-r, h-r, 0]) cylinder(r=r, h=height);",
            "        translate([r, h-r, 0]) cylinder(r=r, h=height);",
            "    }",
            "}",
            "",
            "module boss() {",
            "    difference() {",
            "        cylinder(h=standoff_h, d=6); // Pilar externo",
            "        translate([0,0,-1]) cylinder(h=standoff_h+2, d=2.8); // Agujero para tornillo autorroscante M3",
            "    }",
            "}",
            "",
            "module bottom_shell() {",
            "    difference() {",
            "        // Base exterior sólida",
            "        translate([-wall - clearance, -wall - clearance, 0])",
            "            rounded_rect(outer_w, outer_h, 3, base_z + standoff_h + lip_h);",
            "        ",
            "        // Vaciado interior principal",
            "        translate([-clearance, -clearance, base_z])",
            "            rounded_rect(inner_w, inner_h, 2, standoff_h + lip_h + 1);",
            "            ",
            "        // Vaciado para escalón de encaje (Lip)",
            "        translate([-clearance - wall/2, -clearance - wall/2, base_z + standoff_h])",
            "            rounded_rect(inner_w + wall, inner_h + wall, 2, lip_h + 1);",
            "    }",
            "    ",
            "    // Añadir Pilares de montaje",
        ]
        
        # Compensar por si el origin_x, origin_y de la placa no es 0,0
        for mh in self.pcb._mounting_holes:
            bx = mh.x - self.rx
            by = mh.y - self.ry
            scad.append(f"    translate([{bx:.3f}, {by:.3f}, base_z]) boss();")
            
        scad.extend([
            "}",
            "",
            "module top_shell() {",
            "    // Parte superior de la caja (tapa)",
            "    top_h = total_inner_h - standoff_h;",
            "    translate([0, outer_h + 10, 0]) { // Mover a un lado",
            "        difference() {",
            "            // Techo exterior",
            "            translate([-wall - clearance, -wall - clearance, 0])",
            "                rounded_rect(outer_w, outer_h, 3, base_z + top_h);",
            "            ",
            "            // Vaciado interior",
            "            translate([-clearance, -clearance, base_z])",
            "                rounded_rect(inner_w, inner_h, 2, top_h + 1);",
            "        }",
            "        // Borde de encaje (Rim)",
            "        translate([-clearance - wall/2 + 0.1, -clearance - wall/2 + 0.1, base_z + top_h])",
            "            difference() {",
            "                rounded_rect(inner_w + wall - 0.2, inner_h + wall - 0.2, 2, lip_h);",
            "                translate([wall/2, wall/2, -1])",
            "                    rounded_rect(inner_w - 0.2, inner_h - 0.2, 1, lip_h + 2);",
            "            }",
            "    }",
            "}",
            "",
            "// Representación unificada",
            "bottom_shell();",
            "top_shell();"
        ])
        
        return "\n".join(scad)

    def export(self, output_dir: Path, basename: str = "enclosure") -> dict:
        """ Exporta los diseños y devuelve el diccionario de resultados. """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        scad_path = output_dir / f"{basename}.scad"
        scad_path.write_text(self.generate_scad(), encoding="utf-8")
        
        return {
            "success": True,
            "scad_file": str(scad_path),
            "info": "Para obtener el STL, abre el archivo .scad en OpenSCAD y exporta (F6 -> F7)."
        }
