import subprocess
from pathlib import Path

def test_pcb(layers_block):
    pcb = f"""(kicad_pcb (version 20240108) (generator "PulseLab Forge")
  (general (thickness 1.6))
  (paper "A4")
  {layers_block}
  (setup)
  (net 0 "")
  (gr_line (start 0 0) (end 50 0) (layer "Edge.Cuts") (stroke (width 0.1)))
  (gr_line (start 50 0) (end 50 50) (layer "Edge.Cuts") (stroke (width 0.1)))
  (gr_line (start 50 50) (end 0 50) (layer "Edge.Cuts") (stroke (width 0.1)))
  (gr_line (start 0 50) (end 0 0) (layer "Edge.Cuts") (stroke (width 0.1)))
)"""
    Path("test_layers.kicad_pcb").write_text(pcb, encoding="utf-8")
    res = subprocess.run(
        ['kicad-cli', 'pcb', 'export', 'svg', '--output', 'test_out.svg', '--layers', 'F.Cu,B.Cu,Edge.Cuts', 'test_layers.kicad_pcb'],
        capture_output=True, text=True
    )
    print("Returncode:", res.returncode)
    if res.returncode != 0:
        print("STDERR:", res.stderr.strip())

layers_generated = """(layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user "B.Fab")
    (49 "F.Fab" user "F.Fab")
  )"""

test_pcb(layers_generated)
