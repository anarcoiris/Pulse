---
component: tool-adapter
adapts_from: "netlist propio (Pulse-main), campos etype/value/n1/n2/label/pins"
adapts_to: "modelo intermedio neutral (ver _corpus-meta/ARCHITECTURE.md)"
---

# Adaptador: netlist propio → modelo intermedio

## Responsabilidad
Este es el único lugar del corpus que puede leer literalmente las claves
`etype`, `n1`, `n2`, `pins` (con clave = número de pin como string) del
JSON que produce hoy el sistema. Ningún dominio de reglas debe importar
ni referenciar estas claves directamente.

## Mapeo `etype` → `kind`
| etype | kind         | notas |
|-------|--------------|-------|
| V     | power_source | fuente ideal, típicamente sintética (`V1`) |
| MCU   | mcu          | siempre tiene `symbol`/`footprint` reales |
| IC    | ic            | ojo: en el netlist actual, conectores puros (headers) también usan `etype: IC` (ver más abajo) |
| R     | resistor      | |
| C     | capacitor     | |
| S     | switch        | usado para botones (D-Pad) — un `S` con dos nodos, no tiene `pins` dict |

## Problema conocido: `IC` se usa para dos cosas distintas
En `pulselab_zero.json`, `etype: "IC"` se usa tanto para ICs reales
(SSD1306, PN532, CC1101) como para el header de expansión (`Header_8`,
`symbol: Connector_Generic:Conn_01x08`). El adaptador debe distinguirlos
por `symbol` (si empieza por `Connector_Generic:` es un conector pasivo,
`kind: connector`, no `kind: ic`) — de lo contrario las reglas de
`ee_fundamentals.decoupling.per_ic_100nf` intentarían exigir un
condensador de desacoplo a un simple header de pines, que no tiene sentido
(un conector no consume corriente ni genera ruido de conmutación).

## Problema conocido: `n1`/`n2` no tiene polaridad fija
Confirmado en las dos corridas: para las resistencias de pull-up de
botones, `n1="3.3V", n2=BTN_X`; pero no hay garantía de que ese orden se
mantenga para todos los componentes o en generaciones futuras. **Nunca**
derivar el rol de un pin de si aparece en n1 o n2. El adaptador resuelve
el rol de cada red por:

1. Coincidencia de nombre con alias conocidos de alimentación
   (`3.3V`, `3V3`, `5V`, `VCC`, `VBAT` → `power_rail`;
   `GND`, `GND_PAD`, `AGND` → `ground`).
2. Si no coincide con un alias, el rol del pin se toma del pinout de
   referencia del componente en `component-library/parts/`, resuelto por
   `component.part_value` (p.ej. `"ESP32-S3"`) y número de pin.

## Problema conocido: nombres de red no normalizados entre corridas
La primera corrida usa `"3.3V"` y `"GND"` de forma consistente. La segunda
corrida (tras una modificación incremental) introduce `"3V3"` y
`"GND_PAD"` como alias del mismo rail y la misma masa, conviviendo en el
mismo circuito con los nombres originales (`C2` sigue usando `"3.3V"`
mientras que `C3`, el nuevo condensador, usa `"3V3"`/`"GND_PAD"`). Esto es
importante porque, si no se normaliza, las reglas de desacoplo pueden
fallar en detectar que dos condensadores están, en la práctica,
sobre el mismo rail físico.

El adaptador debe unificar alias de red **antes** de construir el modelo
intermedio: todas las variantes reconocidas de un mismo rail colapsan a un
único nombre de red canónico (p.ej. `"3.3V"` y `"3V3"` → `POWER_3V3`;
`"GND"` y `"GND_PAD"` → `GND`). Este es un caso real observado, no
hipotético — ver `_case-studies/pulselab_zero_run2.md`.

## Cobertura como passthrough, no como cálculo propio
El adaptador **no recalcula** `pin_coverage` — lo recibe ya calculado por
el sistema existente (`pinouts_library`) y lo traduce a findings
`domain: coverage` (ver `evaluation/skills/SKILL.md`). Un componente en
`pin_coverage.unmatched` sin `symbol` de conector genérico reconocible
debería, a medio plazo, promoverse a `component-library/parts/` para
dejar de aparecer como `unmatched` — eso es una tarea de crecimiento del
corpus (ver ROADMAP), no una regla de diseño.

## Pendiente explícito (no resuelto en v0)
- `unconnected_pins` del ESP32-S3 en la segunda corrida lista 22 pines,
  muchos de los cuales SÍ podrían tener roles conocidos (strapping pins,
  USB D+/D-, etc.) que hoy no se están aprovechando. Se deja como tarea
  de `component-library/parts/esp32-s3.yaml` en el roadmap — no bloquea
  las dos skills iniciales.
