# Ingesta de Datos: Parsing de KiCad 8 (S-Expressions)

## Objetivo
Desarrollar un importador capaz de leer archivos `.kicad_sch` y `.kicad_pcb` de KiCad 8 para extraer la "Verdad Terrenal" (Ground Truth) de diseños de referencia.

## Retos del Formato KiCad 8
- **S-Expressions:** Estructuras anidadas de paréntesis.
- **Coordenadas:** KiCad usa `(at X Y ANGLE)`. Necesitamos mapear a nuestro `CircuitGraph` visual (grid).
- **Librerías:** KiCad usa nombres largos `Device:R`. Debemos mapear a nuestros tipos internos (`R`, `C`, etc.).

## Implementación Propuesta
- **Parser Simple:** No usaremos dependencias externas pesadas. Implementaremos un tokenizador basado en regex para identificar bloques `(symbol ...)`, `(wire ...)`, `(pad ...)` y `(segment ...)`.
- **Inversión Espacial:** 
    - `gc = (kicad_x - OFFSET_X) / SCALE`
    - `gr = (kicad_y - OFFSET_Y) / SCALE`

## Salida
Genera un objeto `CircuitGraph` poblado que el sistema intentará replicar.
