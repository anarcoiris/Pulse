# Pulse — PulseLab Forge

<p align="center">
  <img src="pulselab.png" alt="PulseLab Forge Banner" width="800">
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![KiCad](https://img.shields.io/badge/KiCad-8%2B-1BA94C)](https://www.kicad.org/)
[![MCP Tools](https://img.shields.io/badge/MCP-31%20tools-orange)](https://github.com/anarcoiris/Pulse/tree/main/mcp_server)
[![GitHub stars](https://img.shields.io/github/stars/anarcoiris/Pulse?style=flat-square)](https://github.com/anarcoiris/Pulse/stargazers)
[![License](https://img.shields.io/badge/License-not%20specified-lightgrey)](#-licencia)

</div>

You can buy me a coffee... or help me update my Pascal GPUs!
ΧΜΡ: bc1qdwd85m7va6zetwjat9un3agxvvxg65tsld9v8j
BTC: 8BdiSxgPtYTXaG8MB8WehKBQkQYpxxYcBcVSTGqh4s3jdYqDNuHL2KnFiRKs7bZqpASssKfGUjYFseL3931M4dseVLiZwA6

**⚡ Editor de circuitos y simulador MNA unificado, con diseño algorítmico de PCB y agentes autónomos vía MCP**

---

> 🚧 **Proyecto en desarrollo activo.** La arquitectura y las herramientas cambian con frecuencia — consulta [`docs/status/FORGE_STATUS.md`](docs/status/FORGE_STATUS.md) para ver el estado real y [`docs/status/CURRENT_SPRINT.md`](docs/status/CURRENT_SPRINT.md) para el sprint en curso.

## 🎯 ¿Qué es Pulse?

**PulseLab Forge** es un editor de circuitos y simulador **MNA** (Modified Nodal Analysis) que va del esquema conceptual a los archivos de fabricación industrial (Gerbers, Drill, CPL) sin salir de un único flujo de trabajo.

A diferencia de un editor de esquemáticos clásico, Pulse integra un **motor de layout de PCB algorítmico** propio (auto-emplazamiento, ruteo, exportación) y un **servidor MCP local con 31 herramientas**, de forma que un agente LLM puede diseñar, revisar y exportar un circuito completo de forma autónoma — desde "diseña un ESP32 con BME280 en I2C" hasta el Gerber final listo para PCBWay o JLCPCB.

### Características principales

| Módulo | Descripción |
|---|---|
| 🖥️ **Simulador y editor visual** (`pulse_lab.py`) | Interfaz PyGame con render anti-aliased, motor MNA para simulación temporal, osciloscopio en vivo, componentes R/C/L/fuentes/switches |
| 🧩 **Diseño algorítmico de PCB** | Auto-emplazamiento (lineal, circular, simetrías), generación nativa de `.kicad_pcb` (S-Expression), ruteo automatizado, export Gerber vía `kicad-cli` |
| 🧠 **Inteligencia y RAG** | Servidor **MCP** local con 31 herramientas, RAG híbrido (TF-IDF + embeddings) sobre normativas IPC-2221 y pinouts de KiCad, modelo local por defecto `qwythos-9b-96k` (Ollama) |
| 🛠️ **Forge Studio** (`studio/`) | REPL headless con streaming en vivo de `thinking` + `content`, pensado para depurar el pipeline LLM sin PyGame |

## 🚀 Inicio rápido

### Requisitos previos

- **Python 3.10+**
- **KiCad 8+** (para exportación Gerber/SVG — debe estar en el `PATH` o instalado de forma estándar)
- **Ollama** corriendo en `:11431` con el modelo `qwythos-9b-96k` (necesario para Forge Studio y Forge GUI)

### Instalación

```bash
git clone https://github.com/anarcoiris/Pulse.git
cd Pulse
pip install -r requirements.txt
```

### Arrancar el editor principal

```bash
python pulse_lab.py
```

## 🧠 Cómo diseña un circuito el agente

```
Usuario: "Diseña un ESP32 con BME280 en I2C"

Flujo interno:

  1. El servidor MCP (31 herramientas) recibe la petición
     → identifica los componentes necesarios: ESP32, BME280

  2. El motor RAG híbrido (TF-IDF + embeddings) consulta
     → normativas IPC-2221 y pinouts de KiCad indexados

  3. circuit_synthesizer genera el netlist
     → elige huellas (footprints) para cada componente

  4. pcb_layout.py ejecuta el auto-emplazamiento y el ruteo
     → genera las pistas de forma algorítmica

  5. gerber_export.py invoca kicad-cli
     → produce Gerbers, Drill y CPL listos para fabricación
```

**Sin este pipeline**, diseñar un PCB implica pasar manualmente por el esquemático, el ruteo y la exportación en la UI de KiCad. **Con él**, un agente puede completar todo el ciclo describiendo el circuito en lenguaje natural.

## 📁 Estructura del proyecto

```
Pulse/
├── core/                 ← Motor de simulación y bases de datos
│   ├── component_db.py
│   ├── netlist.py
│   └── rf_tools.py
├── bridge/               ← Interconexión con KiCad
│   ├── pcb_layout.py     ← Motor procedural de .kicad_pcb
│   ├── kicad_bridge.py   ← Localizador de binarios / SKiDL
│   └── gerber_export.py  ← Orquestador de kicad-cli
├── knowledge/            ← Motor RAG y agentes LLM
│   ├── circuit_synthesizer
│   └── semantic_reviewer
├── studio/               ← Forge Studio (REPL headless, python -m studio)
├── mcp_server/           ← Servidor MCP (31 herramientas expuestas)
├── ui/                   ← Componentes de interfaz PyGame
├── webapp/               ← Frontend web (TypeScript)
├── examples/             ← Ejemplos y casos de referencia
├── presets/              ← Plantillas y configuraciones predefinidas
├── scripts/              ← Utilidades y automatizaciones
├── tests/                ← Suite de tests (pytest)
├── docs/                 ← Documentación del proyecto
└── Pulse_cfg.json        ← Configuración del backend LLM
```

## 🛠️ Componentes principales

| Componente | Responsabilidad |
|---|---|
| **pulse_lab.py** | Editor visual y simulador MNA (PyGame) |
| **bridge/pcb_layout.py** | Motor procedural de layout de PCB |
| **bridge/gerber_export.py** | Exportación a archivos de fabricación vía `kicad-cli` |
| **knowledge/circuit_synthesizer** | Genera netlists y elige huellas de componentes |
| **knowledge/semantic_reviewer** | Revisión semántica del circuito generado |
| **studio/** | REPL de depuración LLM con streaming en vivo |
| **mcp_server/** | Expone 31 herramientas a Claude Desktop u otros agentes MCP |

## 🎬 Modos de uso

### Editor principal (PyGame)

```bash
python pulse_lab.py
```

### Forge Studio — shell LLM con streaming (Windows Terminal recomendado)

```powershell
$env:PYTHONIOENCODING='utf-8'
pip install -r requirements.txt
python -m studio
python -m studio --backend primary   # qwythos-9b-96k (auto por defecto)
```

Ejemplo de sesión:

```
studio> /backends
studio> Diseña un ESP32 con BME280 en I2C
studio> /review
studio> /schematic
studio> /save output/studio_circuit.json
studio> /quit
```

Los logs de la sesión LLM se guardan en `knowledge/data/llm_sessions/sessions/{session_id}/`.

### Servidor MCP (Claude Desktop u otros agentes)

```bash
python -m mcp_server.server
```

### Validación batch (Calibration Forge)

```bash
python -m knowledge.validate_complex_apps --case esp32_sensors
```

## 🧪 Testing

```bash
pytest tests/
```

## 📚 Documentación

| Documento | Contenido |
|---|---|
| [`docs/README.md`](docs/README.md) | Mapa de toda la documentación |
| [`docs/status/CURRENT_SPRINT.md`](docs/status/CURRENT_SPRINT.md) | Sprint activo, blockers, próximas acciones |
| [`docs/status/FORGE_STATUS.md`](docs/status/FORGE_STATUS.md) | Métricas (tests, RAG, MCP) |
| [`docs/roadmap.md`](docs/roadmap.md) | Fases del producto |
| [`docs/calibration_forge/index.md`](docs/calibration_forge/index.md) | Investigación de Calibration Forge |
## ⚠️ Post-Mortem Note: The 12-Day Validation Gap (July 18, 2026)

**A note from the Steward:** Between July 7 and July 18, the project experienced a seeming halt in LLM validation tasks (Session 4b). Initial reviews incorrectly diagnosed this as "resume-driven development" or strategic avoidance. 

The reality was a severe hardware-level crash: dynamic prompt caching (`--cache-ram`) in `llama.cpp` was causing high-bandwidth PCIe bursts that physically dropped GPU1 from the bus, corrupting orchestrator sessions and causing kernel-level hangs. 

While the hardware fault was being diagnosed and mitigated (via dynamic tensor splitting and `--cache-ram 0`), the team wisely pivoted to building the `skills/` knowledge base architecture—a task that required structural engineering rather than heavy LLM execution. 

With the Qwythos orchestrator now stabilized, the repository documentation has been fully synchronized, and we are clear to resume the pipeline blockers. For full details on the hardware crash, see [`docs/calibration_forge/verification/pcie_instability_postmortem.md`](docs/calibration_forge/verification/pcie_instability_postmortem.md).


## 🤝 Contribuciones

Este proyecto está en evolución constante y las contribuciones son bienvenidas:

- **Reporta bugs o ideas** abriendo un [issue](https://github.com/anarcoiris/Pulse/issues).
- **Propón cambios** vía pull request — indica claramente qué módulo tocas (`core`, `bridge`, `knowledge`, `studio`, `mcp_server`...) y por qué.
- Antes de un PR grande, es buena idea abrir primero un issue para discutir el enfoque.

## 📄 Licencia

Este repositorio no incluye actualmente un archivo `LICENSE`. Si tienes previsto que otras personas usen, modifiquen o distribuyan el código, te recomendamos añadir uno explícito (por ejemplo MIT o Apache-2.0) lo antes posible.

---

<div align="center">

**Si este proyecto te resulta útil, considera darle una ⭐**

[⭐ Star](https://github.com/anarcoiris/Pulse/stargazers) · [🍴 Fork](https://github.com/anarcoiris/Pulse/fork) · [🐛 Issues](https://github.com/anarcoiris/Pulse/issues)

Proyecto de [@anarcoiris](https://github.com/anarcoiris)

</div>
