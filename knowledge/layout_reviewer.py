"""
knowledge/layout_reviewer.py
============================
Módulo de auditoría de diseño (DRC) e inspector estilístico.
Analiza objetos PCBLayout buscando colisiones espaciales, problemas
de aislamiento (clearance) e inconsistencias DFM (Design for Manufacturing).
"""

from typing import Dict, Any
import math

class LayoutReviewer:
    """Ejecuta reglas lógicas sobre el PCB para evitar fallos de producción."""
    
    def __init__(self, pcb_layout, comp_db=None):
        self.pcb = pcb_layout
        self.comp_db = comp_db
        self.issues = []
        self.proposals = []

    def audit(self, run_semantic: bool = False, backend: str = "auto") -> Dict[str, Any]:
        """Ejecuta todos los chequeos de DRC, estéticos, y opcionalmente semánticos con IA."""
        self.issues.clear()
        self.proposals.clear()
        
        self._check_out_of_bounds()
        self._check_clearance()
        
        criticals = [iss['msg'] for iss in self.issues if iss['severity'] == 'critical']
        warnings = [iss['msg'] for iss in self.issues if iss['severity'] == 'warning']
        
        result = {
            "critical_issues": criticals,
            "warnings": warnings,
            "proposals": [p for p in self.proposals],
            "passed": len(criticals) == 0
        }
        
        if run_semantic:
            try:
                import json
                from knowledge.semantic_reviewer import SemanticReviewer
                
                # Convert layout to netlist JSON
                components = []
                for fp in self.pcb._footprints:
                    ref = fp.ref
                    value = fp.value
                    
                    # Heuristics for etype
                    etype = "IC"
                    ref_upper = ref.upper()
                    if ref_upper.startswith("R"):
                        etype = "R"
                    elif ref_upper.startswith("C"):
                        etype = "C"
                    elif ref_upper.startswith("L"):
                        etype = "L"
                    elif ref_upper.startswith("D") or ref_upper.startswith("LED"):
                        etype = "S"
                    elif ref_upper.startswith("V") or ref_upper.startswith("BT") or ref_upper.startswith("BAT"):
                        etype = "V"
                    elif ref_upper.startswith("GND"):
                        etype = "GND"
                    elif ref_upper.startswith("U"):
                        if "ESP" in value.upper():
                            etype = "MCU"
                        else:
                            etype = "IC"
                    
                    pins = {}
                    for p in fp.pads:
                        pins[p.number] = p.net_name if p.net_name else "NC"
                        
                    comp_entry = {
                        "uid": ref,
                        "etype": etype,
                        "value": value,
                        "label": ref,
                        "symbol": fp.lib_id,
                        "footprint": fp.lib_id,
                    }
                    
                    if etype in ("IC", "MCU"):
                        comp_entry["pins"] = pins
                    else:
                        pad_1 = next((p for p in fp.pads if p.number == "1"), None)
                        pad_2 = next((p for p in fp.pads if p.number == "2"), None)
                        comp_entry["n1"] = pad_1.net_name if pad_1 else "NC"
                        comp_entry["n2"] = pad_2.net_name if pad_2 else "NC"
                        
                    components.append(comp_entry)
                    
                netlist_json = json.dumps({"components": components}, ensure_ascii=False)
                
                # Run semantic reviewer
                sem_reviewer = SemanticReviewer(backend=backend)
                sem_res = sem_reviewer.review_netlist(netlist_json)
                
                if "error" in sem_res:
                    result["warnings"].append(f"AI Semantic Review Error: {sem_res['error']}")
                else:
                    for iss in sem_res.get("issues", []):
                        msg = f"AI Semantic ({iss.get('severity', 'warning')}): {iss.get('msg')}"
                        if iss.get("severity") == "critical":
                            result["critical_issues"].append(msg)
                            result["passed"] = False
                        else:
                            result["warnings"].append(msg)
                        if iss.get("proposal"):
                            result["proposals"].append(f"AI Proposal: {iss.get('proposal')}")
            except Exception as e:
                result["warnings"].append(f"AI Semantic Review failed to run: {str(e)}")
                
        return result

    def _add_issue(self, msg: str, severity: str = 'warning', ref: str = ''):
        self.issues.append({"msg": msg, "severity": severity, "ref": ref})

    def _check_out_of_bounds(self):
        """Verifica si algún componente sobresale o está muy cerca del borde."""
        margin_x = 2.0  # Margen típico (para evitar roces con la caja 3D)
        margin_y = 2.0
        bw = self.pcb.board.width_mm
        bh = self.pcb.board.height_mm
        
        for fp in self.pcb._footprints:
            if fp.x < margin_x or fp.x > (bw - margin_x) or fp.y < margin_y or fp.y > (bh - margin_y):
                self._add_issue(
                    f"Componente {fp.ref} ({fp.value}) está peligroosamente cerca del borde de la placa (x:{fp.x:.1f}, y:{fp.y:.1f}).",
                    severity="critical"
                )
                self.proposals.append(f"Mover {fp.ref} hacia el interior al menos {margin_x}mm para evitar interferencias con el encapsulado.")

    def _check_clearance(self):
        """Verifica que las pistas no pasen ilegamente cerca de pads desconectados."""
        pads_abs = []
        for fp in self.pcb._footprints:
            for p in fp.pads:
                rad = math.radians(fp.rotation)
                px = fp.x + p.x * math.cos(rad) - p.y * math.sin(rad)
                py = fp.y + p.x * math.sin(rad) + p.y * math.cos(rad)
                
                pad_layers = []
                if "thru_hole" in p.pad_type or "*.Cu" in p.layers:
                    pad_layers.extend(["F.Cu", "B.Cu"])
                elif "B.Cu" in p.layers or fp.layer == "B.Cu":
                    pad_layers.append("B.Cu")
                else:
                    pad_layers.append("F.Cu")
                    
                pads_abs.append({
                    "x": px, "y": py, 
                    "net_id": p.net_id, 
                    "parent": fp.ref, 
                    "pad": p.number,
                    "layers": pad_layers
                })
        
        min_clearance = getattr(self.pcb, 'clearance', 0.2)
        
        for trace in self.pcb._traces:
            for pad in pads_abs:
                if trace.net_id == pad["net_id"] or pad["net_id"] == 0:
                    continue  # Cortocircuito tolerado (es la misma señal)
                    
                if trace.layer not in pad["layers"]:
                    continue  # No hay colisión porque están en caras diferentes de la placa pcb
                
                dist = self._point_to_segment_dist(pad["x"], pad["y"], trace.start_x, trace.start_y, trace.end_x, trace.end_y)
                # Restar la mitad de la anchura de la pista para obtener la distancia real de cobre a punto (simplificado)
                real_dist = dist - (trace.width / 2.0)
                
                if real_dist < min_clearance:
                    self._add_issue(
                        f"Violación de Clearance: La traza pasa a {real_dist:.2f}mm de {pad['parent']}-{pad['pad']}, "
                        f"menor al mínimo permitido ({min_clearance}mm).",
                        severity="critical"
                    )

    def _point_to_segment_dist(self, px, py, x1, y1, x2, y2) -> float:
        """Matemáticas: Distancia mínima de un punto a un segmento rectilíneo."""
        l2 = (x2 - x1)**2 + (y2 - y1)**2
        if l2 == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)
        return math.hypot(px - proj_x, py - proj_y)

    def generate_report(self, run_semantic: bool = False, backend: str = "auto") -> str:
        """Formatea el resultado de la auditoría en un string Markdown amigable."""
        res = self.audit(run_semantic=run_semantic, backend=backend)
        
        lines = [
            f"# AI Design Review (DRC) — {self.pcb.project_name}",
            f"**Estado General:** {'✅ APROBADO (Listo para Manufactura)' if res['passed'] else '❌ FALLIDO (Requiere Revisiones)'}",
            ""
        ]
        
        if res['critical_issues']:
            lines.append("## 🔴 Errores Críticos (Violaciones de Reglas de Diseño)")
            for iss in res['critical_issues']:
                lines.append(f"- {iss}")
            lines.append("")
            
        if res['warnings']:
            lines.append("## 🟡 Advertencias (Potenciales problemas de ensamble)")
            for iss in res['warnings']:
                lines.append(f"- {iss}")
            lines.append("")
            
        if res['proposals']:
            lines.append("## 💡 Sugerencias de IA (Design For Manufacturing - DFM)")
            for prop in res['proposals']:
                lines.append(f"- {prop}")
            lines.append("")
            
        if res['passed'] and not res['warnings'] and not res['proposals']:
            lines.append("*¡Excelente trabajo! El diseño es mecánicamente sólido y el ruteo respeta el aislamiento mínimo.*")
            
        return "\n".join(lines)
