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

### 1. Presentation Layer
- **`ui/`** — pygame editor (`pulse_lab.py`, canvas, toolbar, modals).
- **`studio/`** — Forge Studio headless REPL (`python -m studio`); streams LLM thinking/content for Calibration Forge debug. Must not import `ui/` or pygame.

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
- `llm_client.py` / `ollama_native.py`: Unified LLM transport; `chat_stream()` for Forge Studio.

## Dependencies & Communication
- **UI → Engine:** UI triggers `runner.load(graph)`, which freezes the graph to extract mathematical matrices.
- **UI → Bridge:** UI sends `CircuitGraph` to `forge_api.generate_pcb(graph)`.
- **Knowledge → UI:** AI threads update modal state; the main loop renders safely (non-blocking).
- **Studio → Knowledge:** `ForgeSession` delegates to synthesizer/reviewer with shared `session_id`; logs under `knowledge/data/llm_sessions/`.

---

## Anexo: Módulos técnicos y flujo de datos

> Fusionado desde `docs/Architecture.md` (Session 5 — repo hygiene, 07-jul-2026). Complementa las
> capas de arriba con el detalle de módulo-por-módulo y el flujo de datos end-to-end.

### Core Pillars

#### 1. Simulation Engine (`circuit_engine.py`)
- **Mathematical Model**: Modified Nodal Analysis (MNA).
- **Integration Scheme**: Backward Euler for robust stability in stiff circuits (like high-voltage pulse forming networks).
- **Solver**: Dense matrix solver using NumPy. Supports regularization to handle floating nodes (within constraints).
- **Real-time**: Designed for frame-by-frame execution synchronized with the UI.

#### 2. Interactive Editor (`ui/editor.py`)
- **Backend**: PyGame-based 2D canvas.
- **Circuit Representation**: `CircuitGraph` maintains the visual and logical netlist.
- **Features**: Real-time voltage display, animated current particles, zoom/pan navigation, and net-aware wire merging.

#### 3. PCB Bridge Logic (`bridge/forge_api.py`)
- **Synthesis**: Translates logical components from the `CircuitGraph` into physical PCB instances.
- **Constraints**: Applies basic spatial constraints and net associations.
- **Manual Overrides**: Supports custom footprint selection for professional components like switches and ICs.
- **Validation**: Integrates with the RAG engine to verify footprints against manufacturer recommendations.

#### 4. PCB Layout Engine (`bridge/pcb_layout.py`)
- **File Format**: Generates KiCad 8.0 S-expression files (`.kicad_pcb`) directly from Python.
- **Capabilities**:
  - Footprint instantiation for SMD and THT components.
  - **Autorouting**: Initial A* implementation for multi-layer trace escape and rounting.
  - **Copper Pours**: Automated ground planes with thermal relief support.
  - **Edge Cuts**: Programmatic generation of PCB outline with corner rounding.
  - **Verification**: Direct bridge to `kicad-cli` for 11-layer Gerber generation and Drill files.

### Data Flow
1. **User Design**: Component placement and wiring in the Editor.
2. **Simulation**: `CircuitGraph` -> `CircuitSimulator` translation. Real-time feedback in HUD.
3. **Synthesis**: `CircuitGraph` -> `PCBLayout` via `forge_api`.
4. **Manufacturing**: `PCBLayout` -> `.kicad_pcb` -> `Gerber Files`.
