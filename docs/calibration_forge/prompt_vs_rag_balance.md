# Investigación: Balance entre reglas fijas en el prompt y retrieval (RAG)

> Parte de [Calibration Forge](./index.md) · Referenciado desde [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §4.3
> Depende de que se resuelva primero [`knowledge_base_fidelity.md`](./knowledge_base_fidelity.md) para que el RAG tenga señal suficiente como para reemplazar reglas fijas.

> **Estado de la dependencia (actualizado 06-jul-2026):** Session 1 completada — ver [Resultado](./knowledge_base_fidelity.md#resultado-sesión-de-fix-0506-jul-2026). El RAG **ya indexa contexto enriquecido** (`circuit_example_description_density` = **80%**, 261/326 chunks). `test_rag_usb_retrieval` pasó (antes fallaba). Queries de design-intent en `sample_*.json` recuperan `design_intent: … RF … induccion`. **Caveat para Session 4:** el índice denso (`vectors.npy`) no se regeneró — Ollama no estaba corriendo; el backend híbrido usa TF-IDF fresh + embeddings stale pre-fix. Correr `python -m knowledge.build_embed_index` con Ollama activo antes del experimento A/B si se quiere comparar retrieval denso post-fix. La señal TF-IDF sola ya es suficiente para empezar el A/B con precaución.
>
> **Session 2 completada (06-jul-2026)** — ver [`dormant_features_audit.md` §Resultado](./dormant_features_audit.md#resultado-sesión-de-wiring-06-jul-2026). El loop de `design_experience.py` ya produce y persiste datos (causa raíz corregida: hook nunca alcanzado + `ingest_to_rag()` no persistía entre procesos; ambos arreglados). Como groundwork directo para la propuesta #3 de este documento, se creó `knowledge/seed_poc_experience.py`: migra la regla "ESP32 EN pull-up 10k" (hardcodeada hoy en `circuit_synthesizer.py` y `semantic_reviewer.py`) a un `DesignExperience.lessons_learned`, y confirma que es recuperable vía `kb.query(..., chunk_type="design_experience")` desde una KB nueva — el chunk ya aparece como resultado natural en queries de ESP32 (`test_rag_esp32_component`). La regla **no se eliminó** de los prompts — eso sigue siendo trabajo de esta sesión (propuesta #3), que ahora tiene un ejemplo funcionando de extremo a extremo para apoyarse.

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

2. **Unificar `_match_pinouts()` con `ElectronicsKnowledgeBase`:** en vez de mantener un segundo scorer, indexar `pinouts_library.json` como chunks tipo `pinout` dentro del RAG existente (similar a `_chunk_component`), y usar `kb.query(..., chunk_type="pinout")`. Esto también resolvería de paso el cap de 14 pines de `pin_model_coverage.md`, porque el mecanismo de selección pasaría a ser relevancia semántica en vez de un límite de tamaño fijo.

3. **Mover reglas de "siempre aplicables" a `design_experience.py` como lecciones ingeridas**, en vez de texto de prompt: por ejemplo, "ESP32 EN necesita pull-up 10k" podría vivir como un `DesignExperience.lessons_learned` genérico asociado a `mcu="ESP32*"`, recuperable solo cuando el circuito efectivamente incluye un ESP32 — resolviendo también la dependencia cruzada con `dormant_features_audit.md` (ese loop existe pero no tiene datos).

4. **Métrica de "regla irrelevante inyectada":** instrumentar cuántos caracteres del prompt final corresponden a reglas fijas que no mencionan ningún componente presente en la descripción del usuario (ej. reglas de USB en un circuito que no tiene USB). Esto cuantifica el "ruido" de sesgo fijo por llamada y podría loguearse vía `knowledge/llm_session_log.py`.

5. **Revisar `chat_options_for_backend()` / `temperature=0.1`** (`Pulse_cfg.json → llm.agents.circuit_synthesizer.temperature`): una temperatura tan baja combinada con reglas fijas fuertes es la combinación que más favorece la convergencia a un único patrón de salida. Vale la pena probar si con más ejemplos de RAG y reglas reducidas, una temperatura ligeramente mayor (0.2-0.3) mejora la diversidad de soluciones sin perder validez.

## Alcance de la investigación

Este hallazgo es el que más se beneficia de resolver primero `knowledge_base_fidelity.md` — sin ejemplos de RAG con intención y contexto real, retirar las reglas fijas del prompt probablemente empeoraría los resultados a corto plazo. El orden de trabajo recomendado es: (1) fix de indexación → (2) parser extendido → (3) re-ingesta → (4) recién entonces el experimento A/B de este documento.
