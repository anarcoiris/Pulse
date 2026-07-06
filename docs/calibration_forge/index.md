# Índice de Investigaciones: Calibration Forge (Iterativa)

Este documento orquesta las líneas de investigación necesarias para implementar el bucle de entrenamiento y validación de PulseLab Forge.

## Plan de Ejecución Principal
- [implementation_plan.md](../../implementation_plan.md): Hoja de ruta para la implementación del sistema evaluador y el bucle de entrenamiento.

## Revisiones Técnicas
- [pulselab_review_05072026.md](../reviews/pulselab_review_05072026.md): Revisión vigente — recap de estado, correcciones sobre la revisión de abril, y origen de los 4 hallazgos de investigación nuevos listados abajo.
- [pulselab_review_23042026.md](../reviews/pulselab_review_23042026.md): Revisión histórica (superada).

## Módulos de Investigación
1.  [Estrategia de Logging](./logging_strategy.md): Trazabilidad total y búfer de contexto para la LLM. Implementación base (`core/logger.py`) lista — ver estado de integración en [`dormant_features_audit.md`](./dormant_features_audit.md).
2.  [Ingesta de Referencias (Parsing)](./kicad_parsing.md): Análisis del formato S-Expression de KiCad 8 para importar diseños "Golden Standard". Gaps de extracción documentados en [`knowledge_base_fidelity.md`](./knowledge_base_fidelity.md). **Próximo gap:** parsing de librerías `.kicad_sym` — ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md).
3.  [Investigación de Datasets](./dataset_research.md): Fuentes de datos masivas (GitHub, Hugging Face, SparkFun) y métodos de extracción automatizada.
4.  [Métricas de Validación](./evaluation_metrics.md): Definición matemática del éxito de una reproducción de hardware. Métrica **Pin Coverage Fidelity** (§4) implementada en Session 3 — ver [`pin_model_coverage.md`](./pin_model_coverage.md) §Resultado.
5.  [Normalización GND/0](./gnd_unification.md): Coherencia entre redes de simulación y redes de producción física.
6.  [Base de conocimiento desde KiCad](./kicad_symbol_kb.md): Extraer pinouts automáticamente de `.kicad_sym` (~20k símbolos) para reemplazar la curación manual de `pinouts_library.json` / ampliar `components.json`. **Implementado en Session 4a** (RAG `chunk_type="pinout"`, 5326 chunks) — ver §Resultado.
7.  [Pipeline LLM — guardrails y backends](./llm_output_pipeline.md): truncación, multi-turn, routing primary/atomic. **Sessions 4c y 4d** — bloquea Session 4b.

## Hallazgos de Investigación Activos (05-jul-2026)
6.  [Cobertura de pines físicos](./pin_model_coverage.md): ~~cap de 14 pines truncaba pinouts antes del LLM~~ **resuelto y confirmado con LLM real** (06-jul-2026) — pinout completo para match primario, convención NC, métrica de cobertura; validación post-fix `esp32_sensors` → **10.3% → 100%** (backend `primary`, `atomic` no disponible); re-confirmado **100%** tras la migración a RAG de Sesión 4a (sin regresión). Presets manuales todavía truncan (~20%) y quedan fuera de alcance de 4a (son datos hand-written, no generación LLM). Ver §Resultado.
7.  [Fidelidad del Knowledge Base](./knowledge_base_fidelity.md): ~~la intención de diseño… se pierde en la ingesta~~ **resuelto** (06-jul-2026) — density 80%, USB retrieval fixed; ver §Resultado.
8.  [Balance Prompt vs. RAG](./prompt_vs_rag_balance.md): … **Depende de Session 4a (completada)** y **Sessions 4c+4d (guardrails LLM)** — correr como **Session 4b** solo tras ellas.
9.  [Auditoría de funcionalidades inactivas](./dormant_features_audit.md): ~~`PulseLogger` y `design_experience.py` están implementados pero no integrados/alimentando datos~~ **resuelto** (06-jul-2026) — PulseLogger wired en 4 módulos + 2 call sites; `knowledge/experiences/` ahora produce y persiste datos; ver §Resultado.
10. [Base de conocimiento desde KiCad](./kicad_symbol_kb.md): ~~`pinouts_library.json` (~12 entradas manuales) no escala~~ **resuelto** (Session 4a, 06-jul-2026) — `kicad_symbol_parser.py` + `build_symbol_index` indexaron 5320 símbolos reales (29 librerías) → RAG `chunk_type="pinout"` (5326 chunks, incluyendo overrides curados); `_match_pinouts()` y `_pin_coverage()` migrados; `pytest` 79/79; `esp32_sensors` 100% de cobertura sin regresión. Ver doc para arquitectura en capas, drift de nombres confirmado y gaps conocidos (módulos breakout sin símbolo KiCad, `ESP8266_Node`).
11. [Truncación y retries LLM](./llm_truncation_review_06072026.md): **abierto** — investigación profunda y fix en **Session 4c** (guardrails + multi-turn) y **Session 4d** (orquestación dual-backend). Plan maestro: [`llm_output_pipeline.md`](./llm_output_pipeline.md). **Bloquea Session 4b** hasta 4c P0.
12. [Pipeline LLM (guardrails + backends)](./llm_output_pipeline.md): plan de arquitectura y entregables 4c/4d.

