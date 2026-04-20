
import sys
import os
sys.path.append(os.getcwd())

from ui.editor import CircuitGraph
from bridge.schematic_generator import SchematicGenerator

# Create a dummy graph
g = CircuitGraph()
g.add("R", 10, 10, "H", 1000, "R_pullup")
g.add("GND", 10, 15, "V", 0, "GND")
g.add_wire([(10, 10), (10, 15)])

# Generate schematic
gen = SchematicGenerator(g)
sch_content = gen.generate()

print("--- KICAD_SCH CONTENT ---")
print(sch_content[:500])
print("...")
print("--- END ---")

gen.save("scratch/test_schematic.kicad_sch")
print(f"Schematic saved to scratch/test_schematic.kicad_sch")
