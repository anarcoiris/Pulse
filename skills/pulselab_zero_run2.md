# Caso de estudio: PulseLab Zero, dos corridas comparadas

Fuente: `pulselab_zero.json` (dos documentos adjuntos con el mismo
`test_case` pero distinto `run_session`), `review.md`.

## Run 1 — `validate_20260713_003837_9f03979b`
Generación desde prompt completo (diseño desde cero). `generation_attempts:
5`. `average_coverage: 0.8854`. `semantic_review.issue_count: 0` en el
propio JSON, pero el `review.md` adjunto (que corresponde a esta corrida)
sí detalla 11 issues, 3 críticos — inconsistencia entre el conteo embebido
en el JSON y el reporte real, a anotar como posible bug del pipeline de
reporting, no del diseño.

## Run 2 — `validate_20260714_151243_a4d4c864`
Generación incremental: prompt pide una modificación puntual ("añade un
condensador de 100nF cerca del ESP32 y un LED de estado en GPIO2") sobre
un circuito base pegado literalmente en el prompt. `generation_attempts:
2`. `average_coverage: 1.0` (mejora frente a run 1 porque ahora sí
completa el pinout de los 48 pines del ESP32-S3 en vez de 26).
`semantic_review.issue_count: 11`, `critical_count: 3` — **los mismos
3 críticos que en run 1, casi palabra por palabra.**

## Lecciones que motivan reglas/skills

1. **El bug de EN (pull-down en vez de pull-up) sobrevive una edición
   incremental completa.** Esto confirma que no es un fallo puntual de
   una generación, sino ausencia de conocimiento persistente → justifica
   `schematic.power_on_reset.en_pullup` como prioridad #1.

2. **El "fix" del LED de estado introduce nombres de red nuevos
   (`3V3`, `GND_PAD`) que conviven con los nombres originales (`3.3V`,
   `GND`) del resto del circuito**, en vez de reutilizar el rail
   existente. Esto es exactamente el tipo de fallo que
   `tool-adapter/netlist-propio/SKILL.md` debe normalizar antes de que
   llegue a cualquier regla — si no, una regla de desacoplo podría no
   reconocer que `C3` (sobre `3V3`/`GND_PAD`) y `C1`/`C2` (sobre
   `3.3V`/`GND`) están en el mismo rail físico.

3. **El LED se modela como `etype: "S"`** (`LED_STATUS`, nodos
   `LED_ANODE`↔`GND_PAD`), el mismo `etype` que usan los pulsadores
   del D-Pad. Un LED no es un interruptor — esto es una limitación real
   del vocabulario `etype` actual que el adaptador debe resolver por
   heurística de nombre de red (`*_ANODE`/`*_CATHODE` → `kind: led`) hasta
   que el netlist propio tenga un `etype` dedicado. Ver
   `component-library/skills/led-modeling-gap.md` (pendiente, roadmap).

4. **La resistencia serie del LED (`R_LED = 220Ω`) sí está presente** —
   esto es correcto y no debe generar ningún finding. Buen ejemplo positivo
   a conservar como caso de regresión: un checker mal escrito podría
   marcar falsamente el LED como "sin serie resistor" si no reconoce el
   patrón `resistor entre power_rail y led_anode`.

5. **`average_coverage` subió de 0.8854 a 1.0 sin que se resolviera
   ningún critical.** Esto confirma que cobertura de pines y corrección
   semántica son señales independientes — nunca usar cobertura como proxy
   de corrección. Ambas deben reportarse como findings separados
   (`domain: coverage` vs. `domain: schematic`/`ee_fundamentals`), nunca
   colapsadas en un único score.
