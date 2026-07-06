# Coding Guidelines

## Python Standards
PulseLab uses Python 3.10+.
All code MUST conform to PEP-8 standards.

### 1. Typing
Use strict type hints for function signatures to allow the IDE and AI assistants to catch UI/Engine mismatches early.
```python
from typing import List, Optional, Dict

def update_node_voltage(self, node_id: str, voltage: float) -> None:
    pass
```

### 2. State Mutability
In Pygame, State == UI Reality. 
- Do not mutate the `CircuitGraph` while the `SimulationRunner` is stepping through the MNA solver, as this will cause mathematical mismatch errors.
- Always pause the simulation (`runner.pause()`) before modifying the grid.

### 3. Pygame Rendering Optimization
- Do not compute bounding boxes, string concatenations, or math inside the `_draw()` loops if it can be avoided. Pre-calculate text surfaces or layout Rects in the `_update()` or `_layout()` phases.
- See `ui/toolbar.py` `_layout()` method for an example of calculating layouts before drawing.

### 4. Hardware Integrations (Bridge)
When invoking `kicad-cli`:
- Never assume the path separator. Use `os.path.join` or `pathlib.Path`.
- Never trust that `kicad-cli` is in the PATH. Always verify using `bridge.kicad_bridge.status()` before attempting execution.
- Handle IOExceptions safely; do not crash the main UI thread.

### 5. Comments and Documentation
- Every module should begin with a docstring explaining its purpose in the Pulse ecosystem.
- Inline comments should explain *why* a specific engineering choice was made, not *what* it does. (e.g. `// Added 0.001R to avoid singular matrices in SPICE solver`).
