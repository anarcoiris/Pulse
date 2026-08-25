script = """
import re

with open("core/visual_inference.py", "r", encoding="utf-8") as f:
    text = f.read()

# Let's add the new passes and radar calculation to inspect()
inspect_body = '''        # ── Pass 5: RF Antenna Keepout & Exterior Flushness (VIS-006) ────────
        rf_comps = [cb for cb in courtyards if cb.package_type in ("RF", "MCU") and any(k in cb.ref.upper() or k in getattr(cb, "package_type", "") for k in ("RF", "ANT", "CC1101", "NRF", "ESP32"))]
        for rf in rf_comps:
            # Check if antenna region is oriented toward board edge
            dist_to_edge = min(
                abs(rf.x - (ox + self.edge_margin_mm)),
                abs(rf.x - (ox + bw - self.edge_margin_mm)),
                abs(rf.y - (oy + self.edge_margin_mm)),
                abs(rf.y - (oy + bh - self.edge_margin_mm))
            )
            # If RF module is buried in board center, give informational suggestion
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
            ys = sorted([b.y for b in ui_buttons])
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
        )'''

pattern = r"        # ── Calculate Inspection Score ───────────────────────────────────────[\s\S]*?return VisualInspectionReport\([\s\S]*?\n        \)"
match = re.search(pattern, text)
if match:
    text = text[:match.start()] + inspect_body + text[match.end():]
    with open("core/visual_inference.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Successfully enhanced inspect() method with 9-pass DFM radar!")
else:
    print("Warning: regex pattern not matched in visual_inference.py")
"""

with open("scripts/patch_vis_engine.py", "w", encoding="utf-8") as f:
    f.write(script)

