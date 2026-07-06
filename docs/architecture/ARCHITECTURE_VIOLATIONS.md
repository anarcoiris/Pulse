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
