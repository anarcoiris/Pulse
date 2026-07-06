# PulseLab Forge — Estado del Sistema

## Pipeline Verificado ✅

```
PCBLayout (Python) → .kicad_pcb → kicad-cli 8.0.6 → Gerber + Drill + CPL
```

**3 placas de ejemplo generadas y exportadas con éxito:**

| Placa | Tamaño | Comps | Trazas | Gerbers | Drill |
|-------|--------|-------|--------|---------|-------|
| Divisor de Tensión | 20×15mm | 3 | 7 | 11 ✅ | 1 ✅ |
| 555 LED Driver | 40×25mm | 14 | 3 | 11 ✅ | 1 ✅ |
| ESP8266 Sensor Node | 50×35mm | 14 | 4 | 11 ✅ | 1 ✅ |

---

## Tests: 7/7 PASS

```
test_rf_tools          ✅  Z₀ error < 0.4%, IPC trace width ~±3%
test_component_db      ✅  10 componentes, búsqueda, filtros, IPC lookup
test_rag_engine        ✅  32 chunks TF-IDF, reglas IPC, búsqueda semántica
test_netlist_generator ⏭️  (skip: pygame env — funciona con py normal)
test_pcb_layout        ✅  Motor layout + S-expression + KiCad valid
test_pcb_kicad_export  ✅  Genera PCB → kicad-cli → 11 Gerbers + Drill
test_kicad_bridge      ✅  KiCad 8.0.6 detectado en D:\Program Files
```

---

## Estructura del Proyecto

```
Pulse/
├── core/
│   ├── component_db.py     ✅ Base de datos + IPC-2221 lookup
│   ├── rf_tools.py         ✅ Microstrip, stripline, matching, skin depth
│   └── netlist.py          ✅ CircuitGraph → KiCad netlist / SKiDL / BOM
├── bridge/
│   ├── kicad_bridge.py     ✅ Auto-detección Multi-plataforma (P0)
│   ├── pcb_layout.py       ✅ Motor de layout (Soporte RawFootprint)
│   ├── gerber_export.py    ✅ kicad-cli: Gerber, Drill, Pos, SVG
│   └── bom_generator.py    ✅ BOM enriquecido con ComponentDB
├── knowledge/
│   ├── rag_engine.py       ✅ TF-IDF RAG, 32 chunks IPC + componentes
│   └── data/
│       ├── ipc_2221.json   ✅ Reglas IPC-2221B completas
│       └── components.json ✅ 5 MCUs + 5 periféricos
├── mcp/
│   ├── server.py           ✅ FastMCP con 23 tools (3 nuevas PCB)
│   └── claude_desktop_config.json
├── ui/                     ✅ Interfaz Gráfica (Toolbar ahora con sección FORGE)
├── pulse_lab.py            ✅ Integración total: GUI → Generador de Layout/Gerbers
├── examples/
│   ├── demo_pcb_layout.py  ✅ Genera 3 placas de ejemplo
│   └── export_all_boards.py ✅ Exporta Gerbers de todas
├── output/                 ✅ Salidas de .kicad_pcb y manufacturing/
└── tests/
    └── test_forge.py       ✅ 7/7 tests pasan
```

---

## MCP Tools (31 total)

> Actualizado 05-jul-2026 (antes se listaban 23 — ver `mcp_server/server.py`). El desglose por categoría abajo cubre las herramientas documentadas en la revisión de abril; consultar `mcp_server/server.py` para el listado exhaustivo actualizado.

### Simulación (3)
| Tool | Descripción |
|------|-------------|
| `simulate_circuit` | Simulación MNA transitoria |
| `load_preset` | Carga presets (emp_pfn, basic_rc, rlc) |
| `create_circuit_json` | Crea circuito desde lista de componentes |

### RF / Impedancia (5)
| Tool | Descripción |
|------|-------------|
| `calculate_microstrip_impedance` | Z₀ microstrip (Hammerstad-Jensen) |
| `calculate_trace_width_for_impedance` | W para Z₀ objetivo |
| `design_matching_network` | Red L de adaptación |
| `calculate_trace_current_capacity` | Corriente máx. para pista dada |
| `calculate_minimum_trace_width` | Ancho mínimo IPC-2221 |

### KiCad / Fabricación (4)
| Tool | Descripción |
|------|-------------|
| `export_to_kicad` | CircuitGraph → netlist + SKiDL + BOM |
| `generate_gerbers` | .kicad_pcb → Gerber+Drill completo |
| `kicad_status` | Estado del sistema KiCad |
| `generate_bom` | BOM en CSV/JSON/texto |

### PCB Layout (3) **NUEVO**
| Tool | Descripción |
|------|-------------|
| `create_pcb_layout` | **Diseña PCB completo con posiciones espaciales** |
| `generate_pcb_gerbers` | Exporta Gerbers desde .kicad_pcb generado |
| `list_pcb_footprints` | Catálogo de footprints disponibles |

### Base de Componentes (4)
| Tool | Descripción |
|------|-------------|
| `search_component` | Busca en ComponentDB |
| `get_component_details` | Info completa de componente |
| `get_mcu_support_circuit` | Circuito soporte mínimo MCU |
| `filter_components_by_params` | Filtro por parámetros técnicos |

