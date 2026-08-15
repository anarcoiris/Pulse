# Workflow: Implementación de Suite de Pruebas (Testing Suite)

Este workflow detalla la estrategia de validación de calidad del repositorio, mitigando el riesgo de romper el motor físico con actualizaciones en la UI.

## Objetivo
Mover la validación desde scripts monolíticos hacia el marco de pruebas `pytest` automatizado y agnóstico a la interfaz gráfica.

## Plan de Actuación

1.  **Configuración del Framework:**
    *   Asegurar que `pytest` esté presente en `requirements.txt`.
    *   Configurar `tests/conftest.py` para asegurar que las variables de entorno de Pygame (`SDL_VIDEODRIVER="dummy"`) permitan ejecutar tests sin inicializar ventanas gráficas, posibilitando pruebas en integración continua (CI/CD).
2.  **Migración de Tests Base:**
    *   Mover y adaptar `test_circuit_engine.py` para que use el formato nativo de aserciones de `pytest` (e.g. `assert is_valid`).
3.  **Expansión de Cobertura (ComponentDB y Bridge):**
    *   Crear `tests/test_component_db.py` para probar la deserialización de parámetros y que los modelos tengan reglas IPC-2221 válidas.
    *   Crear `tests/test_forge.py` simulando la extracción de S-expressions para validar que el `bridge/pcb_layout.py` no colapse con redes de componentes complejos.
4.  **Ejecución Regular:**
    *   Todos los Pull Requests deben cumplir con los comandos: `pytest tests/` arrojando un exit code 0.

## Criterios de Aceptación
- Cobertura de tests validada localmente con el comando nativo `pytest`.
- Los simuladores no invocan drivers gráficos (Pygame dummy display mode funcionando).
