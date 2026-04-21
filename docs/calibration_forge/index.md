# Índice de Investigaciones: Calibration Forge (Iterativa)

Este documento orquesta las líneas de investigación necesarias para implementar el bucle de entrenamiento y validación de PulseLab Forge.

## Plan de Ejecución Principal
- [implementation_plan.md](../../implementation_plan.md): Hoja de ruta para la implementación del sistema evaluador y el bucle de entrenamiento.

## Módulos de Investigación
1.  [Estrategia de Logging](./logging_strategy.md): Trazabilidad total y búfer de contexto para la LLM.
2.  [Ingesta de Referencias (Parsing)](./kicad_parsing.md): Análisis del formato S-Expression de KiCad 8 para importar diseños "Golden Standard".
3.  [Investigación de Datasets](./dataset_research.md): Fuentes de datos masivas (GitHub, Hugging Face, SparkFun) y métodos de extracción automatizada.
4.  [Métricas de Validación](./evaluation_metrics.md): Definición matemática del éxito de una reproducción de hardware.
5.  [Normalización GND/0](./gnd_unification.md): Coherencia entre redes de simulación y redes de producción física.

## Estabilización y Refactorización (Pendiente)
- **Undo/Redo Fix:** Corrección de la temporización de snapshots (Snapshot-First).
- **Modelo Multipin:** Unificación de conectividad para ICs/MCUs en Editor, Netlist y Esquemáticos.
- **Interactividad AI:** Habilitación de eventos para el popup de revisión semántica.
- **Headless Mode:** Desacoplamiento de Pygame para ejecución en racks de servidores o tests automáticos.

## Próximos Pasos (Milestones)
- [ ] Implementar el `PulseLogger` global.
- [ ] Refactorizar el modelo de pines para soporte MCU completo.
- [ ] Construir el `KicadImporter` básico para lectura de símbolos.
- [ ] Realizar el primer test de evaluación con la **ESP-32 2.0 Devboard**.

---
*Última actualización: 20 de Abril de 2026*
