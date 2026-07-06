# Investigación: Balance entre reglas fijas en el prompt y retrieval (RAG)

> Parte de [Calibration Forge](./index.md) · Referenciado desde [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §4.3
> Depende de que se resuelva primero [`knowledge_base_fidelity.md`](./knowledge_base_fidelity.md) para que el RAG tenga señal suficiente como para reemplazar reglas fijas.

> **Estado de dependencias (07-jul-2026)** — ver [`docs/status/CURRENT_SPRINT.md`](../../status/CURRENT_SPRINT.md) (source of truth para orden de sesiones):
> - Sessions 1–3, **4a**: ✅ completadas (enlaces §Resultado en docs citados abajo).
> - **4b parte 1 (A/B confundido)**: ✅ registrada — §Resultado A/B más abajo (runs `182955`/`201754`; **no usar para trimming**).
> - **4c P0**: ✅ verificado live (runs `212059`/`213418`) — [`pipelines/llm_output_pipeline.md`](./pipelines/llm_output_pipeline.md) §Resultado.
> - **4d**: code landed (`review_backend: atomic`); pendiente corrida live con review en atomic.
> - **4b clean re-run**: ⏳ siguiente hito tras verificación 4d.
>
> Blockers de preflight **resueltos** (ver [`verification/session_4b_preflight.md`](./verification/session_4b_preflight.md) §7): `rag_top_k: 1`, embeddings **5685** chunks, reviewer guardrails.

## Problema observado

`knowledge/circuit_synthesizer.py` y `knowledge/semantic_reviewer.py` codifican conocimiento de electrónica como **texto imperativo fijo** en el system prompt, en vez de recuperarlo dinámicamente vía RAG. Esto tenía sentido cuando el backend era un modelo pequeño/remoto con poco contexto y sin RAG maduro; hoy el backend `primary` es un modelo de razonamiento local de 9B con 98,304 tokens de contexto (`Pulse_cfg.json`), y el RAG híbrido ya existe. La pregunta de investigación es: **¿cuánto de esa rigidez sigue aportando valor, y cuánto está limitando innecesariamente al modelo (o incluso introduciendo sesgos incorrectos para casos que no calzan con las reglas)?**

## Evidencia

### 1. Reglas hardcodeadas como texto fijo, no como conocimiento recuperado

```56:64:knowledge/circuit_synthesizer.py
REGLAS UART / USB (OBLIGATORIAS):
- Para ESP32-WROOM-32 programación UART: U0TXD=GPIO1, U0RXD=GPIO3.
- CH340/CP2102: TXD del bridge va a RX del MCU; RXD del bridge va a TX del MCU.
- Incluir condensadores de desacople 100nF + 10uF en alimentación del MCU.
- Pines EN del ESP32 requieren pull-up 10k a 3.3V.
- USB D+ y D- deben nombrarse USB_D+ y USB_D- (o D+/D-).
```

Estas reglas están **siempre presentes**, en cada llamada, sin importar si el circuito solicitado usa USB, UART, o ni siquiera un ESP32. Ocupan presupuesto de prompt fijo y actúan como prior fuerte incluso cuando son irrelevantes.

El mismo patrón se repite en `knowledge/semantic_reviewer.py`:

```24:32:knowledge/semantic_reviewer.py
REGLAS DE DISEÑO ESTRICTAS (AI DRC):
1. '0' es la tierra de simulación SPICE. 'GND' es la malla de masa física en KiCad...
2. Los circuitos integrados (MCU, ICs) necesitan condensadores de desacople de 100nF...
...
7. CH340 TXD conecta a RX del MCU; CH340 RXD conecta a TX del MCU (crossover).
```

7 reglas numeradas inyectadas en **cada** revisión semántica, sea cual sea el circuito.

### 2. Retrieval duplicado y paralelo al RAG real

`circuit_synthesizer.py` implementa su propio buscador de pinouts por keyword-scoring, en vez de usar `ElectronicsKnowledgeBase` (que ya existe para esto):

```102:119:knowledge/circuit_synthesizer.py
def _match_pinouts(self, description: str) -> dict:
    """Return at most 2 best-matching pinout entries (avoid dumping all ESP32 variants)."""
    desc = description.lower()
    scored: list[tuple[int, str, dict]] = []
    for key, entry in self.pinouts_db.items():
        kl = key.lower()
        score = 0
        if kl in desc:
            score += 100 + len(kl)
        ...
```

Esto es un segundo motor de retrieval, ad-hoc y sin scoring semántico, que vive completamente fuera de `rag_engine.py`. Dos sistemas de recuperación distintos, con heurísticas distintas, mantenidos por separado — inconsistencia arquitectónica además de la cuestión de sesgo.

### 3. Presupuesto de RAG deliberadamente muy bajo pese al contexto disponible

```yaml
# Pulse_cfg.json → llm.agents.circuit_synthesizer
rag_top_k: 1
rag_max_components: 8
prompt_max_chars: 48000
```

Solo **un** ejemplo de RAG se inyecta por llamada (`rag_top_k: 1`), truncado a 8 componentes, dentro de un presupuesto de 48,000 caracteres que rara vez se acerca a llenarse (el ejemplo estático + reglas fijas + 1 ejemplo de RAG comprimido está muy por debajo de ese límite). No hay una razón de presupuesto real para no incluir 3-5 ejemplos.

### 4. El ejemplo estático embebido es más fuerte que el RAG dinámico

Como se documenta en `pin_model_coverage.md`, el resultado generado hoy (`esp32_sensors.json`) reproduce el patrón exacto del ejemplo estático del prompt (mismos números de pin), no el de un ejemplo de RAG recuperado dinámicamente — evidencia indirecta de que el ejemplo fijo domina sobre el contexto recuperado.

## Por qué importa

- **Cobertura falsa de seguridad:** las reglas fijas dan la ilusión de "estas 5-7 reglas garantizan diseños correctos", pero no escalan — cualquier MCU, bus o patrón no cubierto explícitamente (STM32, RP2040, CAN bus, un ADC diferencial, etc.) no tiene ninguna regla equivalente y depende 100% de lo que el modelo ya sabe, mientras que el presupuesto de prompt se gasta en reglas que a veces no aplican.
- **Mantenimiento centralizado en código en vez de datos:** cada regla nueva de electrónica requiere editar y desplegar `circuit_synthesizer.py`; si viviera como conocimiento en el RAG (`knowledge/data/training/`, `design_experience.py`), se podría añadir con `ingest_text()` sin tocar código ni prompts.
- **Riesgo de conflicto:** si el RAG recupera un ejemplo real que contradice una regla fija (ej. un diseño real de CH340 con un crossover distinto por alguna razón de footprint específica), el prompt fuerza la regla fija sobre la evidencia recuperada, sin forma de que el modelo pondere ambas fuentes.

## Líneas de investigación / próximos pasos propuestos

1. **Experimento A/B controlado:** correr `knowledge/validate_complex_apps.py` dos veces sobre los mismos 5 casos (`esp32_sensors`, `esp32_steppers`, `esp32_rf_nfc`, `esp32_usb_devkit`, `pulselab_zero`): (a) con las reglas actuales, (b) con las "REGLAS OBLIGATORIAS" retiradas del prompt base y reemplazadas por `rag_top_k=3-5` con ejemplos reales que ya contengan esas mismas convenciones (una vez arreglado `knowledge_base_fidelity.md`, esos ejemplos deberían poder enseñar el mismo conocimiento). Comparar tasa de errores semánticos (`semantic_reviewer`) entre ambas corridas.

2. ✅ **Hecho (Session 4a).** Unificar `_match_pinouts()` con `ElectronicsKnowledgeBase`: en vez de mantener un segundo scorer sobre `pinouts_library.json` (~12 entradas manuales), **indexar pinouts desde KiCad** (`.kicad_sym` → `knowledge/data/symbols_index.json` → chunks `chunk_type="pinout"` en RAG). Ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md) §Resultado para el detalle completo. `_match_pinouts()` llama `kb.query(description, chunk_type="pinout")` con un boost de nombre-exacto-normalizado sobre el score semántico. Preservado de Session 3: retorno ordenado, lógica full/compact (tabla completa solo para el match primario), y `_normalize_unconnected_pins()`. `pinouts_library.json` queda como capa de override permanente para partes sin símbolo KiCad oficial (no solo temporal — ver limitación §3 en `kicad_symbol_kb.md`).

