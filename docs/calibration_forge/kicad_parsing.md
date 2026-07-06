# Ingesta de Datos: Parsing de KiCad 8 (S-Expressions)

## Objetivo
Desarrollar importadores capaces de leer archivos KiCad 8+ en formato S-expression para extraer la "Verdad Terrenal" (Ground Truth) de diseños de referencia **y** el catálogo de componentes de las librerías oficiales.

## Alcance de formatos

| Formato | Estado | Uso |
|---|---|---|
| `.kicad_sch` | Parcial (`kicad_schematic_parser.py`, `kicad_importer.py`) | Ground truth de esquemáticos, RAG `circuit_example` |
| `.kicad_pcb` | Parcial (`kicad_importer.py`) | Nets, footprints, conectividad PCB |
| `.kicad_sym` | **Implementado (Sesión 4a, 06-jul-2026)** | Pinouts de 5320 símbolos reales (29 librerías) — ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) §Resultado |
| `.kicad_mod` | No implementado | Footprints (geometría de pads) — futuro |

## Retos del Formato KiCad 8
- **S-Expressions:** Estructuras anidadas de paréntesis.
- **Coordenadas:** KiCad usa `(at X Y ANGLE)`. Necesitamos mapear a nuestro `CircuitGraph` visual (grid).
- **Librerías:** KiCad usa nombres largos `Device:R`. Debemos mapear a nuestros tipos internos (`R`, `C`, etc.).

## Implementación Propuesta
- **Parser Simple:** No usaremos dependencias externas pesadas. Implementaremos un tokenizador basado en regex para identificar bloques `(symbol ...)`, `(wire ...)`, `(pad ...)` y `(segment ...)`.
- **Símbolos (`.kicad_sym`):** mismo enfoque — extraer `(pin ... (name "...") (number "..."))` por símbolo. `find_kicad_symbol_dir()` en `bridge/kicad_bridge.py` resuelve la ruta (extendido en Sesión 4a para detectar instalaciones de usuario bajo `AppData\Local\Programs`); `knowledge/kicad_symbol_parser.py` implementa el parser (con resolución de `extends` y fusión multi-unidad). Detalle en [`kicad_symbol_kb.md`](./kicad_symbol_kb.md).
- **Inversión Espacial:** 
    - `gc = (kicad_x - OFFSET_X) / SCALE`
    - `gr = (kicad_y - OFFSET_Y) / SCALE`

## Salida
Genera un objeto `CircuitGraph` poblado que el sistema intentará replicar.
