# Investigación: Cobertura de pines físicos en la síntesis de circuitos

> Parte de [Calibration Forge](./index.md) · Referenciado desde [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §4.1
> Relacionado con el milestone pendiente: "Refactorizar el modelo de pines para soporte MCU completo" (`index.md`)

## Problema observado

El sistema conoce el pinout físico completo de los MCUs soportados (ESP32-WROOM-32: 39 pines; ESP32-S3: 48 pines — `knowledge/pinouts_library.json`), pero los circuitos generados por el LLM solo representan un subconjunto muy pequeño de esos pines, incluso cuando el resto existe físicamente en el componente y podría ser relevante (headers de expansión, pines de programación, pines libres a documentar como NC).

## Evidencia

1. **Truncamiento explícito en el contexto del prompt.** `knowledge/circuit_synthesizer.py::_compact_pinout()`:

```121:133:knowledge/circuit_synthesizer.py
def _compact_pinout(self, entry: dict) -> dict:
    """Pinout snippet without full 40+ GPIO tables."""
    out: dict = {}
    for field in ("symbol", "footprint", "description"):
        if entry.get(field):
            out[field] = entry[field]
    for field in ("uart_programming", "usb", "i2c_default"):
        if entry.get(field):
            out[field] = entry[field]
    pins = entry.get("pins") or {}
    if pins and len(pins) <= self._max_pinout_pins:
        out["pins"] = pins
    return out
```

Con `max_pinout_pins = 14` (`Pulse_cfg.json → llm.agents.circuit_synthesizer.max_pinout_pins`), **cualquier MCU con más de 14 pines pierde la tabla de pines por completo** del contexto — no se recorta a los 14 más relevantes, se omite entera. Para ESP32-WROOM-32 (39 pines) y ESP32-S3 (48 pines) esto significa que el modelo nunca ve el pinout completo en el prompt.

2. **El único ejemplo estático embebido ancla el patrón de salida.** El mismo archivo, en el system prompt base:

```42:52:knowledge/circuit_synthesizer.py
Usuario: "Un ESP32 conectado a una pantalla I2C y a un resistor pull-up a 3.3V"
Respuesta:
{
  "circuit": [
    {"etype": "V", "value": 3.3, "n1": "3.3V", "n2": "GND", "label": "V1"},
    {"etype": "MCU", "value": "ESP32-S3", "symbol": "RF_Module:ESP32-WROOM-32", "footprint": "RF_Module:ESP32-WROOM-32", "pins": {"2": "3.3V", "1": "GND", "33": "I2C_SDA", "36": "I2C_SCL"}, "label": "U1"},
    ...
```

Este ejemplo (4 pines de 39) es el único patrón de referencia que el modelo ve siempre, en cada llamada, independientemente del RAG. Es una prioridad más fuerte que cualquier ejemplo recuperado dinámicamente.

3. **Confirmación empírica con datos de hoy.** La corrida de validación `validate_20260705_192012_126038a8` (`knowledge/data/validation_complex/runs/20260705_192012_.../esp32_sensors.json`) generó:

```json
{
  "etype": "MCU",
  "value": "ESP32-S3",
  "pins": { "2": "3.3V", "1": "GND", "33": "I2C_SDA", "36": "I2C_SCL" }
}
```

4 de 39 pines. Coincide exactamente con el patrón del ejemplo estático del prompt (mismos números de pin, incluso). Ni EN (pull-up obligatorio según las propias reglas del prompt), ni IO0/BOOT, ni ningún GPIO de expansión aparecen — aunque las "REGLAS UART/USB OBLIGATORIAS" del mismo prompt exigen explícitamente el pull-up de EN.

4. **No es un problema de exportación KiCad.** `bridge/schematic_generator.py` solo dibuja etiquetas de red para los pines presentes en el dict `pins` (línea 131: `net_name = c.pins.get(p_id, "")`); el símbolo de KiCad (`RF_Module:ESP32-WROOM-32`) ya trae geométricamente todos los pads del componente real. Es decir: **la placa se fabricaría con el footprint completo, pero el diseño lógico/documentación de qué hace cada pin restante se pierde.** El problema es de fidelidad de diseño e intención, no de fabricabilidad.

## Por qué importa

- Un ingeniero que reciba este netlist no sabe si EN/IO0/GPIOs libres fueron **considerados y descartados a propósito**, o simplemente **olvidados**. No hay forma de distinguir "no conectado intencionalmente" de "pin ignorado por el generador".
- Cualquier feature futura de "exponer GPIOs libres a un header de expansión" (como en `pulselab_zero`, que sí lo pide explícitamente en su prompt) depende de que el modelo tenga visibilidad de qué pines quedan realmente libres.
- El cap de contexto (14 pines) fue razonable cuando el presupuesto de prompt era estrecho; con el backend `primary` actual (98,304 tokens de contexto, `prompt_max_chars: 48000`) el costo de incluir una tabla de 48 entradas es marginal.

## Líneas de investigación / próximos pasos propuestos

1. **Eliminar el cap binario "todo o nada" de `_compact_pinout()`.** Alternativas:
   - Incluir siempre el pinout completo del/los MCU(s) que hagan match fuerte con la descripción (score alto en `_match_pinouts`), y solo aplicar compactación a matches débiles/secundarios.
   - O bien: incluir el pinout completo pero comprimido como rango (`"4-24": "GPIOxx (ver tabla completa)"` solo para los truly irrelevantes, mientras que pines con roles conocidos — EN, IO0, UART, I2C, SPI — siempre se listan explícitamente).

2. **Añadir un campo de esquema `"unconnected_pins"` o convención `"NC"`** en las reglas de salida (`ATOMIC_JSON_SUFFIX` en `knowledge/llm_prompt_format.py` y las reglas base de `circuit_synthesizer.py`) para que el modelo pueda declarar explícitamente "estos pines existen y quedan libres a propósito" sin necesidad de imaginar redes ficticias para ellos.

3. **Reemplazar (o complementar) el ejemplo estático embebido** por un ejemplo generado dinámicamente a partir de un caso "golden" real con cobertura completa de pines (ej. el preset `esp32_usb_devkit`, que sí mapea EN, IO0, GPIO breakout headers — ver `presets/esp32_usb_devkit.py`). Esto evita que el único ancla de estilo en el prompt sea, por accidente, el ejemplo menos completo del sistema.

4. **Nueva métrica de calibración: "Pin Coverage Fidelity".** Añadir a `docs/calibration_forge/evaluation_metrics.md` una métrica que compare, para cada componente `MCU`/`IC` generado, `len(pins) / len(pinouts_library[value]["pins"])`, y trackearla en `knowledge/validate_complex_apps.py` junto al resto del resumen (`etypes`). Esto permite ver la evolución de este problema en cada corrida de validación sin inspección manual.

5. **Post-procesado determinista (no-LLM) opcional**: tras recibir el JSON del modelo, para MCUs conocidos en `pinouts_library.json`, rellenar automáticamente los pines no mencionados con `"NC"` (código, no LLM) antes de pasar a `schematic_generator.py`. Esto resuelve el síntoma inmediato (visibilidad completa en el esquemático) mientras se itera sobre el fondo del problema (fidelidad del LLM).

## Alcance de la investigación

Este hallazgo debería expandirse revisando también `presets/esp32s2_usb_devkit.py` y `presets/mcu_uart.py` para confirmar si el mismo patrón de "pines truncados" ocurre en presets escritos a mano (no generados por LLM) — si es así, el problema no es solo del prompt sino también de convención de diseño en todo el proyecto.
