---
rule_id: schematic.i2c_bus.pullup_to_power_rail
domain: schematic
name: I2C Bus Pull-Up Resistors & Open-Drain Termination
---

# I2C Bus Pull-Up Resistors & Open-Drain Termination

## Contexto & Principio Eléctrico

El bus I2C (Inter-Integrated Circuit) utiliza una topología bidireccional de **colector abierto / drenador abierto** (open-drain) en ambas líneas:
- **SDA** (Serial Data)
- **SCL** (Serial Clock)

Los transistores internos de los dispositivos I2C solo pueden conducir hacia masa (nivel lógico `0` / GND). Para alcanzar el nivel lógico alto (`1` / VCC), el bus depende exclusivamente de **resistencias de pull-up externas** conectadas entre las líneas de señal y el rail de alimentación positivo (`3.3V`).

```
          +3.3V (Power Rail)
           |             |
         [R1]          [R2]      (2.2kΩ - 4.7kΩ)
           |             |
SDA ───────+─────────────+─────── SDA Device Pin (open-drain)
                         |
SCL ─────────────────────+─────── SCL Device Pin (open-drain)
```

## Errores Comunes Detectados

### 1. Pull-Down en lugar de Pull-Up (Polaridad Invertida)
- **Causa:** El generador confunde una resistencia de terminación con un pull-down a GND (el mismo bug observado históricamente en `EN`).
- **Consecuencia:** La línea queda permanentemente fijada en nivel bajo. Ningún dispositivo puede transmitir y el bus I2C queda bloqueado (I2C Bus Lockup).
- **Severidad:** `critical`.

### 2. Ausencia Total de Resistencias Pull-Up
- **Causa:** Asumir erróneamente que las resistencias de pull-up internas del MCU son suficientes para operar periféricos a 100 kHz / 400 kHz con capacitancia de traza.
- **Consecuencia:** Tiempos de subida ($t_r$) excesivamente lentos, bordes redondeados y corrupción de tramas I2C.
- **Severidad:** `critical`.

## Dimensionamiento de Resistencias

El valor óptimo depende de la velocidad del bus y la capacitancia parásita total del bus ($C_b$):

$$R_{min} = \frac{V_{DD} - V_{OL}}{I_{OL}} \approx \frac{3.3\,\text{V} - 0.4\,\text{V}}{3\,\text{mA}} \approx 966\,\Omega$$

$$R_{max} = \frac{t_r}{0.8473 \times C_b}$$

- **Valores Estándar Recomendados:**
  - Modo Estándar (100 kHz, $C_b \le 400\,\text{pF}$): $4.7\,\text{k}\Omega$ a $10\,\text{k}\Omega$.
  - Modo Rápido (400 kHz, $C_b \le 200\,\text{pF}$): $2.2\,\text{k}\Omega$ a $4.7\,\text{k}\Omega$.
  - Modo Rápido Plus (1 MHz): $1\,\text{k}\Omega$ a $2.2\,\text{k}\Omega$.

## Ejemplo de Fix Estructurado

```yaml
action: add_component
details:
  etype: R
  value: "4.7k"
  n1: "I2C_SDA"
  n2: "3.3V"
```
