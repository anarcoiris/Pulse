# Architecture Violations

This document tracks known anti-patterns and strict rules that must never be broken in the PulseLab repository.

## 1. Blocking the Main Pygame Loop
**Violation:** Running an AI inference, a `subprocess.run` to `kicad-cli`, or a complex MNA matrix inversion directly inside `_handle_event` or `_update`.
**Consequence:** The entire application window freezes. OS might flag it as "Not Responding".
**Fix:** Always wrap blocking functions in `threading.Thread(target=task, daemon=True).start()`. See `_action_forge_gen_ai` as an example.

## 2. Unsynchronized Node Modifications
**Violation:** Changing a component's `n1` or `n2` manually without triggering `runner.load()`.
**Consequence:** The visualizer will show connections that the `circuit_engine` matrix does not know about. Electrons (particles) will flow incorrectly, and KiCad exports will have floating traces.
**Fix:** Any structural change to `self.graph` MUST invoke `self._reload_graph()` immediately.

## 3. Hardcoded Component Rendering Rules in Core
**Violation:** Putting visual sizing elements (like `width=40, height=20`) inside `core/component_db.py`.
**Consequence:** Mixes presentation with business logic.
**Fix:** Visuals belong strictly to `ui/editor.py` or `bridge/pcb_layout.py`. `component_db` only knows about abstract parameters (Resistance, Package Type).

## 4. UI Direct Dependency on OpenAI
**Violation:** Requiring an active `OPENAI_API_KEY` for the application to boot.
**Consequence:** Offline electronic engineers cannot use the app.
**Fix:** The RAG and NLP features (`knowledge/`) must silently degrade or fallback to local containers (Ollama/Qwen2.5) gracefully. If no LLM is found, only the AI buttons should emit an error; the MNA and UI must keep running perfectly.

---

## Anexo: Deuda técnica y refactors pendientes

> Fusionado desde `docs/Architecture_violations.md` (Session 5 — repo hygiene, 07-jul-2026). Mientras
> las reglas de arriba son prescriptivas ("nunca hagas X"), esta sección es descriptiva: violaciones
> concretas ya presentes en el código hoy, con su refactor pendiente asociado.

### Violaciones actuales

#### 1. Tight UI-Logic Coupling
- **Problem**: `EditorCanvas` currently manages both rendering and logical state transitions (like wire finalization logic).
- **Violation**: The `CircuitGraph` should be the source of truth for all logical connections, including temporary wire states.
- **Impact**: Makes headless testing and multi-user sync difficult.

#### 2. Node Identification Flakiness
- **Problem**: The `node_at_grid` method originally relied only on component terminals. Newer wire-aware logic is a patch, not a first-class netlist engine.
- **Violation**: Lack of a persistent `Net` object. Instead, node names are "merged" string-by-string across components.
- **Impact**: Complex circuits (like the EMP PFN) can reach inconsistent states if nodes are renamed out of order.

#### 3. Footprint Mapping Heuristics
- **Problem**: `bridge/forge_api.py` uses hardcoded mapping (e.g., `etype == 'S' -> switch`).
- **Violation**: Lack of a formal Footprint Registry/Dictionary that decouples component logical type from physical representation.
- **Impact**: Adding new specialized components requires modifying the core bridge code rather than updating a config.

### Pending Refactors

- [ ] **Netlist Engine**: Transition from string-based node names to persistent `Net` objects in `CircuitGraph`.
- [ ] **Renderer Decoupling**: Extract drawing logic from `EditorCanvas` into a dedicated `EditorRenderer` class.
- [ ] **Footprint Registry**: Implement a JSON/Dict-based registry for footprint mapping and pin-out definitions.
- [ ] **Undo/Redo Stability**: Logical state is currently too fragmented for reliable history tracking.
