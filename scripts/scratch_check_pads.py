import sys, math
from pathlib import Path

pcb_file = Path(r'C:\Users\soyko\Documents\Pulse-main\output\flipper_killer_mk_ii_0.6\board.kicad_pcb')
content = pcb_file.read_text(encoding='utf-8')

# Find the block for Header_000
start = content.find('(reference "Header_000"')
if start != -1:
    block = content[start:start+2000]
    lines = block.split('\n')
    for line in lines:
        if '(at ' in line and 'footprint' not in line:
            print(line.strip())