3. **Mover reglas de "siempre aplicables" a `design_experience.py` como lecciones ingeridas**, en vez de texto de prompt: por ejemplo, "ESP32 EN necesita pull-up 10k" podría vivir como un `DesignExperience.lessons_learned` genérico asociado a `mcu="ESP32*"`, recuperable solo cuando el circuito efectivamente incluye un ESP32 — resolviendo también la dependencia cruzada con `dormant_features_audit.md` (ese loop existe pero no tiene datos).

4. **Métrica de "regla irrelevante inyectada":** instrumentar cuántos caracteres del prompt final corresponden a reglas fijas que no mencionan ningún componente presente en la descripción del usuario (ej. reglas de USB en un circuito que no tiene USB). Esto cuantifica el "ruido" de sesgo fijo por llamada y podría loguearse vía `knowledge/llm_session_log.py`.

5. **Revisar `chat_options_for_backend()` / `temperature=0.1`** (`Pulse_cfg.json → llm.agents.circuit_synthesizer.temperature`): una temperatura tan baja combinada con reglas fijas fuertes es la combinación que más favorece la convergencia a un único patrón de salida. Vale la pena probar si con más ejemplos de RAG y reglas reducidas, una temperatura ligeramente mayor (0.2-0.3) mejora la diversidad de soluciones sin perder validez.

