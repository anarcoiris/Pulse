import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath('.'))
from pulse_lab import _load_preset, _generate_pcb

print("1. Cargando EMP PFN 5kV...")
graph = _load_preset('emp_pfn')
res = _generate_pcb(graph, out_dir="output/test_emp")
pcb = res['pcb']

print("2. Revisando DRC...")
import math
pads_abs = []
for fp in pcb._footprints:
    for p in fp.pads:
        rad = math.radians(fp.rotation)
        px = fp.x + p.x * math.cos(rad) - p.y * math.sin(rad)
        py = fp.y + p.x * math.sin(rad) + p.y * math.cos(rad)
        pads_abs.append({
            "x": px, "y": py, 
            "net_id": p.net_id, 
            "parent": fp.ref, 
            "pad": p.number
        })

print(f"Total traces: {len(pcb._traces)}, Total pads: {len(pads_abs)}")

def _point_to_segment_dist(px, py, x1, y1, x2, y2) -> float:
    l2 = (x2 - x1)**2 + (y2 - y1)**2
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
    proj_x = x1 + t * (x2 - x1)
    proj_y = y1 + t * (y2 - y1)
    return math.hypot(px - proj_x, py - proj_y)

issues = []
for trace in pcb._traces:
    for pad in pads_abs:
        if trace.net_id == pad["net_id"] or pad["net_id"] == 0:
            continue
            
        dist = _point_to_segment_dist(pad["x"], pad["y"], trace.start_x, trace.start_y, trace.end_x, trace.end_y)
        real_dist = dist - (trace.width / 2.0)
        
        if real_dist < 0.2:
            issues.append(f"Trace Net:{trace.net_id} (segment {trace.start_x},{trace.start_y}->{trace.end_x},{trace.end_y}) hit Pad {pad['parent']}-{pad['pad']} (Net:{pad['net_id']}) dist={real_dist:.3f}")

if not issues:
    print("NO ISSUES FOUND")
else:
    print("ISSUES:")
    for iss in issues[:30]:
        print("  " + iss)
