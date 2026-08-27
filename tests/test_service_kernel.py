import sys
import tempfile
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.service_kernel import PulseLabEngine

def test_service_kernel_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = PulseLabEngine(output_base_dir=Path(tmpdir))
        
        sample_circuit = {
            "name": "Test Kernel RC Circuit",
            "board_width": 50.0,
            "board_height": 30.0,
            "circuit": [
                {
                    "etype": "R",
                    "value": "10k",
                    "label": "R1",
                    "n1": "PWR_3V3",
                    "n2": "NET_OUT",
                    "footprint": "Resistor_SMD:R_0603_1608Metric"
                },
                {
                    "etype": "C",
                    "value": "100nF",
                    "label": "C1",
                    "n1": "NET_OUT",
                    "n2": "PWR_GND",
                    "footprint": "Capacitor_SMD:C_0603_1608Metric"
                }
            ]
        }
        
        bundle = engine.create_project("test_rc_01", sample_circuit)
        
        assert bundle.success is True
        assert bundle.sch_file.exists()
        assert bundle.pcb_file.exists()
        assert bundle.jlcpcb_bom.exists()
        assert bundle.jlcpcb_cpl.exists()
        assert bundle.gerber_dir.exists()
        print("Service kernel lifecycle test passed successfully!")

if __name__ == "__main__":
    test_service_kernel_lifecycle()
