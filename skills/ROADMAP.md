# Roadmap — knowledge base PulseLab

Prioridad ordenada por evidencia real observada en las corridas
adjuntas, no por cobertura teórica del dominio. Cada ítem indica qué
lo motiva y cuál es el criterio de "hecho".

## ✅ Hecho en esta sesión

- [x] `_corpus-meta/ARCHITECTURE.md` — decisión de desacoplo y modelo
      intermedio v0.
- [x] `evaluation/schemas/finding.schema.json` + `evaluation/skills/SKILL.md`
      — contrato de feedback, reemplaza prosa libre de `semantic_review`.
- [x] `schematic-rules/{rules,skills}/power_on_reset*` — bug de EN
      observado 2/2 corridas.
- [x] `ee-fundamentals/{rules,skills}/decoupling_per_ic*` — 7 findings
      redundantes colapsados en 1 regla por componente.
- [x] `tool-adapter/netlist-propio/SKILL.md` — frontera del netlist propio,
      incluye normalización de alias de red (`3.3V`/`3V3`, `GND`/`GND_PAD`)
      y distinción `ic` real vs. `connector` bajo el mismo `etype: IC`.
- [x] `_case-studies/pulselab_zero_run2.md` — lecciones trazables a las
      dos corridas concretas.

## Fase 1 — cerrar los hallazgos ya detectados en review.md (siguiente sesión)

Motivado directamente por los hallazgos restantes del `review.md` adjunto
que aún no tienen regla propia:

- [ ] `schematic-rules/rules/i2c_bus_pullups.yaml` +
      skill — el caso "SCL con resistor 4.7k a GND" es un error de
      topología distinto de "falta pull-up"; hay que modelar
      correctamente qué significa un pull-up de I2C (resistencia entre
      la línea y VCC, **no** entre la línea y GND) y por qué el generador
      parece haber invertido el mismo tipo de error que en `EN`. Sospecha:
      **puede ser el mismo bug de raíz que power_on_reset** (confundir
      destino "a power rail" con destino "a GND" al generar pull-ups en
      general) — investigar si es una única regla de generación mal
      aprendida (`pull-up genérico`) en vez de dos bugs distintos.
- [ ] `schematic-rules/rules/boot_strap_pins.yaml` + skill — formalizar
      qué pines de un MCU son "strap" (GPIO0/BOOT) vs. "reset" (EN),
      porque hoy se tratan con la misma severidad conceptual y no deberían.
- [ ] `component-library/parts/esp32-s3.yaml` — pinout de referencia con
      roles (no solo número↔nombre), para poder resolver `unconnected_pins`
      con significado real y para que `power_on_reset`/`boot_strap_pins`
      tengan de dónde tomar el rol de cada pin sin heurísticas de nombre.

## Fase 2 — completar `component-library` para los 4 componentes del proyecto

- [ ] `component-library/parts/{ssd1306,pn532,cc1101}.yaml` — mismo
      formato que esp32-s3.yaml. Sin esto, cualquier regla que dependa de
      "rol del pin" para estos componentes sigue apoyándose en heurísticas
      de nombre de red, que es justo el punto débil que ya vimos con `n1`/
      `n2`.
- [ ] `component-library/skills/led-modeling-gap.md` — el LED modelado
      como `etype: S` (ver caso de estudio run 2) necesita una skill que
      documente la heurística de detección hasta que el netlist propio
      tenga un `etype: LED` dedicado.

## Fase 3 — PCB (aún sin evidencia directa, las corridas adjuntas son solo esquemático)

- [ ] `pcb-rules/skills/decoupling-placement.md` — la规la de desacoplo de
      Fase 0 solo verifica *que exista* el condensador; falta la
      contraparte de PCB que verifique *proximidad física* al pin de
      alimentación del IC. No implementar antes de tener al menos un
      `run_session` con datos de PCB (footprint placement), para no
      escribir reglas especulativas.
- [ ] `pcb-rules/rules/stackup_basics.yaml` — bloqueado hasta tener un
      caso real; no crear sin evidencia (ver principio de crecimiento en
      ARCHITECTURE.md).

## Fase 4 — adaptador KiCad

- [ ] `tool-adapter/kicad/SKILL.md` — traducir `.kicad_sch`/`.kicad_pcb`
      al mismo modelo intermedio que ya usa `netlist-propio`. Puede
      empezar en paralelo a las fases 1-2 porque no depende de ellas
      (es una traducción hacia el mismo modelo, no una regla nueva) —
      pero conviene esperar a tener el modelo intermedio estabilizado por
      al menos 2-3 componentes reales de `component-library` para no
      tener que retocar el mapeo dos veces.

## Fase 5 — orchestration

- [ ] `orchestration/skills/iteration-loop.md` — cuándo el agente debe
      parar de iterar (todos los `critical` resueltos, `warning`s
      aceptados explícitamente o resueltos), cómo priorizar qué finding
      atacar primero cuando hay varios (regla propuesta: todos los
      `critical` antes que cualquier `warning`, y dentro de cada
      severidad, por domain en el orden `ee_fundamentals` →
      `schematic` → `pcb`, porque un fallo eléctrico de base invalida
      cualquier verificación topológica posterior).
- [ ] Mecanismo de promoción corpus: cuando el mismo `rule_id` aparece
      repetido en N corridas distintas sin que el generador aprenda a
      evitarlo, es señal de que la skill correspondiente necesita
      ejemplos adicionales o mayor prominencia — definir ese umbral N y
      el proceso de revisión humana antes de tocar el corpus canónico.

## No hacer todavía (evitar sobre-ingeniería)
- No crear reglas de EMC/RF a pesar de que el diseño lleva un transceptor
  sub-GHz (CC1101) — no hay evidencia aún de que el sistema actual llegue
  a nivel de layout de antena; esperar a Fase 3 con datos reales.
- No normalizar todo el vocabulario `etype` de golpe — solo se toca
  cuando un caso real (como el LED-como-switch) lo exige.
