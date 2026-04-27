# Workflow: Refactorización de Modales de UI (UI Modals)

Este workflow define la estrategia para resolver el patrón de "God Object" que plaga actualmente al archivo `pulse_lab.py`, extrayendo la lógica de las ventanas emergentes (modales).

## Objetivo
Desacoplar las funciones complejas de dibujo (`_draw_ai_popup`, `_draw_ai_gen_popup`, `_draw_forge_popup`) del loop principal del framework, orientándolo a una arquitectura más escalable.

## Plan de Actuación

1.  **Creación de Paquete de UI Auxiliar:**
    *   Crear un nuevo archivo `ui/modals.py`.
2.  **Abstracción de Clases:**
    *   Implementar una clase abstracta `Modal` que maneje el rectángulo base (`pygame.Rect`), el "dim" del fondo oscuro (`(0,0,0,180)`), y el botón estándar de cierre.
    *   Crear clases hijas derivadas: `ForgeResultModal`, `AIGeneratorModal`, `AIReviewModal`.
3.  **Inyección de Dependencias:**
    *   Cada Modal recibirá las funciones de callback para sus botones en lugar de inyectar variables de estado directas en `self`. (Por ejemplo, pasar una función `on_submit_prompt(text)` al `AIGeneratorModal`).
4.  **Limpieza en `pulse_lab.py`:**
    *   Eliminar las tuplas y diccionarios como `self._ai_gen_popup` e instanciar las clases en el constructor (`__init__`).
    *   Delegar la intercepción de clics en `_handle_event` al método `modal.handle_event(event)`.
    *   Delegar el dibujado llamando a `modal.draw(surf, fonts)` directamente.

## Criterios de Aceptación
- Reducción del tamaño del archivo `pulse_lab.py` en al menos 200 líneas.
- La funcionalidad de la barra lateral, popups de IA y de exportación continúan funcionando idénticamente.
