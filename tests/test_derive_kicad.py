import json
import sys
from pathlib import Path

# Agregar raíz al path (tests/ -> Pulse-main/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.circuit_graph import CircuitGraph
from bridge.pcb_builder import PCBBuilder
from bridge.schematic_generator import SchematicGenerator

def test_derive_kicad():
    json_path = "knowledge/data/flipper_multiboard_pcb.json"
    
    # Resolviendo ruta absoluta para evitar problemas con CWD
    root_dir = Path(__file__).resolve().parent.parent
    full_json_path = root_dir / json_path

    with open(full_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    circuit = data.get("circuit", [])
    print(f"Loaded circuit with {len(circuit)} elements.")

    # 1. Convert to CircuitGraph
    graph = CircuitGraph.from_component_dicts(circuit)
    print("Successfully built CircuitGraph.")

    # 2. Build PCB & Schematic using PCBBuilder
    net_classes = data.get("net_classes", {})
    builder = PCBBuilder.from_circuit_graph(
        graph,
        out_dir=str(root_dir / "output"),
        project_name="Flipper_Multiboard",
        net_classes=net_classes
    )
    result = builder.save(sub_dir="flipper_multiboard")
    
    print("\n--- Generation Result ---")
    print(f"Success: {result.get('success')}")
    print(f"PCB Path: {result.get('path')}")
    print(f"SCH Path: {result.get('sch_path')}")
    print("PCB Stats:", result.get("stats"))
    
    assert result.get("success") is True

if __name__ == "__main__":
    test_derive_kicad()
