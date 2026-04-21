# Unificación de Redes: El Problema de "0" vs "GND"

## El Conflicto
En simulación SPICE (nuestro motor MNA), el nodo de referencia SIEMPRE es el "0". Sin embargo, en diseño de PCB y esquemáticos reales (KiCad), la red suele llamarse "GND", "VSS" o "EARTH".

## Reglas de Unificación (Normalización)
Para evitar duplicidades o inconsistencias en el "Forge":

1.  **Mapeo de Entrada:** Al importar circuitos, cualquier red con nombre que contenga "GND", "GROUND" o sea el nodo de referencia se mapea internamente al objeto `GND` de PulseLab.
2.  **Mapeo de Salida (PCB):** En el archivo `.kicad_pcb`, la red de retorno siempre se llamará `GND`.
3.  **Audit de Continuidad:** El evaluador detectará si hay nodos "0" que NO están atados al plano de masa físico de la placa.

## Conclusión
Para propósitos de fabricación, "0" == "GND" siempre. No se permiten islas de red "0" flotantes si existe un plano de tierra.
