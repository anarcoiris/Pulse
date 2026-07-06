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

1. ✅ **Eliminar el cap binario "todo o nada" de `_compact_pinout()`.** *(Session 3, 06-jul-2026)* Implementado: el match de mayor score en `_match_pinouts()` recibe siempre la tabla completa (`_compact_pinout(..., full=True)`); matches secundarios siguen compactados por `max_pinout_pins` (14). Verificado en runtime: `ESP32-WROOM-32` → 39/39 pines inyectados en `PINOUTS RELEVANTES`.

2. ✅ **Añadir un campo de esquema `"unconnected_pins"` o convención `"NC"`** *(Session 3)* en `ATOMIC_JSON_SUFFIX` (`knowledge/llm_prompt_format.py`), reglas base de `circuit_synthesizer.py`, y post-procesado `_normalize_unconnected_pins()` (cada pin NC se renombra a `NC_<label>_<pin>` para evitar cortos eléctricos en `schematic_generator.py`).

3. ✅ **Reemplazar (o complementar) el ejemplo estático embebido** *(Session 3)* por `_build_dynamic_pinout_example()` desde `presets/esp32_usb_devkit.py` (39 pines del MCU con NC explícitos); el ejemplo mínimo de 4 pines se conserva como referencia de esquema JSON, con nota de que no debe usarse como modelo de cobertura.

4. ✅ **Nueva métrica de calibración: "Pin Coverage Fidelity".** *(Session 3)* Implementada en `knowledge/validate_complex_apps.py::_pin_coverage()`; definición formal en [`evaluation_metrics.md`](./evaluation_metrics.md) §4.

5. **Post-procesado determinista (no-LLM) opcional**: tras recibir el JSON del modelo, para MCUs conocidos en `pinouts_library.json`, rellenar automáticamente los pines no mencionados con `"NC"` (código, no LLM) antes de pasar a `schematic_generator.py`. *No implementado en Session 3* — la convención NC + normalización ya cubre el caso cuando el LLM coopera (confirmado: 100% cobertura en `esp32_sensors` post-fix, ver §Resultado); esta red de seguridad ya no es prioritaria salvo que la corrida completa de 5 casos en Sesión 4b muestre regresiones puntuales.

## Alcance de la investigación

Este hallazgo debería expandirse revisando también `presets/esp32s2_usb_devkit.py` y `presets/mcu_uart.py` para confirmar si el mismo patrón de "pines truncados" ocurre en presets escritos a mano (no generados por LLM) — si es así, el problema no es solo del prompt sino también de convención de diseño en todo el proyecto.

**Resultado (revisión Session 3, 06-jul-2026):** confirmado — el truncamiento no es exclusivo del prompt LLM:

| Preset / componente | Pines en `pins` | Total en `pinouts_library.json` | Cobertura |
|---|---:|---:|---:|
| `esp32_usb_devkit` → `U3` ESP32-WROOM-32 | 8 | 39 | **20.5%** |
| `esp32s2_usb_devkit` → `U2` ESP32-S2 | 9 | 47 | **19.1%** |
| `mcu_uart` → `U2` ESP8266_Node | 6 | *(sin entrada en librería)* | **n/a** |

En `esp32_usb_devkit`, GPIOs adicionales aparecen en headers separados (`GPIO_HDR_L`/`GPIO_HDR_R`), no en el mapa de pines del MCU — convención de diseño distinta a la que pide el sintetizador. `mcu_uart` usa `ESP8266_Node`, que **no existe** en `pinouts_library.json` (problema de datos faltantes, no solo de truncamiento).

## §Resultado (sesión de fix, 06-jul-2026)

### Cambios de código

| Área | Archivo | Qué cambió |
|---|---|---|
| Inyección de pinout | `knowledge/circuit_synthesizer.py` | `_match_pinouts()` devuelve `list[tuple[str, dict]]` ordenada; `_compact_pinout(entry, full=…)`; pinout completo solo para el match primario |
| Convención NC | `knowledge/circuit_synthesizer.py`, `knowledge/llm_prompt_format.py` | Reglas `FIDELIDAD DE PINES`, `unconnected_pins`, `ATOMIC_JSON_SUFFIX`; `_normalize_unconnected_pins()` |
| Ejemplo dinámico | `knowledge/circuit_synthesizer.py` | `_build_dynamic_pinout_example()` desde `presets/esp32_usb_devkit.py` |
| Métrica | `knowledge/validate_complex_apps.py` | `_pin_coverage()` + salida en consola, JSON por caso y `run_manifest.json` |
| Docs | `evaluation_metrics.md` | §4 Pin Coverage Fidelity |

### Verificación en runtime (06-jul-2026)

- `py -3 scratch/session3_sanity.py`: `base_system_prompt` 6534 chars; ejemplo dinámico presente; match primario `ESP32-WROOM-32` → **39 pines** en contexto; secundario `ESP32-S3` → 0 pines (compactado, >14).
- `pytest tests/test_forge.py tests/test_rag_retrieval.py`: **14/14 passed**.
- **Re-correr validación LLM:** intentado `py -3 -m knowledge.validate_complex_apps --case esp32_sensors` — **bloqueado en la sesión original**: backends `primary` (Ollama `:11431`) y `atomic` (llama-server `:11439`) reportaban `available: false`. **Actualización 06-jul-2026 13:09-13:16 UTC:** re-corrido con `primary` activo (`atomic` seguía caído) — ver resultado abajo, ya no está pendiente.

### Pin Coverage Fidelity — antes / después

