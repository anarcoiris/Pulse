# Current sprint — Robustez Geométrica y Contextual (Agosto 2026)

> **Role:** living  
> **Status:** active  
> **Source of truth for:** session order, blockers, and next actions  
> **Last verified:** 2026-08-15  
> **See also:** [`../calibration_forge/index.md`](../calibration_forge/index.md) · [`../roadmap.md`](../roadmap.md) · [`../status/FORGE_STATUS.md`](./FORGE_STATUS.md)

## Execution order (Agosto Sprint)

**PCB Builder** ✅ → **Audit Gate R001-R014** ✅ → **Thermal & Ground Zone Engines** ✅ → **Component DB & Multi-Provider Fetchers** ✅ → **100% SCH↔PCB Parity** ✅ → **FastAPI Backend & Web UI** ⏳

## Where we are (15-aug-2026)

| Hito / Módulo | Estado | Documento / Artefacto |
|---------------|--------|-----------------------|
| Automated PCB Builder | ✅ | `bridge/pcb_builder.py` |
| Topological Audit Gate (R001-R014) | ✅ | `core/kicad_audit.py` (15 unit tests) |
| Thermal Management Engine | ✅ Completado | `core/thermal_engine.py` (grid $3 \times 3$ en EPAD) |
| Ground Pour & Via Stitching Grid | ✅ Completado | `core/copper_zone_manager.py` (planos 0V + stitching) |
| Systematized Component DB & Candidates | ✅ Completado | `core/component_db.py` (39 componentes) |
| Multi-Provider Supply Chain Engine | ✅ Completado | `core/providers/` (JLCPCB + PCBWay con cache 24h) |
| Cross-check Esquemático↔PCB | ✅ Completado | `core/sch_pcb_crosscheck.py` (100% coincidencia) |
| FastAPI Backend Gateway | ⏳ Pendiente | `app/main.py` (`/api/v1/generate-pcb`) |

## Next actions

1. **FastAPI Backend Gateway (`app/main.py`)**: Implementar endpoint `/api/v1/generate-pcb` para orquestar la generación HTTP.
2. **Web Canvas Frontend (`webapp/`)**: Desarrollar visualizador web 2D SVG y WebGL 3D.

## Active blockers

- **Ninguno**: El ruteador A* rutea el 100% de los segmentos de señal (33/33) y la carga CLI de KiCad 10.0 funciona de manera totalmente limpia sin errores.

## Key numbers (06-aug-2026)

- RAG: **5687** chunks (5328 `pinout`, 326 `circuit_example`)
- Signal Net Routing: **100% (33/33 segmentos)** en `flipper_killer_mk_ii_0.6`
- KiCad 10 CLI Load: **Returncode 0** (`trazado SVG sin errores`)
- Tests: **112** collected (`pytest tests/ --co -q`); Audit: **15** unit tests (`test_kicad_audit.py`); Crosscheck: **3** unit tests (`test_sch_pcb_crosscheck.py`)
- MCP tools: **31** (`mcp_server/server.py`)

## Changes since last sync (18-jul → 06-aug)

- **PCB Builder Unificado**: Implementada la generación algorítmica de S-expressions para KiCad 10.0 / 8.0 (`bridge/pcb_builder.py`).
- **Auditoría Estricta**: Desarrollado `core/kicad_audit.py` con 14 reglas estructurales (R001-R014) y suite de pruebas (`test_kicad_audit.py`).
- **Sincronización Nativa KiCad 10.0**: Formato de cabecera `(generator_version "10.0.3")` en `.kicad_sch` con propiedad `Footprint` y `(net_class "Default" ...)` a nivel raíz en `.kicad_pcb`.
- **Motor de Clearance A* ($0.35\,\text{mm}$)**: Incorporado bloqueo de envolvente física de pads y reserva de corredores de pistas ($0.50\,\text{mm}$) en `bridge/pcb_layout.py`.
- **Taladros NPTH M3 & Desplazamiento de Header**: Desplazamiento de `Header_000` a $x=-31.0\,\text{mm}$ y conversión de agujeros de montaje a `np_thru_hole`, eliminando cortocircuitos falsos.
- **Nomenclatura Unificada (SSOT)**: Prefijos de dominio estándar (`PWR_`, `SPI_FLIPPER_`, `CS_RF_`, `UART_ESP_`, `USB_ESP_`, `EN_ESP_`).


