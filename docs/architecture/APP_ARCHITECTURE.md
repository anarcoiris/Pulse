# PulseLab App Architecture

PulseLab is built as a highly modular, real-time Desktop Application written in Python, orchestrating UI rendering, electronic simulation, and hardware compilation. 

## Architectural Philosophy

Unlike standard web/mobile applications, PulseLab operates in a strict, continuous game loop (`pygame`) paired with a discrete physics simulation loop (MNA). To maintain 60 FPS while solving differential equations and running LLM agents, we adhere to the following principles:

1. **Non-Blocking UI (Threaded Operations)**
   Any heavy task—such as PCB synthesis, Gerber extraction via KiCad CLI, or LLM Generative AI generation—MUST run in a secondary `threading.Thread`. The Main UI loop must never drop below 60 FPS.
   
2. **Decoupled Simulation Engine**
   The UI (`CircuitGraph`, `EditorCanvas`) only holds the physical and visual bounds of the components. The `circuit_engine.py` (MNA Solver) builds its own mathematical matrices. State synchronization happens via explicit node assignments.

3. **Knowledge Injection & RAG**
   AI subsystems (`semantic_reviewer`, `circuit_synthesizer`) are considered "Knowledge Extensions" and operate statelessly via local models (Ollama/Qwen).

## System Layers

### 1. Presentation Layer (`ui/`)
- `pulse_lab.py`: The single entry point and main loop coordinator.
- `editor.py`: Canvas interactions, wire routing, and grid snapping.
- `toolbar.py` & `properties.py`: UI panels.
- `theme.py`: Global constants, fonts, and the "Cyber Night" design system values.

### 2. Core Physics (`core/` & Root)
- `circuit_engine.py`: Modifed Nodal Analysis (MNA) solver handling inductors, capacitors, voltage sources, and non-linear diodes.
- `component_db.py`: Local database mapping footprints, IDs, and IPC-2221 constraints.

### 3. Synthesis Bridge (`bridge/`)
- `forge_api.py` / `pcb_layout.py`: Maps the Nodal Graph to S-expressions (`.kicad_pcb` format).
- `gerber_export.py`: Handles CAM exports and DRC rules via `kicad-cli`.
- `kicad_bridge.py`: Platform-agnostic sub-process wrapper for KiCad tooling.

### 4. Knowledge / AI (`knowledge/`)
- `semantic_reviewer.py`: AI-based DRC checks for logical flaws (e.g., missing decouple caps).
- `circuit_synthesizer.py`: NLP to Netlist generator.
- `firmware_synthesizer.py`: Automatic MicroPython boilerplate generation.

## Dependencies & Communication
- **UI → Engine:** UI triggers `runner.load(graph)`, which freezes the graph to extract mathematical matrices.
- **UI → Bridge:** UI sends `CircuitGraph` to `forge_api.generate_pcb(graph)`.
- **Knowledge → UI:** AI threads update `_ai_popup` or `_ai_gen_popup` state dictionaries dynamically, which the main loop renders safely.