| Fuente | Caso / parte | Pines generados | Total físico | Cobertura |
|---|---|---:|---:|---:|
| **Baseline** (validación 2026-07-05 19:20 UTC, `esp32_sensors`) | MCU `ESP32-S3` *(valor en JSON; pinout matcheado como WROOM-32 en librería)* | 4 | 39 | **10.3%** |
| **Post-fix LLM** (run `20260706_130942_b1a9364b`, backend `primary`, `atomic` no disponible) | `esp32_sensors` → `U1` ESP32-WROOM-32 | 39 | 39 | **100%** |
| **Post-fix LLM** (mismo run) | `esp32_sensors` → `OLED` SSD1306 | 4 | 4 | **100%** |
| **Post-fix LLM** (mismo run) | `esp32_sensors` → `SENSOR` BME280 | 4 | 4 | **100%** |
| **Post-fix LLM** (mismo run) | promedio del caso (`average_coverage`) | — | — | **100%** |
| **Presets manuales** (no LLM) | ver tabla en §Alcance arriba | — | — | 19–21% en MCUs |

**Resultado confirmado:** la cobertura del MCU principal subió de **10.3% → 100%** en `esp32_sensors` con el backend `primary` real (no solo en el sanity check de `scratch/session3_sanity.py`). Los 33 pines del ESP32 no usados en el diseño aparecen correctamente normalizados como `NC_U1_<n>` (`_normalize_unconnected_pins()` funcionando fin-a-fin). Detalle completo en `knowledge/data/validation_complex/runs/20260706_130942_validate_20260706_130942_b1a9364b/esp32_sensors.json`.

**Alcance de esta corrida:** un solo caso (`esp32_sensors`), un solo backend (`primary`; `atomic` seguía sin estar disponible). Los otros 4 casos (`esp32_steppers`, `esp32_rf_nfc`, `esp32_usb_devkit`, `pulselab_zero`) no se han re-corrido post-fix todavía — quedan cubiertos por el baseline (a) del experimento A/B de Sesión 4b (`prompt_vs_rag_balance.md`), que de todos modos necesita correr los 5 casos.

```powershell
$env:PYTHONIOENCODING='utf-8'
py -3 -m knowledge.validate_complex_apps --case esp32_sensors
# o los 5 casos sin --case
```

### Nota para Session 4 (`prompt_vs_rag_balance.md`)

Al unificar `_match_pinouts()` en `ElectronicsKnowledgeBase`, **preservar**:

1. **Tipo de retorno:** `list[tuple[str, dict]]` ordenada por score (ya no `dict`).
2. **Lógica full/compact:** solo el match de mayor confianza debe inyectar la tabla de pines completa; matches secundarios pueden seguir acotados por `max_pinout_pins`.
3. **Normalización NC:** `_normalize_unconnected_pins()` debe seguir ejecutándose tras parsear el JSON del LLM.

Sin esto, la fusión con RAG podría reintroducir el truncamiento "todo o nada" que esta sesión eliminó.

### Próximo paso: fuente de pinouts (KiCad, no curación manual)

Session 3 arregló **cómo** se inyectan pinouts al prompt; la **fuente** sigue siendo `pinouts_library.json` (~12 partes curadas a mano). Eso explica casos como `ESP8266_Node` → métrica `n/a` en presets y validación.

**Dirección acordada (06-jul-2026):** construir la base de conocimiento desde las librerías KiCad (`.kicad_sym`), que ya contienen miles de símbolos con nombres de pines, tipos eléctricos y footprints. Ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) para:

- Arquitectura en capas (KiCad pinouts + `components.json` params + `design_experience` reglas)
- Pipeline propuesto: `kicad_symbol_parser.py` → `build_symbol_index` → RAG `chunk_type="pinout"`
- Integración con Session 4 (`prompt_vs_rag_balance.md` propuesta #2)
- `pinouts_library.json` como overrides temporales hasta que el índice KiCad cubra cada parte

**✅ Implementado en Sesión 4a (06-jul-2026)** — ver [`kicad_symbol_kb.md` §Resultado](./kicad_symbol_kb.md#resultado-sesión-4a-06-jul-2026) para el detalle completo. Resumen:

- `knowledge/kicad_symbol_parser.py` + `python -m knowledge.build_symbol_index` indexaron **5320 símbolos reales** desde 29 librerías de la instalación local de KiCad 10.0 (`knowledge/data/symbols_index.json`), ingestados en `ElectronicsKnowledgeBase` como **5326 chunks `chunk_type="pinout"`** (5320 KiCad + 10 overrides curados de `pinouts_library.json`, que siguen ganando cuando coinciden por nombre).
- `_match_pinouts()` migró a `kb.query(..., chunk_type="pinout")`, preservando exactamente la semántica de esta sección (retorno ordenado, full/compact, `_normalize_unconnected_pins()`). Se detectó y corrigió en la misma sesión una regresión del ranking puramente semántico contra partes nombradas literalmente (ver detalle en `kicad_symbol_kb.md`).
- Regresión confirmada sin cambios: `esp32_sensors` → `ESP32-WROOM-32` **39/39 (100%)**, `SSD1306` **4/4 (100%)**, `BME280` **4/4 (100%)**, `avg=100%` — mismo resultado que el baseline de esta sección, con `pytest tests/` en 79/79.
- `_pin_coverage()` ahora también resuelve contra `symbols_index.json` (match exacto por nombre normalizado) cuando `pinouts_library.json` no cubre la parte — verificado con `AMS1117-3.3` y `Pololu_Breakout_A4988`. `ESP8266_Node` (el caso `n/a` original de esta sección) queda como pendiente explícito: `RF_Module.kicad_sym` sí trae `ESP-12F`/`ESP-12E`/`ESP-07`, pero ninguno coincide por nombre exacto con `ESP8266_Node` — requiere un override o renombrar el preset, no resuelto en 4a.
