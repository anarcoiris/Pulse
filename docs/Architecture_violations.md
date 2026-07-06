# Architecture Violations & Technical Debt

This document tracks segments of the codebase that deviate from the target architecture or present stability risks.

## Critical Violations

### 1. Tight UI-Logic Coupling
- **Problem**: `EditorCanvas` currently manages both rendering and logical state transitions (like wire finalization logic).
- **Violation**: The `CircuitGraph` should be the source of truth for all logical connections, including temporary wire states.
- **Impact**: Makes headless testing and multi-user sync difficult.

### 2. Node Identification Flakiness
- **Problem**: The `node_at_grid` method originally relied only on component terminals. Newer wire-aware logic is a patch, not a first-class netlist engine.
- **Violation**: Lack of a persistent `Net` object. Instead, node names are "merged" string-by-string across components.
- **Impact**: Complex circuits (like the EMP PFN) can reach inconsistent states if nodes are renamed out of order.

### 3. Footprint Mapping Heuristics
- **Problem**: `bridge/forge_api.py` uses hardcoded mapping (e.g., `etype == 'S' -> switch`).
- **Violation**: Lack of a formal Footprint Registry/Dictionary that decouples component logical type from physical representation.
- **Impact**: Adding new specialized components requires modifying the core bridge code rather than updating a config.

## Pending Refactors

- [ ] **Netlist Engine**: Transition from string-based node names to persistent `Net` objects in `CircuitGraph`.
- [ ] **Renderer Decoupling**: Extract drawing logic from `EditorCanvas` into a dedicated `EditorRenderer` class.
- [ ] **Footprint Registry**: Implement a JSON/Dict-based registry for footprint mapping and pin-out definitions.
- [ ] **Undo/Redo Stability**: Logical state is currently too fragmented for reliable history tracking.
