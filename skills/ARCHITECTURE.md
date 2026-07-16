# Arquitectura de la knowledge base — PulseLab / Pulse-main

## Principio rector

El agente necesita tres piezas separadas, y cada una vive en su propio dominio
sin que ninguna sepa demasiado de las otras:

1. **Conocimiento estable** (por qué las cosas son como son)
2. **Reglas verificables** (qué comprobar, automáticamente)
3. **Bucle de evaluación** (cómo se traduce un fallo en feedback útil)

La regla de desacoplamiento más importante de este proyecto concreto:

> Ningún dominio de conocimiento (`ee-fundamentals`, `schematic-rules`,
> `pcb-rules`, `component-library`) conoce el formato de netlist propio
> (`etype`/`n1`/`n2`/`label`) ni sabe nada de KiCad. Solo lo conoce
> `tool-adapter/`.

## Por qué: el adaptador como frontera

Se ha decidido prever ya una capa de traducción a KiCad (no solo trabajar
sobre el netlist propio). Esto significa que el netlist propio pasa a ser
**un adaptador más**, no el formato nativo del corpus.

```
netlist propio (JSON actual)  ──┐
                                 ├──► modelo intermedio neutral ──► reglas / skills (ee-fundamentals, schematic-rules, pcb-rules, component-library)
KiCad (futuro)                 ──┘                                          │
                                                                             ▼
                                                                  evaluation (feedback estructurado)
```

- `tool-adapter/netlist-propio/`: traduce el JSON actual
  (`{etype, value, n1, n2, label, pins, symbol, footprint}`) al modelo
  intermedio.
- `tool-adapter/kicad/`: (placeholder, fase posterior) traducirá
  `.kicad_sch` / `.kicad_pcb` al mismo modelo intermedio.
- Ninguna regla en `schematic-rules/` o `pcb-rules/` debe mencionar `etype`,
  `n1`/`n2`, ni ninguna clave literal del JSON. Si una regla necesita saber
  "es un pin de alimentación", pregunta al modelo intermedio, no al JSON.

## Modelo intermedio (v0)

Basado en lo observado en `pulselab_zero.json` (dos corridas) y `review.md`.
Este modelo es deliberadamente pequeño — se amplía solo cuando un caso real
lo exige, no por anticipación.

```yaml
component:
  ref: str            # "U1", "R_EN", "C3" — identificador único en el diseño
  kind: enum           # power_source | mcu | ic | resistor | capacitor
                       # | switch | connector | led | inductor | ...
  part_value: str|num  # "ESP32-S3" | 10000.0 | 1e-07
  pins: [Pin]          # lista de pines con rol conocido, no solo número

pin:
  number: str          # "3", "EN" (en conectores genéricos el netlist
                       # propio no siempre distingue número físico de
                       # nombre de red — el adaptador debe resolverlo)
  role: enum           # power_in | ground | signal_digital | signal_analog
                       # | i2c_sda | i2c_scl | spi_mosi | spi_miso | spi_sck
                       # | spi_cs | reset_enable | boot_strap | led_anode
                       # | led_cathode | nc | unknown
  net: str             # nombre de la red a la que está unido

net:
  name: str
  role: enum           # power_rail | ground | signal | strap
  nominal_voltage: float|null

# IMPORTANTE — lección del caso PulseLab:
# n1/n2 en el netlist propio NO tiene semántica de polaridad fija
# (a veces es "3.3V,GND", otras "GND,3.3V" según el componente).
# El adaptador netlist-propio SIEMPRE debe derivar el rol de cada extremo
# a partir de (a) el nombre de la red si coincide con un alias conocido
# de power/ground, y (b) el `etype` + pinout de referencia del componente,
# nunca por la posición n1 vs n2.
```

## Dominios y su contrato

| Dominio | Sabe sobre | No sabe sobre |
|---|---|---|
| `ee-fundamentals` | física, márgenes, cálculos (I²R, desacoplo, pull-up/down) | formato de archivo, EDA concreto, fabricante |
| `schematic-rules` | topología correcta, ERC, patrones por función (power-on, bus, botón) | PCB físico, KiCad, JSON |
| `pcb-rules` | rutado, stack-up, SI/EMC, DRC | topología de esquemático, JSON |
| `component-library` | pinouts de referencia, roles de pines por parte | reglas de diseño, formato de salida |
| `dfm` | reglas de fabricación (tolerancias, anillos, distancias) | EE, esquemático |
| `tool-adapter` | sintaxis de netlist propio y de KiCad | reglas de diseño (solo traduce) |
| `evaluation` | cómo puntuar/estructurar feedback | contenido de las reglas en sí (solo las ejecuta) |
| `orchestration` | cómo itera el agente (cuándo parar, cómo priorizar fixes) | contenido técnico de ningún dominio |

## Formato de cada dominio de reglas/skills

Cada regla verificable vive como YAML en `<dominio>/rules/`, con esquema
común (ver `evaluation/schemas/finding.schema.json`). Cada skill narrativa
vive como Markdown en `<dominio>/skills/`, siguiendo la convención
`SKILL.md` (contexto, cuándo aplica, por qué, ejemplos correcto/incorrecto).

Una regla YAML y su skill Markdown correspondiente comparten el mismo
`rule_id` para que el feedback pueda enlazar directamente a la explicación.

## Principio de crecimiento

No se escribe ninguna regla "por si acaso". Cada regla nueva debe poder
señalar un caso real (un `run_session` concreto, un patrón observado dos
veces) que la motiva. Las dos primeras skills de este corpus
(`power-on-reset` y `decoupling-per-ic`) existen porque aparecen, de forma
casi idéntica, en las dos corridas de `pulselab_zero.json` adjuntas.
