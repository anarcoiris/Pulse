"""bridge — Integración con KiCad (SKiDL + kicad-cli + pcbnew)."""
from .kicad_bridge import KiCadBridge
from .gerber_export import export_gerbers, export_drill, export_position
from .bom_generator import generate_bom
from .pcb_layout import PCBLayout, FootprintPresets

__all__ = ['KiCadBridge', 'export_gerbers', 'export_drill',
           'export_position', 'generate_bom',
           'PCBLayout', 'FootprintPresets']
