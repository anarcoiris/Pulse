# Investigación: Balance entre reglas fijas en el prompt y retrieval (RAG)

> Parte de [Calibration Forge](./index.md) · Referenciado desde [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §4.3
> Depende de que se resuelva primero [`knowledge_base_fidelity.md`](./knowledge_base_fidelity.md) para que el RAG tenga señal suficiente como para reemplazar reglas fijas.

> **Estado de la dependencia (actualizado 06-jul-2026):** Session 1 completada — ver [Resultado](./knowledge_base_fidelity.md#resultado-sesión-de-fix-0506-jul-2026). El RAG **ya indexa contexto enriquecido** (`circuit_example_description_density` = **80%**, 261/326 chunks). `test_rag_usb_retrieval` pasó (antes fallaba). Queries de design-intent en `sample_*.json` recuperan `design_intent: … RF … induccion`. **Caveat para Session 4:** el índice denso (`vectors.npy`) no se regeneró — Ollama no estaba corriendo; el backend híbrido usa TF-IDF fresh + embeddings stale pre-fix. Correr `python -m knowledge.build_embed_index` con Ollama activo antes del experimento A/B si se quiere comparar retrieval denso post-fix. La señal TF-IDF sola ya es suficiente para empezar el A/B con precaución.
>
> **Session 2 completada (06-jul-2026)** — ver [`dormant_features_audit.md` §Resultado](./dormant_features_audit.md#resultado-sesión-de-wiring-06-jul-2026). El loop de `design_experience.py` ya produce y persiste datos (causa raíz corregida: hook nunca alcanzado + `ingest_to_rag()` no persistía entre procesos; ambos arreglados). Como groundwork directo para la propuesta #3 de este documento, se creó `knowledge/seed_poc_experience.py`: migra la regla "ESP32 EN pull-up 10k" (hardcodeada hoy en `circuit_synthesizer.py` y `semantic_reviewer.py`) a un `DesignExperience.lessons_learned`, y confirma que es recuperable vía `kb.query(..., chunk_type="design_experience")` desde una KB nueva — el chunk ya aparece como resultado natural en queries de ESP32 (`test_rag_esp32_component`). La regla **no se eliminó** de los prompts — eso sigue siendo trabajo de esta sesión (propuesta #3), que ahora tiene un ejemplo funcionando de extremo a extremo para apoyarse.
>
> **Session 3 completada (06-jul-2026)** — ver [`pin_model_coverage.md` §Resultado](./pin_model_coverage.md#resultado-sesión-de-fix-06-jul-2026). `_match_pinouts()` ahora devuelve `list[tuple[str, dict]]` (ordenada por score, no `dict`); `_compact_pinout(entry, full=True)` inyecta la tabla completa solo para el match primario. Convención `"NC"` / `"unconnected_pins"` + `_normalize_unconnected_pins()` en `circuit_synthesizer.py`. Métrica Pin Coverage Fidelity en `validate_complex_apps.py`. **Al fusionar pinouts en RAG (propuesta #2 abajo), preservar la semántica full/compact y el tipo de retorno ordenado** — no reintroducir el cap binario de 14 pines. **Actualización 06-jul-2026 13:09-13:16 UTC:** re-corrida `validate_complex_apps --case esp32_sensors` con backend `primary` activo (`atomic` seguía caído) — cobertura confirmada **10.3% → 100%** (39/39 pines ESP32-WROOM-32, 4/4 OLED, 4/4 BME280; ver `pin_model_coverage.md` §Resultado). Ya no está pendiente para ese caso; los otros 4 casos (`esp32_steppers`, `esp32_rf_nfc`, `esp32_usb_devkit`, `pulselab_zero`) quedan cubiertos por el baseline (a) del A/B de esta sesión.
>
> **Arquitectura acordada (06-jul-2026):** la fuente de pinouts para RAG **no debe ser** ampliar `pinouts_library.json` a mano (~12 entradas). KiCad ya trae miles de símbolos en `.kicad_sym` (texto S-expression) — ver [`kicad_symbol_kb.md`](./kicad_symbol_kb.md). Session 4 propuesta #2 = indexar desde `kicad_symbol_parser.py` → `symbols_index` → `chunk_type="pinout"`, con `components.json` para params semánticos y `pinouts_library.json` solo como overrides temporales.
>
> **Session 4a completada (06-jul-2026)** — ver [`kicad_symbol_kb.md` §Resultado](./kicad_symbol_kb.md#resultado-sesión-4a-06-jul-2026). La propuesta #2 de abajo está **hecha**: `_match_pinouts()` ahora llama `kb.query(description, chunk_type="pinout")` sobre un índice de 5320 símbolos KiCad reales (5326 chunks con overrides), preservando exactamente el retorno ordenado, la lógica full/compact y `_normalize_unconnected_pins()` de Session 3. Regresión confirmada sin cambios: `esp32_sensors` 100% de cobertura, `pytest tests/` 79/79.
>
> **⚠️ Session 4b RE-BLOQUEADA (06-jul-2026 tarde)** — ver [`llm_truncation_review_06072026.md`](./llm_truncation_review_06072026.md) y plan [`llm_output_pipeline.md`](./llm_output_pipeline.md). Corridas `validate_20260706_182955_b47ed4ea` / `180421_48b2fa28` muestran truncación, stub MCU y reviewer vacío — el A/B confundiría prompt/RAG con fallos de pipeline. **Orden obligatorio:** Session **4c** (guardrails P0 + multi-turn) → Session **4d** (routing primary/atomic, recomendado) → Session **4b**. Ver `CURENT_SPRINT.md` prompts 4c/4d/4b.
>
> **⚠️ BLOQUEANTE detectado 06-jul-2026 (verificación independiente, ver [`session_4b_preflight_verification.md`](./session_4b_preflight_verification.md)) — leer antes de correr la tarea 1:**
> 1. **`rag_top_k` es `0.95` en `Pulse_cfg.json`, no `1`.** El código hace `top_k=int(cfg("llm.agents.circuit_synthesizer.rag_top_k", 1))` (`circuit_synthesizer.py` línea 340) y `int(0.95) == 0` en Python — trunca, no redondea. **Esto significa que ninguna corrida de `validate_complex_apps.py` hecha hasta ahora (incluidas las citadas arriba como "100% pin coverage confirmado" en Session 3 y 4a) inyectó jamás un ejemplo `chunk_type="circuit_example"`** — `self.rag.query(..., top_k=0, ...)` siempre devuelve `[]`. La variante (a) de la tarea 1 ("current behavior with RAG") debe arreglar este valor a un entero ≥ 1 ANTES de correr el A/B, o la variante (a) medirá "cero ejemplos de RAG" por accidente de config, no "comportamiento actual documentado". **Esto NO afecta** el pinout RAG de Session 4a (`_match_pinouts()` usa su propio `pool_size = max(max_pinout_entries * 5, 10)`, línea 214-215, independiente de `rag_top_k`) — solo afecta el mecanismo de "ejemplo de circuito similar completo".
> 2. **`vectors.npy` sigue obsoleto.** Verificado en vivo: `knowledge/data/embeddings/manifest.json` tiene `chunk_count: 358`; una `ElectronicsKnowledgeBase()` real hoy carga **5685** chunks (`pinout: 5326, circuit_example: 326, component: 10, support_circuit: 9, design_rule: 13, design_experience: 1`). `_load_embed_cache()` descarta el índice denso por mismatch (`embed_index_loaded: False` en `kb.stats()`), así que el backend `hybrid` configurado corre como TF-IDF puro ahora mismo, silenciosamente. Correr `python -m knowledge.build_embed_index` con Ollama activo antes del A/B si se quiere que "hybrid" sea real y no solo el valor de config.
> 3. `temperature` real en `Pulse_cfg.json` es `0.6` (no `0.1`, el valor que sigue como fallback hardcodeado en `circuit_synthesizer.py`/`semantic_reviewer.py` y el que asume la propuesta #5 más abajo) — confirmar si esto fue un cambio intencional de una sesión anterior o drift de config antes de usarlo como parte del baseline (a).

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
