# Métricas de Validación y Evaluación (Forge Evaluator)

## Objetivo
Cuantificar qué tan cerca está nuestra generación automática de un diseño de referencia profesional.

## Niveles de Evaluación

### 1. Integridad Lógica (Netlist Match)
- **Topología:** Comparar si todos los terminales de los componentes están conectados a los mismos nodos.
- **Detección de Cortos/Abiertos:** El sistema debe alertar si nuestra versión "abre" un circuito que en la referencia está cerrado.

### 2. Estética y Colocación (Geometric Match)
- **Error de Centroides:** Distancia euclidiana entre la posición del componente original y el generado.
- **Error de Orientación:** Delta de rotación (0, 90, 180, 270).

### 3. Ruteo (Routing Fidelity)
- **Longitud de Pistas:** Comparación de longitud total de cobre.
- **Topología de Traces:** ¿Pasamos por los mismos puntos de control que el diseñador humano?

## Tolerancias admitidas
- `Posición`: < 2.54mm (0.1 inch) de desviación.
- `Orientación`: Debe ser exacta.
- `Netlist`: Debe ser 100% idéntica (Error crítico si falla).
