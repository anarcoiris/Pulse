# Current sprint — Robustez Geométrica y Contextual (Agosto 2026)

> **Role:** living  
> **Status:** active  
> **Source of truth for:** session order, blockers, and next actions  
> **Last verified:** 2026-08-06  
> **See also:** [`../calibration_forge/index.md`](../calibration_forge/index.md) · [`../roadmap.md`](../roadmap.md) · [`../status/FORGE_STATUS.md`](./FORGE_STATUS.md)

## Execution order (Agosto Sprint)

**PCB Builder** ✅ → **Audit Gate R001-R014** ✅ → **Modular Providers & 128k Ctx** ✅ → **A* Autorouter Clearance Engine** ✅ → **KiCad 10.0 PCB/SCH Sync** ✅ → **Estabilización LLM Context** ⏳

## Where we are (06-aug-2026)

| Hito / Módulo | Estado | Documento / Artefacto |
|---------------|--------|-----------------------|
| Automated PCB Builder | ✅ | `bridge/pcb_builder.py` |
| Topological Audit Gate (R001-R014) | ✅ | `core/kicad_audit.py` (15 unit tests) |
| Modular LLM Providers | ✅ | `knowledge/providers/` |
| Multi-turn 128k Context Agent | ✅ | `knowledge/circuit_agent.py` |
| A* Autorouter Clearance Engine | ✅ Completado | Envolvente de clearance $0.35\,\text{mm}$ y corredor de pista $0.50\,\text{mm}$ (`bridge/pcb_layout.py`) |
| KiCad 10.0 PCB/SCH Synthesis | ✅ Completado | Sintaxis S-expr `net_class` raíz, cabecera 10.0.3 con propiedad `Footprint` (CLI `Returncode 0`) |
| Cross-check Esquemático↔PCB | ✅ Completado | `core/sch_pcb_crosscheck.py` (3 unit tests, 100% Coincidencia) |
| Reducción Reintentos LLM (<3) | ⏳ Pendiente | Optimización de prompts en síntesis compleja |

## Next actions

1. **Estabilización LLM Context & Prompts**: Optimización de prompts para reducir reintentos en síntesis complejas de circuitos.
2. **Validación End-to-End**: Re-ejecutar el arnés de prueba en `pulselab_zero` y `flipper_multiboard` tras aplicar las mejoras de ruteado y clearance.
3. **Consolidación de Reglas Diferenciales**: Definición de clases de red avanzadas en `knowledge/data/flipper_multiboard_pcb.json`.

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


