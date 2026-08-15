---
rule_id: ee_fundamentals.decoupling.per_ic_100nf
domain: ee_fundamentals
applies_to: [any IC/module with a power pin]
severity_default: warning
severity_escalation: critical when the IC is the MCU (clock/reset sensitive)
---

# Skill: condensador de desacoplo por IC (100nF)

## Por qué existe esta skill
En `pulselab_zero.json` el mismo tipo de problema —falta un condensador de
100nF entre el pin de alimentación de un IC y GND, cerca de ese IC—
aparece **7 veces** en `semantic_review.issues`: una para el ESP32-S3
(marcada `critical`), y una para cada pin de alimentación referenciado de
SSD1306, PN532 (x3, una por cada pin SPI) y CC1101 (x3). Son la misma
regla física aplicada a 4 componentes distintos, pero el sistema actual
las genera como 7 hallazgos independientes en prosa, con severidad
inconsistente entre ellos. Esto debe colapsar en **una regla, evaluada una
vez por componente con pin de alimentación**, no una vez por pin de señal
que comparte ese componente.

## La regla física
Cualquier IC (MCU, transceptor, sensor, driver) necesita un condensador
cerámico de desacoplo (típicamente 100nF, X7R o mejor) entre su pin de
alimentación y GND, **físicamente próximo** al IC (esto es también una
regla de PCB — ver `pcb-rules/skills/decoupling-placement.md`, pendiente).
Sin él, las conmutaciones internas del chip provocan caídas de tensión
transitorias en la red de alimentación que se acoplan como ruido a otros
pines del mismo IC, incluidas líneas de comunicación (I2C, SPI).

Para MCUs con múltiples dominios de reloj o RF (como el ESP32-S3), suele
añadirse también un condensador de mayor capacidad (1-10 µF) como reserva
de carga de baja frecuencia, además del de 100nF de alta frecuencia — el
diseño de PulseLab ya incluye `C2 = 10µF` junto al `C1 = 100nF` del
ESP32-S3, lo cual es correcto y no debe marcarse como problema.

## Por qué NO es un problema del bus I2C/SPI
El sistema actual redacta el hallazgo como si fuera un problema de la
línea de datos ("SPI_MOSI del CC1101 está conectado a 3.3V... no hay
desacoplo") cuando en realidad **la señal en sí no necesita desacoplo** —
lo que falta es desacoplo en el pin de *alimentación* de ese mismo
componente. Redactarlo por pin de señal en vez de por componente es lo que
produce las 6 repeticiones casi idénticas en `review.md`. La regla
correcta se evalúa **una vez por componente**, no una vez por cada señal
que ese componente expone.

## Patrón correcto (modelo intermedio)
```yaml
- kind: capacitor
  part_value: 1e-7          # 100nF
  pins:
    - {net: "<VCC del IC>", role: power_in}
    - {net: "GND",          role: ground}
  ref: C_<ref del IC>
```
Un condensador por componente con pin de alimentación es el mínimo. No
hace falta (ni es correcto) generar un hallazgo por cada pin de señal del
mismo componente.

## Check verificable
Ver `ee-fundamentals/rules/decoupling_per_ic.yaml`. Resumen: para todo
componente con al menos un pin `role: power_in`, debe existir un
`capacitor` cuyo par de pines sea exactamente (esa red de alimentación,
una red `role: ground`). El hallazgo se emite **una vez por componente**,
con `refs` apuntando al componente, no a cada pin de señal.
