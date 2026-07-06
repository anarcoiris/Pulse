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

3. **Inteligencia y RAG (`rag_engine.py`, `mcp/server.py`)**
   - Sistema de agentes LLM interoperables gracias a un servidor local **MCP** con 23 herramientas expuestas.
   - Puede diseñar un circuito entero, elegir huellas para los componentes, hacer el ruteo algorítmicamente y exportarlo a Gerber de forma autónoma.
   - Integra motor RAG local (TF-IDF) para consultar normativas IPC-2221 (Reglas de diseño de PCB, separaciones, capacidades de corriente de pistas) y buscar los MCUs idóneos en la base de datos interna.

## Requisitos

- **Python 3.10+**
- **Dependencias:** `pygame`, `numpy`, `skidl`, `mcp` ... (Ver `requirements.txt` o dependencias estándar).
- **Herramientas externas:** KiCad 8.0+ para la exportación de Gerbers. Debe estar en el PATH del sistema o instalado en los directorios estándares (`C:\Program Files`, `D:\Program Files`). 

## Uso

```bash
# Iniciar el Editor Principal:
python pulse_lab.py

# Iniciar servidor MCP para Claude Desktop u otros agentes:
python mcp/server.py
```

## Arquitectura

- **`core/`**: Motor de simulación y bases de datos (`component_db.py`, `netlist.py`, `rf_tools.py`).
- **`bridge/`**: Motor de interconexión con KiCad.
  - `pcb_layout.py`: Nuestro potente motor procedural de `.kicad_pcb`.
  - `kicad_bridge.py`: Localizador de binarios e interoperabilidad general con SKiDL/KiCad.
  - `gerber_export.py`: Orquestador de CLI para extraer archivos de fabricación.
- **`knowledge/`**: Motor de búsqueda RAG y conocimiento de diseño electrónico.
- **`ui/`**: Los componentes de interfaz de usuario para el editor gráfico.

---

*Proyecto en constante evolución.* Consulte `FORGE_STATUS.md` para métricas técnicas, herramientas MCP expuestas al detalle y hoja de ruta actual.

## Documentación y estado del proyecto

- [`docs/roadmap.md`](docs/roadmap.md) — hoja de ruta activa, fases futuras y enlaces a revisiones/investigación.
- [`docs/reviews/pulselab_review_05072026.md`](docs/reviews/pulselab_review_05072026.md) — revisión técnica vigente (recap de estado + líneas de investigación abiertas).
- [`docs/calibration_forge/index.md`](docs/calibration_forge/index.md) — índice de investigaciones del bucle de calibración/entrenamiento.
- [`docs/architecture/APP_ARCHITECTURE.md`](docs/architecture/APP_ARCHITECTURE.md) — arquitectura del sistema.
