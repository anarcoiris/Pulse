# Índice de Investigaciones: Calibration Forge (Iterativa)

Este documento orquesta las líneas de investigación necesarias para implementar el bucle de entrenamiento y validación de PulseLab Forge.

## Plan de Ejecución Principal
- [implementation_plan.md](../../implementation_plan.md): Hoja de ruta para la implementación del sistema evaluador y el bucle de entrenamiento.

## Revisiones Técnicas
- [pulselab_review_05072026.md](../reviews/pulselab_review_05072026.md): Revisión vigente — recap de estado, correcciones sobre la revisión de abril, y origen de los 4 hallazgos de investigación nuevos listados abajo.
- [pulselab_review_23042026.md](../reviews/pulselab_review_23042026.md): Revisión histórica (superada).

## Módulos de Investigación
1.  [Estrategia de Logging](./logging_strategy.md): Trazabilidad total y búfer de contexto para la LLM. Implementación base (`core/logger.py`) lista — ver estado de integración en [`dormant_features_audit.md`](./dormant_features_audit.md).
2.  [Ingesta de Referencias (Parsing)](./kicad_parsing.md): Análisis del formato S-Expression de KiCad 8 para importar diseños "Golden Standard". Gaps de extracción documentados en [`knowledge_base_fidelity.md`](./knowledge_base_fidelity.md).
3.  [Investigación de Datasets](./dataset_research.md): Fuentes de datos masivas (GitHub, Hugging Face, SparkFun) y métodos de extracción automatizada.
4.  [Métricas de Validación](./evaluation_metrics.md): Definición matemática del éxito de una reproducción de hardware. Propuesta de nueva métrica "Pin Coverage Fidelity" en [`pin_model_coverage.md`](./pin_model_coverage.md).
5.  [Normalización GND/0](./gnd_unification.md): Coherencia entre redes de simulación y redes de producción física.

## Hallazgos de Investigación Activos (05-jul-2026)
6.  [Cobertura de pines físicos](./pin_model_coverage.md): la tabla de pines de los MCUs se trunca antes de llegar al LLM (cap de 14 pines); circuitos generados representan una fracción mínima de los pines reales (4/39 en ESP32-WROOM-32 observado hoy).
7.  [Fidelidad del Knowledge Base](./knowledge_base_fidelity.md): ~~la intención de diseño… se pierde en la ingesta~~ **resuelto** (06-jul-2026) — density 80%, USB retrieval fixed; ver §Resultado.
8.  [Balance Prompt vs. RAG](./prompt_vs_rag_balance.md): reglas de electrónica hardcodeadas como texto fijo en los prompts de `circuit_synthesizer.py`/`semantic_reviewer.py`, en paralelo a un motor de retrieval propio que duplica al RAG existente — a revisar ahora que el backend local (`qwythos-9b-96k`, 98k ctx) tiene más capacidad de razonar sobre contexto recuperado. POC de migración de una regla (`ESP32 EN pull-up`) a `DesignExperience` ya disponible como evidencia — ver `dormant_features_audit.md` §Resultado.
9.  [Auditoría de funcionalidades inactivas](./dormant_features_audit.md): ~~`PulseLogger` y `design_experience.py` están implementados pero no integrados/alimentando datos~~ **resuelto** (06-jul-2026) — PulseLogger wired en 4 módulos + 2 call sites; `knowledge/experiences/` ahora produce y persiste datos; ver §Resultado.

## Estabilización y Refactorización (Pendiente)
- **Undo/Redo Fix:** Corrección de la temporización de snapshots (Snapshot-First).
- **Modelo Multipin:** Unificación de conectividad para ICs/MCUs en Editor, Netlist y Esquemáticos. Ver hallazgo #6 (`pin_model_coverage.md`) — el problema se confirmó también a nivel de generación LLM, no solo de Editor.
- **Interactividad AI:** Habilitación de eventos para el popup de revisión semántica.
- **Headless Mode:** Desacoplamiento de Pygame para ejecución en racks de servidores o tests automáticos.

## Próximos Pasos (Milestones)
- [x] Implementar el `PulseLogger` global (`core/logger.py`) e integrarlo en el pipeline real (`pcb_layout.py`, `gerber_export.py`, `circuit_synthesizer.py`, `semantic_reviewer.py`) — `dormant_features_audit.md` §Resultado (06-jul-2026).
- [ ] Refactorizar el modelo de pines para soporte MCU completo — investigación abierta en `pin_model_coverage.md`.
- [x] Construir el `KicadImporter` básico para lectura de símbolos (Verificado con ESP8266).
- [x] Realizar el test de evaluación avanzada con la **ESP-32 2.0 Devboard** — corridas diarias en `knowledge/validate_complex_apps.py` (`esp32_sensors`, `esp32_steppers`, `esp32_rf_nfc`, `esp32_usb_devkit`, `pulselab_zero`).
- [x] Corregir indexación de `metadata.prompt` en `_summarize_circuit_data()` — `knowledge_base_fidelity.md` §Resultado.
- [x] Extender `KiCadSchematicParser` para capturar `title_block`/`text`/`label` — `knowledge_base_fidelity.md` §Resultado.
- [x] Confirmar por qué `knowledge/experiences/` no acumulaba datos y corregirlo (causa raíz: hook nunca alcanzado por flujos probados + `ingest_to_rag()` no persistía entre procesos) — `dormant_features_audit.md` §Resultado (06-jul-2026); cubierto permanentemente por `tests/test_forge.py::test_design_experience_loop`.

---
*Última actualización: 06 de Julio de 2026 (sesión de wiring PulseLogger + design-experience loop)*
