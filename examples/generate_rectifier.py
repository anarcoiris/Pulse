import sys
sys.path.insert(0, '..')
from core.circuit_graph import CircuitGraph
import json

g = CircuitGraph()

# Signature: add(etype, grid_c, grid_r, orientation, value, label, n1="", n2="")
g.add('V', 0, 0, 'H', 12.0, 'VAC', 'AC_L', 'AC_N')

# Diodes
g.add('D', 2, 0, 'H', 0, 'D1', 'AC_L', 'DC_POS')
g.add('D', 2, 2, 'H', 0, 'D2', 'AC_N', 'DC_POS')
g.add('D', 4, 0, 'H', 0, 'D3', 'DC_NEG', 'AC_L')
g.add('D', 4, 2, 'H', 0, 'D4', 'DC_NEG', 'AC_N')

# Inductor
g.add('L', 6, 1, 'H', 0.01, 'L1 10mH', 'DC_POS', 'L_OUT')

# Load and GND
g.add('R', 8, 1, 'V', 100, 'Rload 100R', 'L_OUT', 'DC_NEG')
g.add('R', 8, 3, 'V', 0.001, 'GND_Link', 'DC_NEG', 'GND')

with open('../output/rectificador_inductor.json', 'w') as f:
    json.dump(g.to_json(), f, indent=2)

print("Circuit generated at output/rectificador_inductor.json")