## Estabilización y Refactorización (Pendiente)
- **Undo/Redo Fix:** Corrección de la temporización de snapshots (Snapshot-First).
- **Modelo Multipin:** Unificación de conectividad para ICs/MCUs en Editor, Netlist y Esquemáticos. Ver hallazgo #6 (`pin_model_coverage.md`) — el problema se confirmó también a nivel de generación LLM, no solo de Editor.
- **Interactividad AI:** Habilitación de eventos para el popup de revisión semántica.
- **Headless Mode:** Desacoplamiento de Pygame para ejecución en racks de servidores o tests automáticos.

## Próximos Pasos (Milestones)
- [x] Implementar el `PulseLogger` global (`core/logger.py`) e integrarlo en el pipeline real (`pcb_layout.py`, `gerber_export.py`, `circuit_synthesizer.py`, `semantic_reviewer.py`) — `dormant_features_audit.md` §Resultado (06-jul-2026).
- [x] Refactorizar el modelo de pines para soporte MCU completo (síntesis LLM) — `pin_model_coverage.md` §Resultado (06-jul-2026); medición post-fix confirmada en `esp32_sensors` (100%, run `20260706_130942_b1a9364b`); re-confirmada sin regresión tras Sesión 4a (100%, run `20260706_164955_207f6e23`). Pendiente correr los otros 4 casos (cubierto por baseline A/B de Sesión 4b); presets manuales (~20%) siguen fuera de alcance (datos hand-written, no generación LLM).
- [x] Construir el `KicadImporter` básico para lectura de símbolos (Verificado con ESP8266).
- [x] Realizar el test de evaluación avanzada con la **ESP-32 2.0 Devboard** — corridas diarias en `knowledge/validate_complex_apps.py` (`esp32_sensors`, `esp32_steppers`, `esp32_rf_nfc`, `esp32_usb_devkit`, `pulselab_zero`).
- [x] Corregir indexación de `metadata.prompt` en `_summarize_circuit_data()` — `knowledge_base_fidelity.md` §Resultado.
- [x] Extender `KiCadSchematicParser` para capturar `title_block`/`text`/`label` — `knowledge_base_fidelity.md` §Resultado.
- [x] **Base de conocimiento de pinouts desde KiCad** — `kicad_symbol_parser.py` + `build_symbol_index` + indexación RAG `chunk_type="pinout"` implementados en Session 4a (06-jul-2026); `pinouts_library.json` reducido a capa de override (no deprecado del todo — sigue siendo la única fuente para módulos breakout sin símbolo KiCad oficial). Ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) §Resultado. Sesión 4b (`prompt_vs_rag_balance.md` propuesta #2) queda desbloqueada para correr sobre esta base.
- [ ] **Guardrails de truncación LLM (Session 4c)** — [`llm_output_pipeline.md`](./llm_output_pipeline.md): P0 `done_reason`, validación post-parse MCU, multi-turn recovery, tests.
- [ ] **Orquestación dual-backend (Session 4d)** — reviewer en `atomic`, metadata en harness, routing tests.
- [ ] **Session 4b A/B prompt vs RAG** — solo tras 4c P0 (+ 4d recomendado): [`prompt_vs_rag_balance.md`](./prompt_vs_rag_balance.md).

---
*Última actualización: 06 de Julio de 2026 (Sessions 4c/4d añadidas; 4b reordenada tras guardrails LLM)*
