# Workflow: Limpieza de Directorio Raíz (Root Cleanup)

Este workflow define el plan de acción para resolver el anti-patrón de "Root Clutter" en el proyecto PulseLab.

## Objetivo
Mover los módulos del núcleo lógico a sus respectivos paquetes y archivar los scripts obsoletos para mantener la raíz limpia y facilitar el onboarding de desarrolladores.

## Plan de Actuación

1.  **Migración del Motor MNA:**
    *   Mover `circuit_engine.py` (el solver MNA principal) a `core/circuit_engine.py`.
    *   Actualizar todas las importaciones en `pulse_lab.py`, `ui/editor.py` y los tests para apuntar a `core.circuit_engine`.
2.  **Migración de Suite de Pruebas:**
    *   Mover `test_circuit_engine.py` a `tests/test_circuit_engine.py`.
    *   Asegurar que las pruebas pasen exitosamente con la nueva ruta usando pytest.
3.  **Archivado de Scripts Legacy:**
    *   Crear un directorio `legacy/` o moverlos a `examples/`.
    *   Archivar `ai_studio_code.py`, `emp_simulator.py` y `circuit_generator.py`. Estos scripts representaban pruebas de concepto tempranas (como el control del motor Pulse o iteraciones de generación de código IA).

## Criterios de Aceptación
- El directorio raíz solo debe contener `pulse_lab.py` como punto de entrada de la aplicación, configuraciones (`.gitignore`, `requirements.txt`) y carpetas del sistema.
- La ejecución de `python pulse_lab.py` debe levantar la UI y simular sin arrojar excepciones de `ModuleNotFoundError`.
