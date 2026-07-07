# PulseLab Forge

PulseLab Forge es un **Editor de Circuitos y Simulador MNA Unificado** con capacidades avanzadas de diseño de PCB algorítmico y agentes autónomos (vía protocolo MCP). 

Permite ir desde el esquema conceptual, pasando por simulación física rigurosa, hasta la generación directa de archivos de fabricación industrial (Gerbers, Drill, CPL) usando el motor de KiCad bajo la superficie.

## Características

1. **Simulador y Editor Visual (`pulse_lab.py`)**
   - Interfaz con motor de renderizado PyGame, gráficos anti-aliased.
   - Motor MNA (Modified Nodal Analysis) para simulaciones físicas realistas en el dominio temporal.
   - Componentes: R, C, L, Fuentes, Switches.
   - Osciloscopio integrado para visualizar respuestas transitorias en vivo.
   - **NUEVO:** Herramientas "FORGE" integradas en la interfaz de usuario para saltar directo a CAD.

2. **Diseño Algorítmico de PCB (Spatial Layout Engine)**
   - Algoritmos de auto-emplazamiento (distribución lineal, circular, alineaciones estáticas, simetrías).
   - Generación geométrica nativa del formato S-Expression para `.kicad_pcb` sin requerir la UI de KiCad.
   - Generador de pistas (traces) automatizado.
   - Exportación nativa e independiente mediante `kicad-cli` a Gerbers listos para producción (ej. PCBWay).

3. **Inteligencia y RAG (`knowledge/`, `mcp_server/`)**
   - Sistema de agentes LLM interoperables gracias a un servidor local **MCP** con **31** herramientas expuestas.
   - Puede diseñar un circuito entero, elegir huellas para los componentes, hacer el ruteo algorítmicamente y exportarlo a Gerber de forma autónoma.
   - Integra motor RAG híbrido (TF-IDF + embeddings) para consultar normativas IPC-2221 y pinouts KiCad indexados.
   - Modelo local por defecto: **qwythos-9b-96k** vía Ollama (`Pulse_cfg.json`).

4. **Forge Studio (`studio/`) — depuración LLM headless**
   - REPL Rich con streaming en vivo de `thinking` + `content` durante generación y revisión semántica.
   - Sin pygame: proceso separado para calibrar el pipeline Calibration Forge.
   - Comandos: `/generate`, `/review`, `/backends`, `/save`, `/load`, `/schematic`, `/session`, `/quit`.
   - Ver [`docs/calibration_forge/forge_studio.md`](docs/calibration_forge/forge_studio.md).

## Requisitos

- **Python 3.10+**
- **Dependencias:** ver [`requirements.txt`](requirements.txt) (`pygame`, `numpy`, `openai`, `rich`, `mcp`, …).
- **Herramientas externas:**
  - **KiCad 8+** para exportación Gerber/SVG (PATH o instalación estándar).
  - **Ollama** en `:11431` con `qwythos-9b-96k` para generación/revisión LLM (Forge Studio y Forge GUI).

## Uso

### Editor principal (pygame)

```bash
python pulse_lab.py
```

### Forge Studio — shell LLM con streaming (Windows Terminal recomendado)

```powershell
$env:PYTHONIOENCODING='utf-8'
pip install -r requirements.txt
python -m studio
python -m studio --backend primary   # qwythos-9b-96k (default auto)
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

Requisitos: Ollama activo, modelo cargado. Los logs LLM van a `knowledge/data/llm_sessions/sessions/{session_id}/`.

### Servidor MCP (Claude Desktop u otros agentes)

```bash
python -m mcp_server.server
```

### Validación batch (Calibration Forge)

```bash
python -m knowledge.validate_complex_apps --case esp32_sensors
```

## Arquitectura

- **`core/`**: Motor de simulación y bases de datos (`component_db.py`, `netlist.py`, `rf_tools.py`).
- **`bridge/`**: Motor de interconexión con KiCad.
  - `pcb_layout.py`: Nuestro potente motor procedural de `.kicad_pcb`.
  - `kicad_bridge.py`: Localizador de binarios e interoperabilidad general con SKiDL/KiCad.
  - `gerber_export.py`: Orquestador de CLI para extraer archivos de fabricación.
- **`knowledge/`**: Motor RAG, agentes LLM (`circuit_synthesizer`, `semantic_reviewer`), logs de sesión.
- **`studio/`**: Forge Studio — REPL headless para depuración LLM con streaming (`python -m studio`).
- **`ui/`**: Componentes de interfaz pygame para el editor gráfico.

---

*Proyecto en constante evolución.* Consulte [`docs/README.md`](docs/README.md) para el mapa de documentación y [`docs/status/FORGE_STATUS.md`](docs/status/FORGE_STATUS.md) para métricas actuales.

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [`docs/README.md`](docs/README.md) | Mapa de toda la documentación |
| [`docs/status/CURRENT_SPRINT.md`](docs/status/CURRENT_SPRINT.md) | Sprint activo, blockers, next actions |
| [`docs/status/FORGE_STATUS.md`](docs/status/FORGE_STATUS.md) | Métricas (tests, RAG, MCP) |
| [`docs/roadmap.md`](docs/roadmap.md) | Fases del producto |
| [`docs/calibration_forge/index.md`](docs/calibration_forge/index.md) | Investigación Calibration Forge |
| [`docs/calibration_forge/forge_studio.md`](docs/calibration_forge/forge_studio.md) | Forge Studio CLI (streaming LLM debug) |
| [`docs/architecture/APP_ARCHITECTURE.md`](docs/architecture/APP_ARCHITECTURE.md) | Arquitectura del sistema |
