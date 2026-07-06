# PulseLab Forge — Revisión técnica (05 julio 2026): recap de estado, correcciones y líneas de investigación

> Revisión realizada el 5 de julio de 2026, a partir de inspección directa de código, logs de ejecución del día (`knowledge/data/validation_complex/runs/20260705_*`), y `docs/baseline_report.md`.
> **Supera y corrige** a [`pulselab_review_23042026.md`](./pulselab_review_23042026.md) — varios hallazgos de esa revisión ya están resueltos; otros siguen abiertos y se detallan aquí con más profundidad.
> Ver también: [`docs/roadmap.md`](../roadmap.md) · [`docs/calibration_forge/index.md`](../calibration_forge/index.md) · [`FORGE_STATUS.md`](../../FORGE_STATUS.md)

---

## 1. Resumen ejecutivo

Desde la revisión de abril, PulseLab Forge ha resuelto la mayoría de los gaps de fabricación (P0/P1) y ha dado un salto de infraestructura LLM (modelo local `qwythos-9b-96k`, 98k ctx, RAG híbrido denso+TF-IDF). El pipeline de generación → PCB → Gerber sigue verificado y ahora corre a diario contra casos de validación complejos (ESP32 + sensores, steppers, RF/NFC).

Sin embargo, tres problemas de **fidelidad de la información** persisten y son more sutiles que "falta una feature": el pipeline **trunca datos que ya existen** (pines físicos, descripciones en lenguaje natural de los ejemplos de entrenamiento) y **sobre-especifica en el prompt** reglas que el modelo actual, mejor y con más contexto, probablemente podría inferir de un RAG bien poblado. Se documentan en detalle en tres nuevos informes de investigación (§4).

Además, dos piezas de infraestructura ya construidas (`core/logger.py` / `PulseLogger`, `knowledge/design_experience.py`) están **implementadas pero no integradas/alimentadas** — ver [`dormant_features_audit.md`](../calibration_forge/dormant_features_audit.md).

---

## 2. Estado verificado (05-jul-2026)

| Área | Estado | Evidencia |
|------|--------|-----------|
| Pipeline `CircuitGraph → .kicad_pcb → Gerber` | ✅ Verificado | `docs/baseline_report.md`, 3 placas de ejemplo + runs de hoy |
| Tests | 8/8 `test_forge.py`, 4/4 `test_rag_retrieval.py` | `docs/baseline_report.md` |
| RAG | Híbrido TF-IDF + `nomic-embed-text` (358 chunks, 326 `circuit_example`) | `knowledge/rag_engine.py`, `knowledge/data/embeddings/manifest.json` |
| Backend LLM | Doble carril: `primary` (qwythos-9b-96k, razonamiento, 98304 ctx) + `atomic` (llama-server, ejecución MCP rápida) | `Pulse_cfg.json` |
| MCP tools | **31** herramientas expuestas (no 23 — ver §3) | `mcp_server/server.py` |
| DRC Gate | ✅ Implementado (`kicad-cli pcb drc` obligatorio antes de exportar) | `docs/workflows/fabrication_pipeline.md` |
| Autorouter | ✅ A* con clearance/dilation por pad, penalización de vías, 2 capas — **no es el gap que se creía** | `bridge/pcb_layout.py:829-940`, usado en `bridge/pcb_builder.py:255` |
| Footprints SMD (ESP32, QFN, etc.) | ✅ Vía biblioteca KiCad (`get_kicad_footprint`) | `bridge/kicad_bridge.py` |
| Multiplataforma `kicad-cli` | ✅ `shutil.which` + fallback por SO (Win/macOS/Linux) | `bridge/kicad_bridge.py:30-51` |
| `requirements.txt` en raíz | ✅ Presente | `requirements.txt` |
| Esquemático nativo `.kicad_sch` + render SVG | ✅ Implementado | `bridge/schematic_generator.py`, `bridge/gerber_export.py` |
| `PulseLogger` (logging unificado + buffer de contexto IA) | ✅ Implementado, ❌ **no integrado** en el pipeline real | `core/logger.py` (solo referenciado en `tests/test_import_esp32.py`) |
| Design-experience feedback loop | ✅ Implementado, ❌ **no está produciendo datos** | `knowledge/design_experience.py`, `knowledge/experiences/` vacío |
| PDF datasheet ingestion | ❌ Pendiente | No hay `pdfminer` en `requirements.txt`, sin referencias en código |
| Parámetros S / scikit-rf | ❌ Pendiente | No hay `skrf`/`scikit-rf` en el repo |
| CI/CD | ❌ Pendiente | No existe `.github/workflows/` |

---

## 3. Correcciones respecto a la revisión de abril (23-04-2026)

La revisión anterior señaló varios gaps que **ya están resueltos** y uno que sigue vigente pero mal diagnosticado:

