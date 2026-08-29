# PulseLab Architecture & Engineering Blueprint

PulseLab Forge is built as a highly modular, multi-target EDA and circuit synthesis platform, combining native desktop physics simulation, a unified FastAPI/FastMCP service kernel, and a modern Web Studio client.

---

## Architectural Philosophy

Unlike standard CAD packages, PulseLab operates across a dual execution model:
1. **Desktop Physics Loop (PyGame)**: Real-time interactive MNA (Modified Nodal Analysis) solver running at 60 FPS for fast component tuning, differential equations, and oscilloscope analysis without browser overhead.
2. **Unified Cloud/Web Studio (FastAPI + React + Three.js)**: Multi-viewport 2D/3D WebGL CAD interface, LLM generative synthesis co-pilot, automated supply-chain matching (JLCPCB/PCBWay), and DRC validation gates.

---

## System Layers

### 1. Presentation Layer
- **Desktop Simulator (`ui/` & `pulse_lab.py`)**: PyGame visual editor, interactive HUD, and real-time oscilloscope.
- **Web Studio (`webapp/`)**: React 19 + TypeScript + Vite + Tailwind CSS + Lucide Icons + Three.js / Canvas 2D.
- **Forge Studio REPL (`studio/`)**: Headless terminal REPL (`python -m studio`) for direct LLM synthesis and debugging.

### 2. Backend & Service Layer (`core/service_kernel.py` & `app/`)
- **`core/service_kernel.py`**: Singleton-capable `PulseLabEngine` orchestrating the complete lifecycle: synthesis → placement → routing → copper zones → DRC audit → manufacturing bundle export.
- **`app/main.py`**: FastAPI REST API and WebSocket gateway serving the Web Studio and external automated integrations.
- **`mcp_server/server.py`**: Local FastMCP server exposing 36 specialized EDA tools to external LLM clients (Claude Desktop, Ollama, etc.).

### 3. Compilation, CAD & Layout Bridges (`bridge/`)
- **`bridge/pcb_builder.py`**: Procedural KiCad 8+/10 S-expression PCB generator.
- **`bridge/schematic_generator.py`**: Automatic `.kicad_sch` builder with verified net labels and mounting holes.
- **`bridge/freerouting_bridge.py`**: Specctra DSN export, headless FreeRouting CLI auto-router, and SES back-annotation.
- **`bridge/graphics_engine.py`**: Vector artwork and logo polygon primitive renderer (`gr_poly`).
- **`bridge/kicad_bridge.py`**: Cross-platform CLI wrapper for `kicad-cli` (Gerber, Drill, SVG, DRC).
- **`bridge/pcb_layout.py`**: S-expression layout primitives and clearance overrides.

### 4. Physics Simulation & Quality Gates (`core/`)
- **`core/circuit_engine.py`**: Modified Nodal Analysis (MNA) solver handling non-linear devices, AC/DC sources, and RLC networks with Backward Euler integration.
- **`core/auto_placement.py`**: Physics-based force-directed auto-placement engine (Hooke attraction, Coulomb pin repulsion, courtyard envelopes, and mounting hole keep-outs).
- **`core/copper_zone_manager.py`**: Automated double-sided ground pour zones, thermal spokes, and inter-layer via stitching matrices.
- **`core/thermal_engine.py`**: Automated thermal via grid generators ($3 \times 3$) under high-power IC exposed pads (EPAD).
- **`core/sch_pcb_crosscheck.py`**: Net and symbol parity validator ensuring 100% agreement between schematic and PCB.
- **`core/kicad_audit.py`**: 14 topological pre-routing design rule audit gates (R001-R014).
- **`core/component_db.py` & `core/providers/`**: Live multi-supplier catalog search (JLCPCB, PCBWay) with local 24h caching.

### 5. Knowledge, Skills & AI Subsystems (`knowledge/` & `skills/`)
- **`knowledge/rag_engine.py`**: Dense embedding + TF-IDF hybrid RAG over IPC-2221 standards, pinout databases, and component catalogs.
- **`knowledge/llm_client.py` & `knowledge/llm_backends.py`**: Modular multi-provider LLM client supporting local Ollama, Qwythos, and cloud models.
- **`app/circuit_synthesizer.py`**: Natural language to verified hardware circuit netlist generator.
- **`skills/`**: Domain-separated EE rules (power-on-reset, decoupling, I2C pullups, boot strapping).
