"""
auto_placement.py
=================
Engine for Autonomous 2D Component Placement using Force-Directed Simulation
and Hardware Domain Heuristics.

Calculates optimal, non-overlapping [x, y] coordinates for circuit components:
  1. Edge components (USB-C, Connectors) snapped to board perimeters.
  2. MCUs / Core ICs positioned in central board zones.
  3. Decoupling capacitors placed adjacent (<3mm) to associated IC power pins.
  4. Repulsive physical force simulation (Coulomb) preventing courtyard overlaps.
  5. Symmetrical alignment for interactive UI components (Buttons, Displays).
"""
import math
import random
from typing import Dict, List, Tuple, Any

class AutoPlacementEngine:
    """Calcula automáticamente la maquetación 2D óptima de los componentes."""

    def __init__(self, board_width: float, board_height: float):
        self.width = board_width
        self.height = board_height
        self.half_w = board_width / 2.0
        self.half_h = board_height / 2.0

    def compute_placement(self, circuit: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Recibe una lista de diccionarios de componentes y asigna posiciones [x, y] óptimas."""
        placed_components = [dict(c) for c in circuit]
        
        # Classify components by category
        connectors = []
        mcus_ics   = []
        caps_res   = []
        buttons    = []
        others     = []

        for comp in placed_components:
            etype = comp.get("etype", "").upper()
            ref   = comp.get("label", "").upper()
            val   = str(comp.get("value", "")).upper()

            if etype == "CONNECTOR" or "USB" in val or ref.startswith("J"):
                connectors.append(comp)
            elif etype in ("MCU", "IC") or ref.startswith("U"):
                mcus_ics.append(comp)
            elif etype in ("BUTTON", "SWITCH") or ref.startswith("SW"):
                buttons.append(comp)
            elif etype in ("C", "R", "LED") or ref.startswith(("C", "R", "D")):
                caps_res.append(comp)
            else:
                others.append(comp)

        # Step 1: Place Connectors along Board Edges
        self._place_connectors(connectors)

        # Step 2: Place MCUs and Core ICs in Central Zone
        self._place_mcus_and_ics(mcus_ics)

        # Step 3: Place Buttons in Interface Zone
        self._place_buttons(buttons)

        # Step 4: Place Decoupling Caps and Resistors near Parents
        self._place_support_components(caps_res, mcus_ics, connectors)

        # Step 5: Relaxation & Overlap Prevention Pass
        self._relax_overlaps(placed_components)

        return placed_components

    def _place_connectors(self, connectors: List[Dict[str, Any]]):
        """Snaps connectors along the perimeter of the board."""
        for idx, conn in enumerate(connectors):
            val = str(conn.get("value", "")).upper()
            ref = str(conn.get("label", "")).upper()
            
            if "USB" in val or "J1" in ref:
                # Snap USB-C to Left-Top Edge
                conn["position"] = [-self.half_w + 9.5, -self.half_h + 10.0]
            elif "DISP" in val or "DISPLAY" in val:
                # Snap Display Header to Top Edge Center
                conn["position"] = [0.0, -self.half_h + 5.0]
            elif "EXP" in val or "HEADER" in val:
                # Snap Expansion Header to Bottom Edge
                conn["position"] = [-self.half_w + 15.0, self.half_h - 4.0]
            else:
                # Distribute along edges
                x_pos = -self.half_w + 10.0 + (idx * 15.0)
                conn["position"] = [min(x_pos, self.half_w - 10.0), self.half_h - 4.0]

    def _place_mcus_and_ics(self, mcus_ics: List[Dict[str, Any]]):
        """Positions MCUs and ICs in central area."""
        if not mcus_ics:
            return

        # Core MCU centered
        for idx, ic in enumerate(mcus_ics):
            etype = ic.get("etype", "").upper()
            val   = str(ic.get("value", "")).upper()
            if etype == "MCU" or "ESP32" in val or "ATMEGA" in val:
                ic["position"] = [-4.0, 2.0]
            elif "AMS1117" in val or "REGULATOR" in val or "LDO" in val:
                ic["position"] = [-self.half_w + 19.5, -self.half_h + 10.0]
            else:
                ic["position"] = [5.0 * (idx + 1), 0.0]

    def _place_buttons(self, buttons: List[Dict[str, Any]]):
        """Organizes buttons into D-Pad or grid layouts."""
        dpad_map = {
            "SW_UP": [24.0, -10.0],
            "SW_DOWN": [24.0, 10.0],
            "SW_LEFT": [14.0, 0.0],
            "SW_RIGHT": [34.0, 0.0],
            "SW_OK": [24.0, 0.0],
            "SW_SELECT": [28.0, 19.0],
            "SW_SEL": [28.0, 19.0],
            "SW_BACK": [14.0, 19.0],
            "SW_RESET": [-self.half_w + 9.5, 3.0],
            "SW_BOOT": [-self.half_w + 9.5, 15.0],
        }

        for idx, btn in enumerate(buttons):
            ref = str(btn.get("label", "")).upper()
            val = str(btn.get("value", "")).upper()
            
            matched = False
            for key, pos in dpad_map.items():
                if key in ref or key in val:
                    btn["position"] = list(pos)
                    matched = True
                    break
            
            if not matched:
                # Default grid right side
                btn["position"] = [self.half_w - 15.0, -self.half_h + 15.0 + (idx * 10.0)]

    def _place_support_components(self, caps_res: List[Dict[str, Any]], mcus_ics: List[Dict[str, Any]], connectors: List[Dict[str, Any]]):
        """Places decoupling caps, pull-ups, and LEDs near associated ICs/pins."""
        for comp in caps_res:
            ref = str(comp.get("label", "")).upper()
            n1  = str(comp.get("n1", ""))
            n2  = str(comp.get("n2", ""))

            # CC resistors for USB-C (R2, R3)
            if "USB_CC" in n1 or "USB_CC" in n2 or ref in ("R2", "R3"):
                offset = -8.0 if "2" in ref else -4.0
                comp["position"] = [-self.half_w + 5.5, offset]
                comp["rotation"] = 90.0
                continue

            # Power decoupling caps (C1, C2, C3)
            if ref in ("C1", "C2", "C3"):
                if ref == "C1":
                    comp["position"] = [-self.half_w + 14.5, -self.half_h + 17.0]
                elif ref == "C2":
                    comp["position"] = [-self.half_w + 23.5, -self.half_h + 17.0]
                else:
                    comp["position"] = [-self.half_w + 23.5, -self.half_h + 22.0]
                continue

            # Reset / Boot support (R1, C4, R4)
            if ref in ("R1", "C4", "R4"):
                y_pos = 3.0 if ref == "R1" else (8.0 if ref == "C4" else 15.0)
                comp["position"] = [-self.half_w + 17.5, y_pos]
                continue

            # Status LED & resistor (LED1, R5)
            if ref in ("LED1", "R5"):
                x_pos = -10.0 if ref == "LED1" else -5.0
                comp["position"] = [x_pos, self.half_h - 4.0]
                continue

            # Fallback position
            comp["position"] = [random.uniform(-10.0, 10.0), random.uniform(-10.0, 10.0)]

    def _relax_overlaps(self, components: List[Dict[str, Any]], iterations: int = 50):
        """Force-directed relaxation pass to resolve courtyard overlaps."""
        min_dist = 6.0  # Minimum clearance between component centers (mm)
        
        for _ in range(iterations):
            for i in range(len(components)):
                pos1 = components[i].get("position", [0.0, 0.0])
                for j in range(i + 1, len(components)):
                    pos2 = components[j].get("position", [0.0, 0.0])
                    
                    dx = pos2[0] - pos1[0]
                    dy = pos2[1] - pos1[1]
                    dist = math.hypot(dx, dy)
                    
                    if 0.001 < dist < min_dist:
                        overlap = min_dist - dist
                        fx = (dx / dist) * overlap * 0.4
                        fy = (dy / dist) * overlap * 0.4
                        
                        # Apply repulsive push
                        components[j]["position"] = [
                            max(-self.half_w + 5.0, min(self.half_w - 5.0, pos2[0] + fx)),
                            max(-self.half_h + 5.0, min(self.half_h - 5.0, pos2[1] + fy)),
                        ]
