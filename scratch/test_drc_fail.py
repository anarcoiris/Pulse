import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path('.').absolute()))

from bridge.pcb_layout import PCBLayout
from bridge.kicad_bridge import KiCadBridge
from ui.editor import CircuitGraph

def test_drc_short_circuit():
    print("Generating a board with an intentional short circuit...")
    
    # We will create a graph with two connected components, but we will place them
    # directly on top of each other, causing a courtyard and clearance violation.
    graph = CircuitGraph()
    graph.add('R', 10, 10, 'H', 10000, 'R1', 'VCC', 'GND')
    graph.add('C', 10, 10, 'H', 100e-9, 'C1', 'VCC', 'GND')
    
    # Layout engine
    pcb = PCBLayout(board_width=20, board_height=20)
    
    # Place them EXACTLY on the same spot to force a DRC failure
    r1 = pcb.add_resistor("R1", "10k", x=10, y=10, net1="VCC", net2="GND")
    c1 = pcb.add_capacitor("C1", "100nF", x=10, y=10, net1="VCC", net2="GND")
    
    # Save PCB
    out_dir = Path("output/drc_test")
    out_dir.mkdir(parents=True, exist_ok=True)
    pcb_path = out_dir / "design.kicad_pcb"
    pcb.save(pcb_path)
    
    print(f"PCB generated at: {pcb_path}")
    
    # Run the export pipeline
    bridge = KiCadBridge()
    print("Running export_all (which should trigger DRC)...")
    result = bridge.export_all(graph, output_dir=str(out_dir), project_name="design")
    
    if "error" in result:
        print(f"SUCCESS: DRC caught the violation! Error message: {result['error']}")
        # Let's inspect the report
        if "drc_report" in result:
            violations = result["drc_report"].get("violations", [])
            print(f"Number of violations found: {len(violations)}")
            if violations:
                print(f"First violation: {violations[0].get('description', 'No description')}")
    else:
        print("FAILURE: DRC did not catch the short circuit/overlap! Export succeeded incorrectly.")

if __name__ == "__main__":
    test_drc_short_circuit()