| # | Hallazgo abril 2026 | Estado real hoy | Nota |
|---|---|---|---|
| 3.1 | Sin `requirements.txt` | ✅ Resuelto | Presente en raíz con deps pineadas (sin versiones exactas todavía — ver §5) |
| 3.2 | Rutas Windows hardcodeadas | ✅ Resuelto | `shutil.which` + candidatos por SO |
| 3.4 | "Autorouter sin evitación de colisiones" | ✅ Resuelto | Implementado A* con `occupied` set, dilatación de pads por `clearance=0.35mm`, coste de vía. La propuesta original (`OccupancyGrid` + BFS) nunca se creó como archivo aparte, pero el problema que resolvía ya no existe: la solución tomó otra forma (A* dentro de `pcb_layout.py`) |
| 3.5 | Sin footprints SMD para MCUs modernos | ✅ Resuelto | `get_kicad_footprint` + símbolos `RF_Module:ESP32-WROOM-32`, etc. |
| 3.6 | Sin DRC antes de exportar | ✅ Resuelto | Gate obligatorio documentado en `docs/workflows/fabrication_pipeline.md` |
| 3.3 | "RAG demasiado básico" (solo TF-IDF) | ⚠️ Parcialmente resuelto, pero **el síntoma correcto era otro** | El backend ahora es híbrido (denso + TF-IDF), pero el problema real no era el algoritmo de retrieval — es que **el contenido indexado está incompleto** (ver `knowledge_base_fidelity.md`). Mejorar el motor de búsqueda no ayuda si los chunks no contienen la información relevante. |
| 3.7 | Archivos de trabajo en el repo (`scratch/`) | ⚠️ Sigue presente | `scratch/test_drc_fail.py` sigue en el repo; sin verificar `.gitignore` |
| 3.8 | Sin CI/CD | ❌ Sigue pendiente | — |

**FORGE_STATUS.md desactualizado:** listaba 23 tools MCP; hoy son 31 (corregido en este ciclo de sync, ver commit de este documento).

---

## 4. Hallazgos nuevos — líneas de investigación abiertas

Estos tres hallazgos nacen de una intuición del usuario validada contra el código real. Cada uno tiene su propio informe de investigación con evidencia línea-por-línea y próximos pasos concretos:

### 4.1 [Cobertura de pines físicos incompleta](../calibration_forge/pin_model_coverage.md)
~~El pipeline truncaba pinouts a 14 pines y el ejemplo estático anclaba salidas de 4 pines.~~ **Mitigado en Session 3 (06-jul-2026):** pinout completo para match primario, convención NC, métrica Pin Coverage Fidelity. ~~La **fuente** de pinouts sigue siendo `pinouts_library.json` (~12 entradas manuales)~~ **resuelto en Session 4a (06-jul-2026)** — ver §4.5: la fuente ahora es un índice real de 5320 símbolos KiCad, con `pinouts_library.json` reducido a capa de override.

### 4.2 [Pérdida de descripciones en lenguaje natural del knowledge base](../calibration_forge/knowledge_base_fidelity.md)
Dos bugs de indexación independientes:
1. El parser de esquemáticos KiCad (`knowledge/kicad_schematic_parser.py`) nunca extrae `title_block`, `text` ni `label` — solo `lib_id`/`Reference`/`Value`. Los ~280 esquemáticos humanos indexados son solo bolsas de componentes sin contexto de diseño.
2. Para las muestras auto-generadas (`knowledge/data/training/sample_*.json`), el campo `metadata.prompt` (la descripción en lenguaje natural original, ej. *"RLC con LED, funcionando como receptor de pulsos..."*) existe en el JSON pero **`_summarize_circuit_data()` nunca lo lee** porque busca `data["source"]` en la raíz en vez de `data["metadata"]["prompt"]`. Es un bug de 1-2 líneas, no una limitación arquitectónica.

### 4.3 [Prompts sobre-especificados vs. RAG + modelo más capaz](../calibration_forge/prompt_vs_rag_balance.md)
`circuit_synthesizer.py` y `semantic_reviewer.py` codifican reglas de electrónica como texto imperativo fijo en el system prompt (UART crossover, pull-ups, desacoplo) en vez de dejar que el modelo las infiera de ejemplos recuperados. ~~Además existe un sistema de retrieval paralelo y redundante (`_match_pinouts()`, scoring por keywords) que duplica lo que `ElectronicsKnowledgeBase` ya hace mejor.~~ **Retrieval unificado en Session 4a (06-jul-2026)** — `_match_pinouts()` ahora consulta `ElectronicsKnowledgeBase` (`chunk_type="pinout"`) en vez de un scorer ad-hoc propio, ver `kicad_symbol_kb.md` §Resultado. La pregunta de las reglas fijas en el prompt sigue abierta para el experimento A/B de Session 4b. Con un modelo de razonamiento local más grande, esta rigidez probablemente resta más de lo que aporta.

