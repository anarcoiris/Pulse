---
component: component-library
name: LED Component Modeling Gap & Role Mapping
---

# LED Component Modeling Gap & Role Mapping

## Contexto del Problema

En versiones tempranas de modelos de netlist generativo (`pulselab_zero.json`), los LEDs carecían de un tipo de entidad dedicado y fueron modelados ocasionalmente como `etype: S` (switch) o dentro de `etype: D` genérico.

Esto provocó dos discrepancias:
1. **Falta de Semántica de Polaridad:** Un switch o resistor es bidireccional, mientras que un LED es un diodo emisor de luz polarizado unidireccionalmente (**Ánodo** $\rightarrow$ **Cátodo**).
2. **Omisión de Resistencia Limitadora de Corriente:** Al modelar un LED como switch conectado entre GPIO y GND, el generador a veces omitía la resistencia serie limitadora ($R_{limit}$), provocando sobrecorriente directa sobre el pin del microcontrolador ($I > I_{max\_gpio} \approx 40\,\text{mA}$).

## Especificación del Modelo Intermedio

En el modelo intermedio neutral (`_corpus-meta/ARCHITECTURE.md`), los LEDs se formalizan como:

```yaml
component:
  ref: "D1"
  kind: "led"
  part_value: "Red"           # Color o código de parte (p.ej. "Green 0805")
  pins:
    - number: "1"
      role: "led_anode"        # Conectado hacia la señal GPIO o VCC
      net: "LED_STAT_A"
    - number: "2"
      role: "led_cathode"      # Conectado hacia GND a través de R_limit
      net: "LED_STAT_K"
```

## Regla de Protección de Corriente

Todo LED debe poseer una resistencia limitadora de corriente en serie con un valor calculado según el voltaje directo ($V_F$) y la corriente deseada ($I_F \approx 2-10\,\text{mA}$):

$$R_{limit} = \frac{V_{CC} - V_F}{I_F} \approx \frac{3.3\,\text{V} - 2.0\,\text{V}}{5\,\text{mA}} \approx 260\,\Omega \quad (\text{Valor estándar: } 330\,\Omega - 1\,\text{k}\Omega)$$

## Heurística de Adaptación para Netlists Propios

Cuando el adaptador `tool-adapter/netlist-propio` procesa un componente con:
- `label` que comienza por `D`, `LED`, `D_`
- `etype` igual a `"LED"`, `"D"` o con valor textual de color (`"Red"`, `"Green"`, `"Blue"`, `"Amber"`, `"WS2812B"`)

El adaptador traduce automáticamente la entidad a `kind: led` y asigna `led_anode` y `led_cathode` a sus respectivos terminales.
