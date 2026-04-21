# Estrategia de Logging y Trazabilidad (AI-Aware)

## Introducción
El sistema requiere una trazabilidad completa de cada decisión del motor Forge (colocación, ruteo, DRC) para permitir una depuración profunda y proporcionar contexto en tiempo real a la LLM.

## Arquitectura del Logger
- **Centralización:** Un único objeto `PulseLogger` en `core/logger.py`.
- **Niveles de Log:**
    - `DEBUG`: Detalles del algoritmo A* (nodos explorados).
    - `INFO`: Pasos de alto nivel (Mapeando componente X).
    - `WARNING`: Discrepancias no críticas (Ej: Red "0" tratada como "GND").
    - `ERROR`: Fallos fatales en la ruta o netlist.
    - `AI_REVIEW`: Sugerencias y auditorías de la IA.

## AI Context Buffer (Memoria Circular)
- Se implementará un `deque(maxlen=200)` que almacena los últimos logs significativos.
- En caso de error o duda, PulseLab inyectará este buffer en el prompt de la LLM como "Historial de Ejecución Reciente".

## Formato de Salida
`[TIMESTAMP] [MODULE] [LEVEL] Message`
Archivo: `./logs/pulse_forge.log`
