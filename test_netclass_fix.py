import subprocess
from pathlib import Path

def test_netclass_inner(subtags):
    pcb = f"""(kicad_pcb (version 20240108) (generator "PulseLab Forge")
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))
  (setup (pad_to_mask_clearance 0.05))
  (net_class "Default" "Default netclass"
{subtags}
  )
  (net 0 "")
  (gr_line (start 0 0) (end 50 0) (layer "Edge.Cuts") (stroke (width 0.1)))
  (gr_line (start 50 0) (end 50 50) (layer "Edge.Cuts") (stroke (width 0.1)))
  (gr_line (start 50 50) (end 0 50) (layer "Edge.Cuts") (stroke (width 0.1)))
  (gr_line (start 0 50) (end 0 0) (layer "Edge.Cuts") (stroke (width 0.1)))
)"""
    Path("test_nc.kicad_pcb").write_text(pcb, encoding="utf-8")
    res = subprocess.run(
        ['kicad-cli', 'pcb', 'export', 'svg', '--output', 'test_out.svg', '--layers', 'F.Cu,B.Cu,Edge.Cuts', 'test_nc.kicad_pcb'],
        capture_output=True, text=True
    )
    print(f"Subtags:\n{subtags}\n--> Returncode: {res.returncode}")
    if res.returncode != 0:
        print("  STDERR:", res.stderr.strip())

test_netclass_inner("""    (clearance 0.15)
    (trace_width 0.25)
    (via_dia 0.6)
    (via_drill 0.3)
    (uvia_dia 0.3)
    (uvia_drill 0.1)""")
