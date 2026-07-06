# PulseLab Forge Architecture

## Overview
PulseLab Forge is an integrated EDA (Electronic Design Automation) platform designed for iterative hardware prototyping. It moves beyond traditional static schematic capture by providing a real-time, interactive simulation environment coupled with a direct bridge to professional PCB manufacturing.

## Core Pillars

### 1. Simulation Engine (`circuit_engine.py`)
- **Mathematical Model**: Modified Nodal Analysis (MNA).
- **Integration Scheme**: Backward Euler for robust stability in stiff circuits (like high-voltage pulse forming networks).
- **Solver**: Dense matrix solver using NumPy. Supports regularization to handle floating nodes (within constraints).
- **Real-time**: Designed for frame-by-frame execution synchronized with the UI.

### 2. Interactive Editor (`ui/editor.py`)
- **Backend**: PyGame-based 2D canvas.
- **Circuit Representation**: `CircuitGraph` maintains the visual and logical netlist.
- **Features**: Real-time voltage display, animated current particles, zoom/pan navigation, and net-aware wire merging.

### 3. PCB Bridge Logic (`bridge/forge_api.py`)
- **Synthesis**: Translates logical components from the `CircuitGraph` into physical PCB instances.
- **Constraints**: Applies basic spatial constraints and net associations.
- **Manual Overrides**: Supports custom footprint selection for professional components like switches and ICs.
- **Validation**: Integrates with the RAG engine to verify footprints against manufacturer recommendations.

### 4. PCB Layout Engine (`bridge/pcb_layout.py`)
- **File Format**: Generates KiCad 8.0 S-expression files (`.kicad_pcb`) directly from Python.
- **Capabilities**:
  - Footprint instantiation for SMD and THT components.
  - **Autorouting**: Initial A* implementation for multi-layer trace escape and rounting.
  - **Copper Pours**: Automated ground planes with thermal relief support.
  - **Edge Cuts**: Programmatic generation of PCB outline with corner rounding.
  - **Verification**: Direct bridge to `kicad-cli` for 11-layer Gerber generation and Drill files.

## Data Flow
1. **User Design**: Component placement and wiring in the Editor.
2. **Simulation**: `CircuitGraph` -> `CircuitSimulator` translation. Real-time feedback in HUD.
3. **Synthesis**: `CircuitGraph` -> `PCBLayout` via `forge_api`.
4. **Manufacturing**: `PCBLayout` -> `.kicad_pcb` -> `Gerber Files`.
