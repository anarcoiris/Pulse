# Pulse — PulseLab Forge

<p align="center">
  <img src="pulselab.png" alt="PulseLab Forge Banner" width="800">
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![KiCad](https://img.shields.io/badge/KiCad-8%2B%20%7C%2010.0-1BA94C.svg)](https://www.kicad.org/)
[![Tests](https://img.shields.io/badge/Tests-152%20passing-brightgreen.svg)](https://github.com/anarcoiris/Pulse)
[![MCP Tools](https://img.shields.io/badge/MCP-31%20tools-orange.svg)](https://github.com/anarcoiris/Pulse/tree/main/mcp_server)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

</div>

```c
/**
 *    .,::::::   :::    .,::::::   .,-::::::::::::::::::::::::..       ...   :::.    :::.:::  .,-::::: .::::::. 
 *    ;;;;''''   ;;;    ;;;;'''' ,;;;'````';;;;;;;;'''';;;;``;;;;   .;;;;;;;.`;;;;,  `;;;;;;,;;;'````';;;`    ` 
 *     [[cccc    [[[     [[cccc  [[[            [[      [[[,/[[['  ,[[     \[[,[[[[[. '[[[[[[[[       '[==/[[[[,
 *     $$""""    $$'     $$""""  $$$            $$      $$$$$$c    $$$,     $$$$$$ "Y$c$$$$$$$$         '''    $
 *     888oo,__ o88oo,.__888oo,__`88bo,__,o,    88,     888b "88bo,"888,_ _,88P888    Y88888`88bo,__,o,88b    dP
 *     """"YUMMM""""YUMMM""""YUMMM "YUMMMMMP"   MMM     MMMM   "W"   "YMMMMMP" MMM     YMMMM  "YUMMMMMP""YMmMY" 
 *                      .,-::::: :::::::..    :::.    .-:::::'::::::::::::::                                    
 *                    ,;;;'````' ;;;;``;;;;   ;;`;;   ;;;'''' ;;;;;;;;'''','                                    
 *                    [[[         [[[,/[[['  ,[[ '[[, [[[,,==      [[                                           
 *                    $$$         $$$$$$c   c$$$cc$$$c`$$$"``      $$                                           
 *                    `88bo,__,o, 888b "88bo,888   888,888         88,                                          
 *                      "YUMMMMMP"MMMM   "W" YMM   ""` "MM,        MMM                                          
 */
```

**⚡ Unified Circuit Editor & MNA Simulator with Algorithmic PCB Layout & Autonomous MCP Hardware Synthesis**

---

> 🚧 **Active Development.** Architecture and generative pipelines evolve continuously — check [`docs/status/FORGE_STATUS.md`](docs/status/FORGE_STATUS.md) for live metrics and [`docs/status/CURRENT_SPRINT.md`](docs/status/CURRENT_SPRINT.md) for current active sprint tasks.

---

## 🎯 What is Pulse?

**PulseLab Forge** is a unified Modified Nodal Analysis (MNA) circuit editor, generative PCB synthesis engine, and hardware manufacturing pipeline. It bridges conceptual schematics to production-ready manufacturing deliverables (Gerbers, Drill files, CPL, BOM, and KiCad 8+/10 S-expressions) without leaving a single programmatic workflow.

Unlike standard CAD packages, Pulse incorporates:
1. **Procedural PCB Layout Engine**: Force-directed attraction/repulsion, thermal via matrix generator, ground plane manager with inter-layer via stitching, and Specctra DSN/FreeRouting auto-routing bridge.
2. **Multi-Provider Supply Chain Engine**: Live component fetching from **JLCPCB (LCSC)** and **PCBWay** catalogs with local 24h disk caching and interactive component candidate decision matching.
3. **Local MCP Server (31 Tools)**: Exposes structural circuit design, schematic cross-checks, DRC verification, thermal calculation, and CAM exports directly to LLM agents (Claude Desktop, Ollama, etc.).

---

## 🛠️ Main Features & Modules

| Module | Location | Description |
|---|---|---|
| 🖥️ **MNA Simulator & UI** | `pulse_lab.py` | PyGame visual editor with anti-aliased rendering, real-time MNA solver, live oscilloscope, and interactive passive/active components. |
| 📐 **Algorithmic PCB Builder** | `bridge/pcb_builder.py` | Generates KiCad 8+/10 S-expressions, coordinates auto-placement heuristics, thermal pads, and DRC gates. |
| 📍 **2D Auto-Placement Engine** | `core/auto_placement.py` | Physics-based placement relaxation using Hooke attraction, Coulomb pin repulsion, and domain orientation rules. |
| ⚡ **Thermal Management Engine** | `core/thermal_engine.py` | Automated $3 \times 3$ thermal via grids under high-power pads (e.g. ESP32 EPAD 41, AMS1117 tab) with solid zone connections. |
| 🛡️ **Ground Zone & Via Stitching** | `core/copper_zone_manager.py` | Automated double-sided `PWR_GND` ground pours, $0.50\,\text{mm}$ thermal peninsulas, and matrix inter-layer ground via stitching. |
| 📦 **Multi-Provider Fetcher Engine** | `core/providers/` | Live side-by-side component search across **JLCPCB (LCSC)** and **PCBWay** with Basic/Extended library detection and local caching. |
| 🎨 **Graphics & Stencil Engine** | `bridge/graphics_engine.py` | Converts DXF/SVG vector artwork into silk/copper KiCad polygon primitives (`gr_poly`). |
| 🛣️ **FreeRouting Auto-Router Bridge** | `bridge/freerouting_bridge.py` | DSN export (`kicad-cli pcb export dsn`), headless FreeRouting CLI runner, and SES back-annotation import. |
| 📑 **100% SCH $\leftrightarrow$ PCB Parity** | `core/sch_pcb_crosscheck.py` | Automatic net and symbol cross-check gate embedded into DRC validation. |
| 🧠 **MCP Server (31 Tools)** | `mcp_server/` | FastMCP service exposing complete hardware synthesis capabilities to external LLM client apps. |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **KiCad 8+ or KiCad 10+** (in `PATH` for Gerber/Drill generation and SVG export via `kicad-cli`)
- *(Optional)* **Ollama** running locally on `:11434` or `:11431` for Forge Studio LLM agent features.

### Installation

```bash
git clone https://github.com/anarcoiris/Pulse.git
cd Pulse
pip install -r requirements.txt
```

### Launch the Visual Circuit Editor & Simulator

```bash
python pulse_lab.py
```

### Run Full Test Suite (152 Unit Tests)

```bash
python -m pytest tests/
```

---

## 📁 Repository Structure

```
Pulse/
├── core/                 ← Physics simulation, placement algorithms, supply chain & audit gates
│   ├── auto_placement.py ← 2D spatial layout physics engine
│   ├── circuit_engine.py ← Modified Nodal Analysis (MNA) solver
│   ├── component_db.py   ← Systematized component database & decision assistant
│   ├── copper_zone_manager.py ← Ground plane pour & via stitching manager
│   ├── kicad_audit.py    ← 14-rule topological pre-routing audit gate
│   ├── provider_fetcher.py ← JLCPCB / PCBWay multi-provider fetcher & cache
│   ├── providers/        ← Supplier API fetchers (JLCPCB, PCBWay)
│   ├── sch_pcb_crosscheck.py ← Schematic <-> PCB net & symbol validator
│   └── thermal_engine.py ← Thermal via grid & pad zone connection manager
├── bridge/               ← KiCad compilation, S-expressions, graphics & auto-routing
│   ├── freerouting_bridge.py ← Specctra DSN export & SES import wrapper
│   ├── gerber_export.py  ← Fabrication CAM export orchestrator (kicad-cli)
│   ├── graphics_engine.py← Polygon vector logo artwork renderer
│   ├── kicad_bridge.py   ← Cross-platform KiCad CLI wrapper & DRC gate
│   ├── pcb_builder.py    ← S-expression PCB generator & auto-placement fallback
│   ├── pcb_layout.py     ← S-expression primitives & zone connection overrides
│   └── schematic_generator.py ← Automatic .kicad_sch builder with mounting holes
├── knowledge/            ← RAG knowledge base, prompt templates & agent engines
│   ├── circuit_agent.py  ← Multi-turn hardware agent loop
│   ├── circuit_synthesizer.py ← High-level NLP circuit synthesis
│   └── rag_engine.py     ← Hybrid RAG over IPC-2221 standards & KiCad libraries
├── studio/               ← Forge Studio headless LLM REPL (`python -m studio`)
├── mcp_server/           ← Local MCP server (31 exposed tools)
├── ui/                   ← PyGame presentation layer & oscilloscope UI
├── webapp/               ← Next.js / Vite web frontend canvas
├── docs/                 ← Project documentation, status metrics & roadmap
├── presets/              ← Circuit templates (ESP32 DevKit, EMP PFN, MCU UART)
├── scripts/              ← Automation scripts & reference generation loops
└── tests/                ← Pytest regression suite (152 tests)
```

---

## 🎬 Modos de Uso / Execution Modes

### 1. Main PyGame UI Simulator

```bash
python pulse_lab.py
```

### 2. Forge Studio (Headless LLM Debug REPL)

```powershell
python -m studio
```

Session log transcripts are stored under `knowledge/data/llm_sessions/sessions/{session_id}/`.

### 3. MCP Server (Claude Desktop / Agent Integration)

```bash
python -m mcp_server.server
```

---

## 📚 Documentation Map

| Document | Purpose |
|---|---|
| [`docs/README.md`](docs/README.md) | Complete documentation index and doc roles |
| [`docs/status/CURRENT_SPRINT.md`](docs/status/CURRENT_SPRINT.md) | Active sprint execution order & next actions |
| [`docs/status/FORGE_STATUS.md`](docs/status/FORGE_STATUS.md) | Verified system metrics (tests, RAG, MCP tools) |
| [`docs/roadmap.md`](docs/roadmap.md) | Product phases & feature roadmap |
| [`docs/architecture/APP_ARCHITECTURE.md`](docs/architecture/APP_ARCHITECTURE.md) | System architecture & layer isolation rules |

---

## 📄 License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.