## Alcance de la investigación

Este hallazgo es el que más se beneficia de resolver primero `knowledge_base_fidelity.md` — sin ejemplos de RAG con intención y contexto real, retirar las reglas fijas del prompt probablemente empeoraría los resultados a corto plazo. El orden de trabajo recomendado es: (1) fix de indexación → (2) parser extendido → (3) re-ingesta → (4) recién entonces el experimento A/B de este documento.

---

## Resultado A/B — Session 4b, parte 1 (experimento confundido, sin decisión de trimming)

**Fecha:** 06-jul-2026  
**Estado:** Datos recogidos; **no válidos para decidir trimming** hasta Session **4c** (guardrails reviewer) + **4d** (reviewer en `atomic`) + rebuild de embeddings.

### Confounders activos durante la corrida

| Confounder | Efecto observado |
|---|---|
| Reviewer en `primary` con `think=low` y `max_tokens=4096` | 9/10 revisiones fallaron con JSON vacío (thinking agotó budget). Solo `esp32_usb_devkit` variante B devolvió issues. |
| Embeddings densos obsoletos (358 vs ~5685 chunks) | Backend `hybrid` ejecutó como TF-IDF puro. |
| Variante A: `atomic` caído al inicio | Run A sin lane paralela; variante B tuvo `atomic` disponible pero reviewer siguió en `primary`. |
| 2/10 generaciones fallaron (variante A) | `esp32_steppers` JSON truncado; `pulselab_zero` respuesta vacía. |

### Tabla comparativa (pin coverage + semantic review)

Runs:
- **Variante A:** [`20260706_182955_validate_20260706_182955_b47ed4ea`](../../knowledge/data/validation_complex/runs/20260706_182955_validate_20260706_182955_b47ed4ea/)
- **Variante B:** [`20260706_201754_validate_20260706_201754_36f71d18`](../../knowledge/data/validation_complex/runs/20260706_201754_validate_20260706_201754_36f71d18/)

| Caso | Var | Gen | Comp | Pin cov avg | Review issues | Review critical | Gen time | Review time |
|---|---|---|---|---|---|---|---|---|
| esp32_sensors | A | OK | 9 | 100% | FAIL | — | 793s | 196s |
| esp32_sensors | B | OK | 7 | 99% | FAIL | — | 200s | 198s |
| esp32_steppers | A | **FAIL** | — | — | — | — | 1764s | — |
| esp32_steppers | B | OK | 15 | 99% | FAIL | — | 163s | 201s |
| esp32_rf_nfc | A | OK | 7 | 100% | FAIL | — | 875s | 199s |
| esp32_rf_nfc | B | OK | 6 | 100% | FAIL | — | 636s | 198s |
| esp32_usb_devkit | A | OK | 11 | 100% | FAIL | — | 665s | 199s |
| esp32_usb_devkit | B | OK | 12 | 85% | **4** | **2** | 515s | 107s |
| pulselab_zero | A | **FAIL** | — | — | — | — | 1779s | — |
| pulselab_zero | B | OK | 19 | 146%* | FAIL | — | 699s | 201s |

\* Promedio >100% indica enumeración de pines alucinada (ej. PN532 con 16 pines generados vs 7 de referencia).

### Lectura preliminar (no decisoria)

- **Generación:** variante B completó 5/5 casos vs 3/5 en A; tiempos más bajos en la mayoría de casos exitosos. Parte del delta puede ser varianza del modelo, no solo el toggle A/B.
- **Pin coverage:** ambas variantes logran alta fidelidad en ESP32 cuando generan; variante B mostró sobre-enumeración en `pulselab_zero`.
- **Semantic review:** métrica primaria **inutilizable** en esta corrida — el reviewer truncó en ~90% de casos. No se puede comparar "reglas vs RAG" con esta señal.
- **Decisión de trimming (tareas 2-3 de Session 4b):** permanece **abierta**; requiere re-ejecución limpia tras 4c+4d.

### Infra arreglada (antes del re-run limpio)

- `rag_top_k: 0.95 → 1` + `rag_top_k_variant_b: 4` en `Pulse_cfg.json`
- Toggle `--variant a|b` en harness + `tests/test_ab_variant.py`
- Session **4c P0** — ver [`llm_output_pipeline.md`](./llm_output_pipeline.md) §Resultado
- Embeddings rebuild — **5685** chunks (`manifest.json`)

### Próximo paso (ver [`docs/status/CURRENT_SPRINT.md`](../../status/CURRENT_SPRINT.md))

1. Verificar review en `atomic` (Session 4d — cfg ya en `review_backend: atomic`)
2. **4b clean re-run** (`--variant a` + `--variant b`, 5 casos cada uno)
3. Decisión trimming con datos no confundidos
