# Métricas de Validación y Evaluación (Forge Evaluator)

## Objetivo
Cuantificar qué tan cerca está nuestra generación automática de un diseño de referencia profesional.

## Niveles de Evaluación

### 1. Integridad Lógica (Netlist Match)
- **Topología:** Comparar si todos los terminales de los componentes están conectados a los mismos nodos.
- **Detección de Cortos/Abiertos:** El sistema debe alertar si nuestra versión "abre" un circuito que en la referencia está cerrado.

### 2. Estética y Colocación (Geometric Match)
- **Error de Centroides:** Distancia euclidiana entre la posición del componente original y el generado.
- **Error de Orientación:** Delta de rotación (0, 90, 180, 270).

### 3. Ruteo (Routing Fidelity)
- **Longitud de Pistas:** Comparación de longitud total de cobre.
- **Topología de Traces:** ¿Pasamos por los mismos puntos de control que el diseñador humano?

### 4. Cobertura de Pines Físicos (Pin Coverage Fidelity)

> Añadida en Session 3 (06-jul-2026) — ver [`pin_model_coverage.md`](./pin_model_coverage.md) para
> el contexto completo del problema que motivó esta métrica.

**Objetivo:** detectar cuándo el sintetizador de circuitos (`knowledge/circuit_synthesizer.py`)
representa solo una fracción de los pines físicos reales de un IC/MCU, en vez de darlos por
"considerados" (conectados o marcados explícitamente como no usados).

**Definición formal**, por cada componente generado con `etype` en `{"IC", "MCU"}` cuyo `value`
tiene una entrada en la base de pinouts de referencia (`knowledge/pinouts_library.json` primero,
con fallback a `knowledge/data/symbols_index.json` desde KiCad desde Sesión 4a — ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) §Resultado):

```
coverage(component) = len(component["pins"]) / len(pinouts_library[component.value]["pins"])
```

- Un pin cuenta para la cobertura tanto si está conectado a una red real como si está
  declarado explícitamente como no conectado (convención `"NC"` / `"unconnected_pins"`,
  normalizada por `circuit_synthesizer._normalize_unconnected_pins()` a un nombre de red
  único `NC_<label>_<pin>` antes de contarse). Solo un pin **ausente** del diccionario
  `pins` deja de contar — ese es exactamente el modo de fallo ("omitido en silencio") que
  esta métrica existe para detectar.
- **Cobertura promedio de una corrida:** promedio simple de `coverage(component)` sobre
  todos los componentes IC/MCU con pinout de referencia conocido, en un caso de prueba.
- **Componentes "unmatched":** si `component.value` (o `lib_id` KiCad) no existe en ninguna de
  las dos bases de pinouts de referencia (`pinouts_library.json` ni `symbols_index.json` desde
  Sesión 4a — ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) §Resultado)
  (p. ej. un preset escrito a mano que usa un nombre de parte que nunca se agregó a ninguna de
  las dos, como `"ESP8266_Node"` en `presets/mcu_uart.py` — pendiente explícito, ver
  `kicad_symbol_kb.md` §Limitaciones), el componente se reporta por
  separado como *sin pinout de referencia* — no se cuenta como 0% ni se omite en silencio,
  porque no hay base de comparación válida.
- Un componente sin ningún pin (`pins == {}`) da `coverage = 0.0` explícitamente (no `None`),
  siempre que su parte sí tenga pinout de referencia — 0% cobertura es una señal válida.

**Implementación:** `knowledge/validate_complex_apps.py::_pin_coverage()`, invocada por
cada caso de prueba y persistida tanto en el JSON de salida por caso
(`knowledge/data/validation_complex/runs/<run>/<case>.json` → clave `"pin_coverage"`) como
en `run_manifest.json` (por entrada de resultado), para poder comparar corridas en el tiempo
sin inspección manual.

**Baseline y resultado de Session 3:** ver la sección "§Resultado" de
[`pin_model_coverage.md`](./pin_model_coverage.md) para los números antes/después medidos.

### 5. Revisión Semántica (Semantic Review Issue Count)

> Añadida en Session 4b (06-jul-2026) — señal primaria del experimento A/B en
> [`prompt_vs_rag_balance.md`](./prompt_vs_rag_balance.md).

**Objetivo:** cuantificar cuántos problemas de diseño detecta `knowledge/semantic_reviewer.py`
sobre el circuito generado, independientemente de si el generador usó reglas fijas o RAG
enriquecido. El revisor mantiene su propio `_SYSTEM_PROMPT` con las 7 reglas AI DRC en
ambas variantes — la comparación A/B mide calidad de *generación*, no de *revisión*.

**Definición formal**, por cada caso de prueba en `validate_complex_apps.py`:

- `issue_count`: número total de entradas en `issues[]` devueltas por `SemanticReviewer.review_netlist()`.
- `critical_count`: subconjunto con `severity == "critical"`.
- Si el revisor devuelve `error`, ambos contadores quedan `null` y se persiste el mensaje de error.

