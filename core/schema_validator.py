"""
schema_validator.py
===================
Pydantic JSON Schema Validation & Auto-Placement Pipeline.
Enforces strict circuit schemas for LLM structured outputs and automatically
triggers 2D AutoPlacementEngine when coordinates are omitted.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator

from core.auto_placement import AutoPlacementEngine

class NetClassParams(BaseModel):
    clearance: float = Field(default=0.12, description="Clearance in mm")
    trace_width: float = Field(default=0.15, description="Trace width in mm")
    via_dia: float = Field(default=0.6, description="Via outer diameter in mm")
    via_drill: float = Field(default=0.3, description="Via drill diameter in mm")
    nets: Optional[List[str]] = Field(default=None, description="Nets bound to this netclass")

class ComponentSpec(BaseModel):
    etype: str = Field(..., description="Component type: MCU, IC, Connector, R, C, Button, LED, Header")
    value: str = Field(..., description="Component value e.g. 10k, 100nF, ESP32-S3-WROOM-1U")
    symbol: Optional[str] = Field(default="Device:R", description="KiCad symbol library identifier")
    footprint: Optional[str] = Field(default=None, description="KiCad footprint identifier")
    footprint_id: Optional[str] = Field(default=None, description="Preset footprint ID")
    position: Optional[List[float]] = Field(default=None, description="[X, Y] coordinates in mm")
    rotation: float = Field(default=0.0, description="Rotation angle in degrees")
    pins: Optional[Dict[str, str]] = Field(default=None, description="Pin number/name to net mapping")
    n1: Optional[str] = Field(default=None, description="Pin 1 net for 2-pin passive components")
    n2: Optional[str] = Field(default=None, description="Pin 2 net for 2-pin passive components")
    label: str = Field(..., description="Unique component designator (e.g. U1, R1, C1, J1)")
    jlcpcb_part: Optional[str] = Field(default=None, description="LCSC / JLCPCB Part Number (e.g. C165948)")

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        v_clean = v.strip().upper()
        if not v_clean:
            raise ValueError("Component label cannot be empty")
        return v_clean

class CircuitDesignSchema(BaseModel):
    name: str = Field(default="PulseLab Automated Design", description="Project name")
    version: str = Field(default="0.1.0", description="Design version")
    board_width: float = Field(default=75.0, description="Board width in mm")
    board_height: float = Field(default=50.0, description="Board height in mm")
    net_classes: Dict[str, NetClassParams] = Field(
        default_factory=lambda: {
            "Default": NetClassParams(clearance=0.12, trace_width=0.15, via_dia=0.6, via_drill=0.3),
            "Power": NetClassParams(clearance=0.15, trace_width=0.50, via_dia=0.8, via_drill=0.4, nets=["PWR_5V_USB", "PWR_3V3_ESP"])
        }
    )
    circuit: List[ComponentSpec] = Field(..., description="List of components in the circuit")

    def process_and_auto_place(self) -> Dict[str, Any]:
        """Validates circuit data and auto-places unpositioned components."""
        data_dict = self.model_dump()
        circuit_comps = data_dict.get("circuit", [])
        
        # Check if positions are missing
        missing_positions = any(c.get("position") is None for c in circuit_comps)
        
        if missing_positions:
            engine = AutoPlacementEngine(self.board_width, self.board_height)
            circuit_comps = engine.compute_placement(circuit_comps)
            data_dict["circuit"] = circuit_comps
            
        return data_dict
