# Knowledge base de diseño electrónico — Pulse

## Empieza aquí
1. `_corpus-meta/ARCHITECTURE.md` — por qué está desacoplado así y el
   modelo intermedio que usan todas las reglas.
2. `_corpus-meta/ROADMAP.md` — qué existe, qué sigue, y por qué en ese
   orden (evidencia real, no cobertura teórica).
3. `_case-studies/` — corridas reales anotadas; cada regla nueva debería
   poder señalar un caso aquí que la motive.

## Estructura
```
ee-fundamentals/     física y cálculos (desacoplo, pull-up/down, márgenes)
schematic-rules/     ERC, topología, patrones por función
pcb-rules/            DRC, stack-up, SI/EMC (vacío aún, ver ROADMAP fase 3)
component-library/    pinouts de referencia con roles semánticos
dfm/                  reglas de fabricación (vacío aún)
tool-adapter/
  netlist-propio/     traduce el JSON actual (etype/n1/n2) al modelo intermedio
  kicad/              (placeholder, fase 4)
evaluation/           esquema de findings + cómo puntuar/estructurar feedback
orchestration/        cómo itera el agente (vacío aún, ver ROADMAP fase 5)
_corpus-meta/         arquitectura y roadmap (este dominio no es técnico)
_case-studies/        corridas reales anotadas
```

Cada `rules/*.yaml` tiene un `skill_ref` a su `skills/*.md` hermana, y
comparten `rule_id`. Un dominio nunca importa contenido de otro dominio
directamente — si `pcb-rules` necesita saber algo de `ee-fundamentals`,
pasa por el modelo intermedio, no por un import cruzado.

## Estado actual (2026-07-16)
2 reglas activas, ambas motivadas por los 2 `run_session` de
`pulselab_zero.json` adjuntos:

- `schematic.power_on_reset.en_pullup` — critical, bug confirmado en 2/2 corridas
- `ee_fundamentals.decoupling.per_ic_100nf` — warning (critical si es MCU)

Ver `_corpus-meta/ROADMAP.md` para lo siguiente.