**Implementación:** `knowledge/validate_complex_apps.py::_semantic_review_summary()`, invocada
tras cada generación exitosa y persistida en el JSON por caso (`"semantic_review"`) y en
`run_manifest.json`, junto con `"ab_variant"` (`"a"` | `"b"`) para trazabilidad del experimento.

**Uso en A/B (Session 4b):**

| Variante | Generador | Señal primaria | Señal secundaria |
|---|---|---|---|
| `a` | Reglas OBLIGATORIAS + `rag_top_k=1` | `issue_count` / `critical_count` | Pin Coverage Fidelity |
| `b` | Sin reglas OBLIGATORIAS + `rag_top_k_variant_b` (default 4) | idem | idem |

La decisión de recortar reglas del prompt (tareas 2-3 de Session 4b) requiere comparar estas
métricas entre variantes y juicio humano — no se automatiza aquí.

### 6. Completitud de Generación (Generation Completeness)

> Añadida en Session 4c (06-jul-2026) — ver [`llm_output_pipeline.md`](./llm_output_pipeline.md) y
> [`verification/llm_truncation_review_06072026.md`](./verification/llm_truncation_review_06072026.md) para la evidencia de
> los 4 modos de fallo que motivan esta métrica.

**Objetivo:** distinguir "la generación produjo JSON parseable" de "la generación realmente
completó lo que se le pidió", que **no son lo mismo** — un stub sintácticamente válido pero
semánticamente vacío (ej. un MCU con pinout inyectado pero sin ningún pin declarado) pasaba
como éxito antes de Session 4c. Pin Coverage Fidelity (§4) ya detecta este caso concreto para
componentes IC/MCU, pero es una métrica *posterior* al parseo; Generation Completeness es la
señal de *pipeline* — si la llamada al LLM en sí terminó de forma sana.

**Definición formal**, por cada llamada LLM (síntesis o revisión) registrada vía
`knowledge/llm_client.py::LLMClient.chat()`:

- `done_reason`: normalizado desde `raw.done_reason` (path native) o `choice.finish_reason`
  (path OpenAI) en un único campo top-level del resultado — ver `llm_client.py` y
  `llm_session_log.py::record_llm_exchange()` (persistido también como `content_len` /
  `thinking_len` / `done_reason` a nivel de registro, no solo dentro de `output`).
- **Truncado** (`knowledge/llm_json.py::llm_output_truncated()`): `True` si `done_reason ==
  "length"`, o si `done_reason == "stop"` con `content` y `thinking` ambos vacíos tras strip.
- **Recuperado vía continuación**: si la síntesis truncó con contenido parcial parseable-en-
  progreso, `circuit_synthesizer._continue_truncated_json()` intenta hasta 2 turnos de
  continuación antes de caer al reintento completo con RAG. Un caso se cuenta como
  "generación completa con recuperación" si el resultado final proviene de una continuación
  (`meta.attempt` con prefijo `continue_`), no de un intento limpio.
- **Validación semántica post-parse**: incluso con `done_reason == "stop"` y JSON válido,
  `circuit_synthesizer._validate_injected_pinouts()` puede seguir marcando el intento como
  incompleto si un IC/MCU con pinout completo inyectado no declaró ningún pin
  (`"sin pines pese a pinout completo inyectado"`) o declaró una enumeración sospechosa
  (`"enumeracion sospechosa (N pines vs M esperados)"`, guard contra el modo de fallo
  "1000 pines" de `llm_truncation_review_06072026.md`).

**Valores posibles por intento:** `ok` (stop + contenido válido + validación semántica pasa),
`ok_continued` (recuperado tras 1-2 turnos de continuación), `truncated` (agotó continuación y
el reintento con RAG completo), `stub_rejected` (JSON válido pero rechazado por validación
post-parse). Estos no reemplazan `pin_coverage` ni `semantic_review` — son ortogonales: un
intento puede ser `ok` en Generation Completeness y aun así tener baja Pin Coverage si el
componente no tenía pinout de referencia conocido.

**Implementación:** guards en `knowledge/circuit_synthesizer.py` (`_components_from_llm_result`,
`_continue_truncated_json`, `_validate_injected_pinouts`) y `knowledge/semantic_reviewer.py`
(mismo `llm_output_truncated()` antes de intentar parsear `issues`). Tests de regresión con
fixtures (sin LLM en vivo) en `tests/test_llm_truncation_guards.py`.

## Tolerancias admitidas
- `Posición`: < 2.54mm (0.1 inch) de desviación.
- `Orientación`: Debe ser exacta.
- `Netlist`: Debe ser 100% idéntica (Error crítico si falla).
- `Pin Coverage Fidelity`: objetivo ≥ 90% para el MCU principal de cada caso de prueba
  (pines conectados o explícitamente marcados NC); < 50% se considera una regresión
  del truncamiento descrito en `pin_model_coverage.md`.