### 4.4 [Funcionalidades construidas pero inactivas](../calibration_forge/dormant_features_audit.md)
~~`PulseLogger` y el loop de `design_experience.py` están completos mas no conectados/alimentados en el flujo real.~~ **Resuelto en Session 2 (06-jul-2026)** — ver §Resultado en ese documento.

### 4.5 [Base de conocimiento de componentes desde KiCad](../calibration_forge/kicad_symbol_kb.md)
~~`pinouts_library.json` y `components.json` se mantienen a mano (~12 y ~10 entradas)... `find_kicad_symbol_dir()` localiza las librerías pero ningún parser las lee aún.~~ **Implementado en Session 4a (06-jul-2026)** — ver [`kicad_symbol_kb.md` §Resultado](../calibration_forge/kicad_symbol_kb.md#resultado-sesión-4a-06-jul-2026): `kicad_symbol_parser.py` + `build_symbol_index.py` indexaron 5320 símbolos reales (29 librerías) desde una instalación local de KiCad 10.0 hallada bajo `AppData\Local\Programs` (ruta que `find_kicad_symbol_dir()` no cubría, también corregido esta sesión); ingestados en el RAG como 5326 chunks `chunk_type="pinout"`. `pinouts_library.json` se mantiene como capa de override (no deprecado del todo — sigue siendo la única fuente para módulos breakout sin símbolo KiCad oficial).

---

## 5. Otros puntos menores observados

- `scratch/test_drc_fail.py` sigue en el repo (higiene, bajo impacto).
- `requirements.txt` no fija versiones — riesgo de romper el solver MNA si `numpy`/`pygame` suben de major version sin test de regresión (ver `docs/architecture/SEGURIDAD_DEPENDENCIAS.md`).
- `docs/Architecture.md` / `docs/Architecture_violations.md` (raíz de `docs/`) y `docs/architecture/APP_ARCHITECTURE.md` / `ARCHITECTURE_VIOLATIONS.md` (subcarpeta) son documentos **duplicados con contenido distinto** — el de raíz menciona "Autorouting: Initial A* implementation" (ahora confirmado correcto) mientras el de la subcarpeta no lo menciona. Recomendable fusionar o clarificar cuál es la fuente de verdad.

---

## 6. Próximos pasos sugeridos (orden propuesto)

| Prioridad | Tarea | Doc de referencia |
|---|---|---|
| ✅ Hecho | Corregir `_summarize_circuit_data()` para indexar `metadata.prompt` | → ver `knowledge_base_fidelity.md` §Resultado (density 80%, USB test fixed) |
| ✅ Hecho | Extender `KiCadSchematicParser` para capturar `title_block`/`text`/`label` | → ver `knowledge_base_fidelity.md` §Resultado (320 archivos re-ingestados) |
| ✅ Hecho | Eliminar el cap de 14 pines en `_compact_pinout()`; inyectar tabla completa del MCU detectado | → ver `pin_model_coverage.md` §Resultado (match primario 39/39 pines en prompt) |
| ✅ Hecho | Añadir convención `"unconnected_pins"` / `NC` al esquema de salida del sintetizador | → ver `pin_model_coverage.md` §Resultado + `evaluation_metrics.md` §4 |
| ✅ Hecho | Base de conocimiento de pinouts desde KiCad (`.kicad_sym` → RAG) en vez de curar `pinouts_library.json` a mano | → ver `kicad_symbol_kb.md` §Resultado (Session 4a: 5320 símbolos / 29 librerías → 5326 chunks `pinout`) |
| 🟡 Media | Auditar y, si procede, recortar las "REGLAS OBLIGATORIAS" del prompt de `circuit_synthesizer.py` a favor de RAG con más ejemplos (`rag_top_k` > 1) | `prompt_vs_rag_balance.md` |
| ✅ Hecho | Conectar `core/logger.py` al pipeline real (`pcb_layout.py`, `circuit_synthesizer.py`, `gerber_export.py`) | → ver `dormant_features_audit.md` §Resultado (Session 2) |
| ✅ Hecho | Investigar por qué `knowledge/experiences/` está vacío pese a `record_design_outcome()` estar wired | → ver `dormant_features_audit.md` §Resultado (Session 2) |
| 🟢 Baja | Fusionar/clarificar duplicidad `docs/Architecture*.md` vs `docs/architecture/*.md` | — |
| 🟢 Baja | Pin versions en `requirements.txt` | — |

---

*Este documento se sincroniza con `docs/roadmap.md`, `docs/calibration_forge/index.md` y `FORGE_STATUS.md` en el mismo commit.*