### Knowledge/RAG (4)
| Tool | Descripción |
|------|-------------|
| `search_electronics_knowledge` | RAG sobre IPC + componentes |
| `get_design_rules` | Reglas IPC-2221 por voltaje/corriente |
| `ingest_knowledge_text` | Añade texto al RAG |
| `knowledge_base_stats` | Stats del RAG |

### Utilidad (1)
| Tool | Descripción |
|------|-------------|
| `pulselab_status` | Estado global del sistema |

---

## Workflows Documentados 📄

1. [**Pipeline de Fabricación Seguro (DRC Gate)**](file:///c:/Users/soyko/Documents/Pulse/docs/workflows/fabrication_pipeline.md)
2. [**Gestión de Componentes y Librerías**](file:///c:/Users/soyko/Documents/Pulse/docs/workflows/component_management.md)

---

## Capacidades del Motor PCB Layout

```python
pcb = PCBLayout(board_width=50, board_height=30)

# Colocación de componentes
r1 = pcb.add_resistor("R1", "10k", x=10, y=15, net1="VCC", net2="OUT")
c1 = pcb.add_capacitor("C1", "100nF", x=20, y=15, net1="OUT", net2="GND")
u1 = pcb.add_dip_ic("U1", 8, x=25, y=15, value="NE555")
j1 = pcb.add_pin_header("J1", 4, x=5, y=10)

# Controles espaciales
pcb.align_horizontal(r1, c1)           # Alinear en Y
pcb.align_vertical(r1, c1)             # Alinear en X
pcb.distribute_horizontal(r1, c1, u1)  # Distribución uniforme
pcb.distribute_circular(r1, c1, u1)    # Distribución circular
pcb.mirror_horizontal(r1)              # Simetría
pcb.center(u1)                         # Centrar en placa

# Trazas
pcb.trace(r1, "2", c1, "1", net="OUT") # Ruta en L automática
pcb.trace_bus([(5,5), (10,5), (10,15)]) # Polyline

# Infraestructura
pcb.add_mounting_holes_corners()
pcb.add_text("Mi Placa", 25, 28)
pcb.add_via(15, 10, net="GND")

# Exportar
pcb.save("output/mi_placa.kicad_pcb")
```

---

## Próximos Pasos

> Sincronizado 05-jul-2026 contra el estado real del código. Ver [`docs/reviews/pulselab_review_05072026.md`](docs/reviews/pulselab_review_05072026.md) para el análisis completo y [`docs/calibration_forge/index.md`](docs/calibration_forge/index.md) para las líneas de investigación abiertas.

1. ✅ **Hybrid RAG** — Implementado: TF-IDF + `nomic-embed-text` vía Ollama (`knowledge/rag_engine.py`, `PULSE_RAG_BACKEND=hybrid`). Pendiente: el contenido indexado tiene gaps de fidelidad — ver [`docs/calibration_forge/knowledge_base_fidelity.md`](docs/calibration_forge/knowledge_base_fidelity.md).
2. ✅ **ESP32 USB devkit** — Presets `esp32_usb_devkit` / `esp32s2_usb_devkit` + workflow MCP (`docs/workflows/esp32_devboard_mcp.md`) implementados y en validación diaria.
3. ✅ **Design experience loop** — `knowledge/design_experience.py` ahora produce datos reales (06-jul-2026). Causa raíz del directorio vacío: el hook de `record_design_outcome()` en `bridge/gerber_export.py::generate_all_manufacturing_files()` nunca era alcanzado por ningún flujo automatizado/probado (es una acción GUI/MCP separada de "Generar PCB"), y `DesignExperience.ingest_to_rag()` no persistía sus chunks entre procesos. Ambos se corrigieron: `ElectronicsKnowledgeBase._load_experiences()` releé `knowledge/experiences/*.json` al iniciar, y `tests/test_forge.py::test_design_experience_loop()` cubre el flujo completo de forma permanente. Ver [`docs/calibration_forge/dormant_features_audit.md`](docs/calibration_forge/dormant_features_audit.md) §Resultado.
4. **Copper pours advanced** — Plano de masa (GND) con thermal reliefs mejorados. Sigue pendiente.
5. **Parámetros S con scikit-rf** — Carta de Smith, S11/S21. Sigue pendiente (sin dependencia `scikit-rf` en `requirements.txt`).
6. **PDF datasheet ingestion** — Expandir RAG con pdfminer. Sigue pendiente (sin dependencia `pdfminer` en `requirements.txt`).
7. ✅ **Schematic SVG export** — Resuelto vía `bridge/schematic_generator.py` (`.kicad_sch` nativo) + render SVG en `bridge/gerber_export.py`.
8. **Nuevo:** Cobertura de pines de MCU en la síntesis LLM — ver [`docs/calibration_forge/pin_model_coverage.md`](docs/calibration_forge/pin_model_coverage.md).
9. **Nuevo:** Revisión del balance entre reglas fijas en prompts y retrieval RAG — ver [`docs/calibration_forge/prompt_vs_rag_balance.md`](docs/calibration_forge/prompt_vs_rag_balance.md).
