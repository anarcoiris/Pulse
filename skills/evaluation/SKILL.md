# Skill: estructurar feedback como findings, no como prosa

## Contexto
El sistema actual (`review_backend`) genera `semantic_review.issues` como
objetos `{msg, severity, proposal}` redactados libremente por un LLM
revisor. Esto tiene dos problemas observados directamente en
`pulselab_zero.json`:

1. **Severidad inconsistente entre hallazgos equivalentes**: la ausencia de
   desacoplo en SSD1306 se marca `warning`, pero en el ESP32-S3 se marca
   `critical` — mismo tipo de problema (falta C 100nF cerca de un IC con
   VCC), dos severidades distintas, porque cada instancia la decide el LLM
   revisor de forma independiente en vez de una regla compartida.
2. **El "fix" es texto, no una acción aplicable**: `proposal` dice "Añadir
   un condensador de 100nF entre..." en prosa. El agente generador tiene
   que reinterpretar ese texto para producir el siguiente intento —
   introduce una traducción con pérdida en cada iteración.

## Qué cambiar
Todo checker (ERC, DRC, cobertura, DFM) devuelve una lista de objetos que
cumplen `evaluation/schemas/finding.schema.json`, nunca prosa suelta.

- La **severidad** la fija la regla (`schematic-rules/rules/*.yaml`), no el
  LLM revisor en tiempo de ejecución. Dos instancias de la misma regla
  (`rule_id` igual) tienen siempre la misma severidad.
- El **mensaje** se genera por plantilla desde la regla + los `refs`
  concretos — el LLM revisor puede seguir redactando el mensaje final para
  que sea legible, pero no decide severidad ni el fix.
- El **fix** es un `suggested_fix.action` estructurado
  (`add_component`, `rewire_pin`, ...) que el agente generador puede aplicar
  directamente sin pasar por lenguaje natural.

## Cobertura de pines como finding, no como bloque aparte
`pin_coverage` dejar de ser un bloque separado del reporte y se emite como
findings `domain: "coverage"`:

- Cobertura `< 1.0` en un componente con pinout de referencia conocido →
  `severity: warning`, `rule_id: "coverage.incomplete_pinout"`.
- Un componente en `unmatched` (sin pinout de referencia, p.ej. un
  conector genérico como `Header_8`) → **no es un problema**, es esperado.
  `rule_id: "coverage.no_reference_pinout"`, `severity: "info"`, y el
  agente/orquestador lo trata como resuelto automáticamente, sin pedir
  intervención. (Ver caso real: `J1` queda siempre en `unmatched` en ambas
  corridas de PulseLab porque es un header de expansión genérico — es
  correcto que así sea.)

## Ejemplo: antes / después

**Antes** (`semantic_review.issues[3]`, tal cual lo produce el sistema hoy):
```json
{
  "msg": "El pin I2C_SDA del SSD1306 está conectado a un resistor de 4.7kΩ desde 3.3V a GND, pero no hay un condensador de desacople entre VCC y GND cercano al SSD1306...",
  "severity": "warning",
  "proposal": "Añadir un condensador de 100nF entre el pin VCC (pin 2) del SSD1306 y GND (pin 1)..."
}
```

**Después** (finding conforme al esquema):
```json
{
  "rule_id": "ee_fundamentals.decoupling.per_ic_100nf",
  "domain": "ee_fundamentals",
  "severity": "warning",
  "refs": [{"component_ref": "U2", "pin": "2", "net": "3.3V"}],
  "message": "U2 (SSD1306) no tiene condensador de desacoplo de 100nF entre su pin de alimentación y GND.",
  "suggested_fix": {
    "action": "add_component",
    "details": {"etype": "C", "value": 1e-7, "n1": "3.3V", "n2": "GND", "near_ref": "U2"}
  },
  "confidence": 1.0
}
```

La severidad `warning` ahora viene de la regla `ee_fundamentals.decoupling
.per_ic_100nf` (ver skill correspondiente) aplicada uniformemente a los 4
ICs con alimentación del diseño — no de una decisión puntual del revisor
para cada uno.

## Nota sobre el caso "SCL con resistor 4.7k a GND"
Ese hallazgo (`semantic_review.issues[4]`) es un caso distinto y más
importante: no es falta de desacoplo, es un **error real de topología**
heredado probablemente de una regla de pull-up de I2C mal aplicada (ver
`schematic-rules/skills/i2c-bus-pullups.md`). Un buen esquema de findings
debe permitir distinguir claramente "falta un componente estándar"
(severidad uniforme, fix mecánico) de "hay una conexión topológicamente
incorrecta" (requiere que el checker entienda el rol semántico del pin,
no solo su presencia).
