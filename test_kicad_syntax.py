import subprocess
from pathlib import Path

def test_pcb(path_str):
    res = subprocess.run(
        ['kicad-cli', 'pcb', 'export', 'svg', '--output', 'test_out.svg', '--layers', 'F.Cu,B.Cu,Edge.Cuts', path_str],
        capture_output=True, text=True
    )
    print('Path:', path_str)
    print('Returncode:', res.returncode)
    print('STDOUT:', res.stdout)
    print('STDERR:', res.stderr)

print("=== Testing board.kicad_pcb ===")
test_pcb('output/flipper_killer_mk_ii_0.6/board.kicad_pcb')
