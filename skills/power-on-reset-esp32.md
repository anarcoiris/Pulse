---
rule_id: schematic.power_on_reset.en_pullup
domain: schematic
applies_to: [ESP32-S3, ESP32, ESP8266, ESP32-C3, ESP32-C6]
severity_default: critical
---

# Skill: pin EN (chip enable) — pull-up, no pull-down

## Por qué existe esta skill
Observado en **dos corridas independientes** de `validate_*` sobre el
mismo `test_case` (PulseLab Zero): el generador conecta el pin `EN` del
ESP32-S3 a GND mediante una resistencia de 10 kΩ. El revisor lo marca
`CRITICAL` las dos veces, con la misma explicación, casi palabra por
palabra. Eso es la señal más clara posible de que falta conocimiento en
el generador, no en el revisor — el revisor ya "sabe" la regla, el
generador no.

## La regla física
`EN` (a veces llamado `CHIP_PU`, `CHIP_EN` o `RESET` según el módulo) es
la señal que habilita el regulador interno y saca al chip de reset. Su
comportamiento correcto:

- **Activo en alto**: el chip arranca cuando `EN` está en `3.3V`.
- Debe llevar una resistencia de **pull-up a 3.3V** (típicamente 10 kΩ),
  no a GND. Un pull-down mantiene el chip permanentemente en reset —
  el dispositivo no arrancará nunca, ni con firmware perfecto.
- Es habitual (no obligatorio) añadir un condensador de 100 nF entre `EN`
  y GND para un power-on-reset más suave y evitar rearranques por ruido
  en la alimentación — pero eso es un *añadido*, nunca un sustituto del
  pull-up.

## Patrón correcto (modelo intermedio)
```yaml
- kind: resistor
  part_value: 10000.0
  pins:
    - {net: "3.3V", role: power_in}
    - {net: "EN",   role: reset_enable}
  ref: R_EN
# opcional, no sustituye al pull-up:
- kind: capacitor
  part_value: 1e-7
  pins:
    - {net: "EN",  role: reset_enable}
    - {net: "GND", role: ground}
  ref: C_EN
```

## Patrón incorrecto (el que produjo el generador, dos veces)
```yaml
- kind: resistor
  part_value: 10000.0
  pins:
    - {net: "3.3V", role: power_in}   # <- ambos extremos "parecen" correctos
    - {net: "EN",   role: reset_enable}
  ref: R_EN
```
En el JSON crudo esto se ve casi idéntico al caso correcto:
`{"n1": "3.3V", "n2": "EN"}` — la diferencia real que importa NO está en
`n1`/`n2` (ver nota en `ARCHITECTURE.md` sobre por qué `n1`/`n2` no tiene
polaridad fija), sino en si el otro extremo de la resistencia realmente
llega a 3.3V o si, por un error de generación, el nodo `EN` termina
uniéndose a `GND` en vez de a `3.3V`. **El check no debe fiarse del orden
de n1/n2** — debe verificar el nombre de red real en cada extremo.

## Check verificable
Ver `schematic-rules/rules/power_on_reset.yaml`. Resumen: para todo pin
con `role: reset_enable`, debe existir exactamente un componente
`resistor` que una ese pin con una red `role: power_rail`. Si en cambio se
une con una red `role: ground`, es `critical` inmediato — no hay caso en
el que EN a GND directo (vía resistencia o no) sea válido para arranque
normal.

## Caso relacionado, no confundir
`GPIO0` (BOOT/strap pin) sí se conecta a GND legítimamente — pero solo
para forzar modo de descarga de firmware, no como parte del circuito de
power-on. `review.md` marca esto como `WARNING` informativo, correctamente
distinto del caso de `EN`. Ver
`schematic-rules/skills/boot-strap-pins.md` (pendiente, ver roadmap).
