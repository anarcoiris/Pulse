# LLM output pipeline — investigación y hardening (06-jul-2026)

> **Role:** reference (pipeline master)  
> **Status:** active  
> **Source of truth for:** LLM guardrails, multi-turn recovery, dual-backend orchestration  
> **Last verified:** 2026-07-07  
> **See also:** [`../verification/llm_truncation_review_06072026.md`](../verification/llm_truncation_review_06072026.md) · [`../../status/CURRENT_SPRINT.md`](../../status/CURRENT_SPRINT.md)

**Estado:** Session **4c P0 verificado**; **4d code landed** — pendiente verify atomic review. **4b clean re-run** tras 4d. Ver §Resultado y [`CURRENT_SPRINT.md`](../../status/CURRENT_SPRINT.md).

**Documentos relacionados:**
- [Revisión inicial con evidencia de logs](../verification/llm_truncation_review_06072026.md)
- [Session 4b preflight](../verification/session_4b_preflight.md) (`rag_top_k` bug, harness gaps)
- [Estrategia de logging](../logging_strategy.md) (AI Context Buffer en retries)

---

## Problema

El pipeline LLM actual asume **una sola respuesta por tarea** y **JSON parseable = éxito**. Con `qwythos-9b-96k` + `think: low` en Ollama (`primary`), y un reviewer semántico en el mismo backend con solo 4096 tokens, las corridas de `validate_complex_apps.py` producen:

1. **Stub semántico** — JSON válido pero MCU sin `pins` (`558a7e5ad3f2`)
2. **Truncación dura** — `done_reason: length`, `content` vacío (`3654463beaa0`)
3. **Reviewer truncado** — todo el budget en `thinking`, sin JSON en `content`
4. **Enumeración runaway** — pines 1–1000 cuando falta pinout de referencia (`ae86f93ab97c`)

Además, **no hay orquestación** entre `primary` (Ollama `:11431`) y `atomic` (llama-server `:11439`): el harness es secuencial, `SemanticReviewer` ignora `llm.routing` y siempre usa `get_llm_client()` (primary).

---

## Arquitectura objetivo (post-Session 4c/4d)

```
┌─────────────────────────────────────────────────────────────────┐
│ validate_complex_apps (orquestador, secuencial por caso)        │
├─────────────────────────────────────────────────────────────────┤
│ 1. Pinout retrieval        │ determinístico (RAG pinout)       │
│ 2. Circuit generation      │ primary | atomic, 1–3 chat turns  │
│ 3. Post-parse validation   │ determinístico (pins, done_reason)│
│ 4. Semantic DRC            │ atomic, think=off, json_mode      │
│ 5. Persist + métricas      │ pin_coverage + review + trunc meta│
└─────────────────────────────────────────────────────────────────┘
```

**Principio:** separar **razonamiento largo** (síntesis en `primary`) de **JSON corto y fiable** (revisión en `atomic`), con **validación determinística** entre etapas — no un único agente monolítico.

---

## División en sesiones

| Sesión | Alcance | Prioridad |
|--------|---------|-----------|
| **4c** | Guardrails P0–P2, multi-turn continuation, tests con fixtures | **Bloquea 4b** |
| **4d** | Routing reviewer → atomic, observabilidad en logs, harness pipeline | Recomendado antes de 4b |
| **4b** | A/B prompt vs RAG (solo tras 4c mínimo) | Depende de 4c |

Session 5 (repo hygiene) permanece independiente.

---

## Session 4c — entregables esperados

### P0 (obligatorio)
- [x] Inspeccionar `output.raw.done_reason` tras cada llamada LLM en síntesis y revisión (`result["done_reason"]` normalizado en `llm_client.py`)
- [x] Tratar `length` y `stop`+`content` vacío como fallo recuperable (`llm_output_truncated`, retry en síntesis)
- [x] Validación post-parse: MCU/IC con pinout inyectado debe tener `pins` no vacío (`_validate_injected_pinouts`)
- [x] Reviewer: `disable_thinking=True`, `json_mode`, `max_tokens` 8192, `parse_llm_result`, `session_id` passthrough
- [x] `parse_llm_result(content, thinking)` en `llm_json.py`
- [x] Subir `semantic_reviewer.max_tokens` a 8192 (además de `disable_thinking`, ambos aplicados — plan (c)+(d) de la lista de opciones abajo)

### P1 (recomendado)
- [x] Fallback: extraer JSON de `thinking` si `content` vacío/inválido (`parse_llm_result`, unifica el fallback que antes solo existía oculto en `_chat_openai`)
- [x] Continuation turn: `circuit_synthesizer._continue_truncated_json()`, hasta 2 turnos, usando el nuevo parámetro `history` de `LLMClient.chat()`; se dispara solo cuando hay contenido parcial truncado (`done_reason=="length"` + `content` no vacío), cae al reintento con RAG completo si no aplica o se agota
- [x] Unificar retry: parse error OR done_reason OR validación semántica → mismo camino de reintento en `generate_circuit_json()` (vía `_components_from_llm_result` + `_finalize_components` compartido)

### P2 (recomendado)
- [x] Guard de recuento de pines vs pinout de referencia: `_validate_injected_pinouts()` rechaza `len(pins) > max(expected*2, 120)` ("enumeracion sospechosa") — cubre el modo "1000 pines" de la revisión de truncación
- [x] Ajuste de prompt FIDELIDAD DE PINES cuando no hay tabla completa en contexto — nueva instrucción explícita "nunca inventes ni enumeres pines consecutivos para completar un rango que no conoces"

### P3 (observabilidad)
- [x] Campos top-level en `llm_session_log`: `done_reason`, `content_len`, `thinking_len` (más `eval_count` cuando el backend lo reporta)
- [x] `tests/test_llm_truncation_guards.py` con fixtures de los 4 modos de fallo (stub MCU, truncación dura, reviewer solo-thinking, enumeración runaway) + un test de recuperación por continuación con un cliente LLM falso (sin red)
- [x] Métrica en `evaluation_metrics.md` §6: **Generation Completeness** (distinto de Pin Coverage — mide si la llamada LLM en sí terminó de forma sana, no solo si el JSON resultante tiene pines completos)

### Verificación
- [x] Verificación live reducida: `--case esp32_rf_nfc`, `--case esp32_usb_devkit` (runs `212059`, `213418`) — reviewer JSON OK
- [x] Confirmar que reviewer vacío ya no pasa como OK (vs confounded A/B: 9/10 FAIL)
- [x] `pytest tests/` verde — **101 passed** (incl. `test_llm_truncation_guards.py`)

---

## Session 4d — entregables esperados

### Routing
- [x] `SemanticReviewer` usa `get_backend_client(resolve_backend_name(task="review"))` — constructor ahora acepta `backend="auto"` y resuelve una sola vez en `_resolve_backend()`, igual que `CircuitSynthesizer`
- [x] `validate_complex_apps --backend` afecta síntesis; se añadió `--review-backend auto|primary|atomic` (default `auto` → `llm.routing.review_backend`)
- [x] Revisión por defecto en `atomic` (`think: none`, `json_mode: true`) si está healthy — `Pulse_cfg.json` → `llm.routing.review_backend` cambiado de `"primary"` a `"atomic"`; `auto_fallback: true` ya cubre atomic caído (vuelve a `primary` sin excepción)

### Harness
- [x] Exponer en `run_manifest.json`: `generation_attempts`, `truncation_events`, backends usados por etapa — `synthesis_backend`/`review_backend` por caso, `generation_attempts`/`truncated` por caso (de `circuit_synthesizer.generate_circuit_json()`, cuenta intentos incluyendo turnos de continuación), `truncation_events` agregado a nivel de manifiesto (conteo de casos truncados)
- [ ] Documentar política: casos secuenciales (no paralelizar 5× A/B hasta guardrails estables) — sigue siendo la política; no se implementó paralelismo, `validate_complex_apps.py` sigue corriendo casos en un `for` secuencial

### Concurrencia (investigación, implementación mínima)
- [ ] Documentar en §Resultado: VRAM/perf con ambos servidores activos — pendiente de una corrida con ambos backends activos simultáneamente ejercitados (ver §Resultado para datos parciales ya recogidos)
- [ ] Opcional: pipeline de 2 casos (caso N review en atomic mientras caso N+1 synth en primary) — no implementado, fuera de alcance de esta sesión

### Verificación
- [x] Con Ollama `:11431` y llama-server `:11439` activos, una corrida completa de un caso usa backends distintos por etapa según config — confirmado por routing tests (`tests/test_llm_backends.py`); pendiente una corrida `validate_complex_apps` en vivo que ejercite ambos backends a la vez (el harness de verificación de 4c usó `review_backend` aún en `primary` por config, antes de este cambio — ver §Resultado)
- [x] `list_llm_backends()` / MCP reflejan el routing nuevo — `list_backends()` lee `cfg("llm.routing")` en vivo, no necesita cambio de código; refleja `review_backend: "atomic"` automáticamente

---

## Auditoría de código adicional (06-jul-2026, tarde — sesión de harness A/B)

Verificación línea-por-línea de `llm_client.py`, `ollama_native.py`, `llm_backends.py`, `llm_prompt_format.py`, `llm_session_log.py`, `atomic_lane.py` y `semantic_reviewer.py` hecha mientras corría la validación variante A. Hallazgos que **refinan** los entregables de 4c/4d (no los reemplazan):

### Correcciones/precisiones al plan de Session 4c

1. **`done_reason` sólo existe en el path native.** `ollama_native.chat_native()` lo devuelve dentro de `raw`, pero `LLMClient._chat_openai()` (líneas ~239-256) **descarta `choice.finish_reason` y no devuelve `raw`**. El backend `atomic` es OpenAI-only (`api: "openai"`), así que el guardrail de la tarea P0 #1 tal como está escrito ("leer `result['raw'].done_reason`") funcionaría en `primary` (native) pero sería un **no-op silencioso en `atomic`** — exactamente el backend al que 4d quiere mandar la revisión. Implementación correcta: normalizar ambos paths a un campo común en el dict de retorno (ej. `result["done_reason"]`), mapeando `finish_reason: "length"|"stop"` (OpenAI) y `raw.done_reason` (native), y que los guardrails lean SOLO ese campo normalizado.
2. **Ya existe un fallback thinking→content oculto en el path OpenAI:** `_chat_openai` copia `msg.thinking`/`msg.reasoning` a `content` cuando `content` llega vacío. El path native NO lo hace. La tarea P1 #5 (`parse_llm_result(content, thinking)`) debe **unificar** este comportamiento en un solo lugar (idealmente moverlo fuera de `_chat_openai` hacia `llm_json.py`), no añadir una tercera variante divergente.
3. **`LLMClient.chat()` no acepta historial de mensajes** — sólo `system` + `user` (arma la lista de 2 mensajes internamente). La continuation turn de P1 #6 tiene este prerequisito oculto: extender `chat()` con un parámetro `messages`/`history` (ambos paths internos ya trabajan con listas de mensajes, el cambio es pequeño) o añadir `chat_continue()`. Sin esto no hay forma de mandar "assistant partial + user continue".
4. **Quick-win P0 para el reviewer que no requiere subir `max_tokens`:** `llm.chat(..., disable_thinking=True)` ya fuerza el path OpenAI con `extra_body.reasoning_effort: "none"` (`_use_native()` devuelve False). Con thinking desactivado, los 4096 tokens completos van a `content` — probablemente suficiente para `{"issues":[...]}`. Verificar en vivo que Ollama honra `reasoning_effort` para `qwythos-9b-96k`; si no lo honra, subir `max_tokens` a 8192-16384 como plan B (ambas cosas juntas tampoco hacen daño).
5. **Trazabilidad del reviewer rota:** `SemanticReviewer.review_netlist()` no acepta `session_id` ni `meta`, así que cada llamada de revisión aterriza en una **sesión aleatoria separada** (`31fed70fcaf9`, `2ee7bbcf5034`, `1094f048c47f`…) con `attempt: 0`, desconectada del run de validación que la disparó. Extender la firma con `session_id`/`meta` passthrough (como ya hace `generate_circuit_json`) para que el A/B de 4b pueda correlacionar generación y revisión.

### Investigación externa (Ollama upstream) que valida y mejora el plan

- **Confirmado por docs/issues de Ollama:** `num_predict` limita thinking + content **combinados**; cuando el thinking agota el budget, la API devuelve `content: ""` + `done_reason: "length"` — exactamente el modo de fallo del reviewer. El issue upstream #16184 recomienda tratar ese par como "output budget exhausted" y reintentar con más budget o menos thinking effort: es literalmente la tarea P0 de 4c, con respaldo del mantenedor.
- **Alternativa superior para el reviewer — structured outputs:** el `/api/chat` nativo acepta un campo `format` (json / json-schema) que **acota la respuesta final sin desactivar el thinking** (recomendación del mantenedor en #16184). Nuestro `ollama_native.chat_native()` hoy NO envía `format`. Añadirlo (1 línea en el payload + parámetro passthrough) daría al reviewer JSON garantizado manteniendo el razonamiento. Candidato fuerte para 4c task 3, plan A+.
- **`think: false` top-level funciona en `/api/chat` para la familia Qwen3** (issue #14793: falla solo si se mete dentro de `options`; nuestro cliente ya lo manda top-level ✅). Wart detectado en `LLMClient._use_native()`: decide el path con `self.think` (nivel de instancia) e ignora el override per-call `think=False` — o sea `chat(think=False)` se queda en el path native con think desactivado, lo cual es correcto de facto pero por accidente. Documentar o arreglar en 4c.
- Resumen de opciones para el reviewer (4c task 3), en orden de preferencia: **(1)** native + `format: "json"` + `think` bajo/off, **(2)** native + `think=False` per-call, **(3)** path OpenAI vía `disable_thinking=True` (`reasoning_effort: "none"` — verificar que Ollama lo honra), **(4)** subir `max_tokens` a 8192-16384 (paliativo, compatible con todas las anteriores).

### Correcciones/precisiones al plan de Session 4d

6. **`llm.routing.review_backend` vale `"primary"` en `Pulse_cfg.json` hoy** — la tarea 1 de 4d requiere cambiar el **valor de config** a `"atomic"` además del refactor de código (`get_backend_client(resolve_backend_name(task="review"))` respetaría el routing, pero el routing actual apunta a primary).
7. **`atomic` está caído ahora mismo** (health check a `:11439/health` falla; el `qwythos.state.json` tiene un pid stale). La verificación de 4d necesita levantar llama-server primero (`scripts_dir: C:/Users/soyko/Documents/Ollama/docker/llamacpp`, perfil `concurrent2`). El fallback `auto_fallback: true` → primary ya funciona (es lo que pasó en todas las corridas de hoy).
8. **`chat_options_for_backend("atomic")`** ya devuelve `json_mode: true` + `disable_thinking: true` — el reviewer en atomic saldría con JSON estricto por `response_format` (llama-server lo soporta), PERO nota que `_chat_openai` hace `call_kwargs.pop("response_format")` si `is_reasoning_model(model)` matchea; el modelo atomic actual es `qwen3-4b-instruct-48k`, que NO matchea los patrones de `is_reasoning_model()` — OK. Si algún día el atomic corre un modelo con "qwq"/"r1" en el nombre, el json_mode se desactivaría silenciosamente.

### Ya implementado en la sesión de harness del 06-jul (NO rehacer en 4c/4d — verificar y construir encima)

- ✅ `rag_top_k` fix (`0.95` → `1`) + warning si `int(cfg(top_k)) < 1` en `circuit_synthesizer._circuit_example_rag_top_k()` — tarea P0 #4 de 4c **ya hecha**.
- ✅ Toggle A/B: `CircuitSynthesizer(ab_variant="a"|"b")` (variante b sin bloque OBLIGATORIAS + `rag_top_k_variant_b: 4`), flag `--variant` en `validate_complex_apps.py`, `ab_variant` en manifiestos y meta de logs. Tests en `tests/test_ab_variant.py` (5/5).
- ✅ `semantic_review` (issue_count/critical_count/issues) persistido por caso y en `run_manifest.json` — la parte "semantic_review status distinto de synthesis OK" de la tarea 4 de 4d ya existe; 4d sólo añade `synthesis_backend`/`review_backend`/`truncation_events`.
- ✅ Reviewer usa `parse_json_object()` (tolera fences/prosa alrededor del JSON) en vez de `json.loads` crudo — mitiga el modo de fallo "JSON con texto alrededor", NO el de content vacío por truncación (ese sigue siendo 4c P0).
- ✅ Harness a prueba de cp1252 (`sys.stdout.reconfigure(utf-8)` + `_safe_print`) — el crash `UnicodeEncodeError` por `Ω` en el run `180421` no puede repetirse.
- ✅ Clip de inputs de embedding + rebuild completado — **5685** chunks indexados (`build_embed_index` 06-jul noche).

---

## Logs de referencia (no re-ejecutar salvo regresión)

| Session ID | Call ID | Modo de fallo |
|------------|---------|---------------|
| `validate_20260706_182955_b47ed4ea` | `558a7e5ad3f2` | Stub MCU |
| `validate_20260706_182955_b47ed4ea` | `3654463beaa0` | `length`, content vacío |
| `validate_20260706_182955_b47ed4ea` | reviewer `2ee7bbcf5034` | Reviewer `length` |
| `validate_20260706_180421_48b2fa28` | `ae86f93ab97c` | 1000 pines |

---

## Resultado

### Session 4c — estado (07-jul-2026)

| Ámbito | Estado | Notas |
|--------|--------|-------|
| **P0** | ✅ Done + verified live | Runs `212059` (`esp32_rf_nfc`), `213418` (`esp32_usb_devkit`) |
| **P1–P3** | ✅ Code landed | `parse_llm_result`, `_continue_truncated_json`, `test_llm_truncation_guards.py`, log fields |
| **pytest** | 101 passed | |

**Verificación live (post-guardrails, variant A, `review_backend` aún `primary`):**

| Caso | Run | Gen | Review | Review time | Antes (confundido) |
|------|-----|-----|--------|-------------|-------------------|
| esp32_rf_nfc | `validate_20260706_212059_812581a9` | OK (8 comp) | 1 issue (1 critical) | 61s | FAIL (~198s) |
| esp32_usb_devkit | `validate_20260706_213418_bb587bdd` | OK (12 comp) | 6 issues (3 critical) | 115s | FAIL |

Reviewer log (`f0c4a3fce85a.json`): `api=openai`, `think=false`, `max_tokens=8192`, `finish_reason=stop`, `session_id` correlacionado.

### Session 4d — estado (07-jul-2026)

| Entregable | Estado |
|------------|--------|
| `SemanticReviewer` → `resolve_backend_name(task="review")` | ✅ |
| `Pulse_cfg.json` → `review_backend: "atomic"` | ✅ |
| `--review-backend` en harness + campos manifiesto | ✅ |
| Corrida live review en `atomic` | ✅ Confirmado |

**Corrida live en `atomic` (07-jul-2026, sesión paralela de hardening):** se re-revisó el netlist ya
generado de `esp32_sensors` (run `validate_20260706_213340_b12415d7`, 9 componentes) directamente
contra `SemanticReviewer()` con la config ya apuntando a `review_backend: "atomic"` (sin regenerar el
circuito — el reviewer es independiente de qué backend generó el netlist). Resultado: `reviewer.backend_name
== "atomic"`, revisión completada en **16.6s** (vs 61-115s en `primary`) con **6 issues (3 critical)**
coherentes con las reglas AI DRC (EN sin pull-up, GPIO0/boot, decoupling caps, alias GND/0, USB D+/D-
faltante). Confirma que el modelo `qwen3-4b-instruct-48k` en `atomic` produce revisiones de calidad
comparable a `primary` a una fracción del tiempo — la orquestación dual-backend cumple su objetivo de
diseño (razonamiento largo en `primary`, JSON corto y fiable en `atomic`).

**Hallazgo adicional (verificación 4c/4d en vivo, sesión de hardening 07-jul-2026):** dos corridas
adicionales de `--case esp32_sensors` y `--case esp32_steppers` (`validate_20260706_213340_b12415d7`,
variant A) confirman que la generación y el reviewer P0 funcionan de forma consistente (2/2 revisiones
exitosas, `esp32_steppers` ya no crashea con `JSONDecodeError` como en el A/B confundido), **pero
exponen un gap real en el guard de pines parciales** (`_validate_injected_pinouts`): el guard solo
valida el componente que coincide con el match "primario" de `_match_pinouts(description)` sobre el
texto COMPLETO de la descripción — en prompts multi-componente (ESP32 + 2×A4988, o ESP32 + PN532 +
CC1101) el match primario resuelve a un solo componente, y los demás quedan sin validar aunque tengan
pinout de referencia conocido. Evidencia:

| Run | Caso | Pin coverage por componente |
|---|---|---|
| `20260706_213340...` | esp32_sensors | U1 ESP32-WROOM-32 **4/39 (10%)**, OLED 4/4, BME280 4/4 |
| `20260706_220539...` | esp32_steppers | U1 ESP32 **4/39 (10%)**, U2 A4988 **4/16 (25%)**, U3 A4988 **4/16 (25%)** |
| `212059` (sesión paralela) | esp32_rf_nfc | U1 ESP32 40/39 (103%), PN532 7/7, CC1101 **4/8 (50%)** |

Se añadió un guard de "cobertura de pines incompleta" (`_validate_injected_pinouts`, umbral ≥90%,
mismo criterio que Pin Coverage Fidelity) que SÍ habría rechazado estos casos **si el componente
afectado fuera el match primario** — pero como se ve arriba, en circuitos multi-IC frecuentemente no
lo es. Cubierto por test de regresión (`test_mcu_with_partial_pins_is_rejected` en
`tests/test_llm_truncation_guards.py`), pero el test aísla el componente afectado artificialmente; no
reproduce el caso multi-componente real. **Backlog para una futura sesión de hardening:** extender
`_validate_injected_pinouts` para validar TODOS los componentes IC/MCU contra SU PROPIO match de RAG
(no solo el match global de la descripción completa) — requeriría llamar `_match_pinouts` por
componente en vez de una sola vez por descripción, con el costo de N queries RAG en vez de 1. La
métrica Pin Coverage Fidelity (§4 de `evaluation_metrics.md`) ya mide y reporta este gap por caso
aunque no bloquee la generación; no es una regresión silenciosa de datos, solo de generación no
óptima.

### Session 4b — estado

| Fase | Estado |
|------|--------|
| Parte 1 (A/B confundido) | ✅ Runs `182955` / `201754` — [`prompt_vs_rag_balance.md`](./prompt_vs_rag_balance.md) §Resultado A/B |
| Clean re-run (5×2) | 🔄 En curso — ver [`prompt_vs_rag_balance.md`](./prompt_vs_rag_balance.md) §Resultado A/B (parte 2) |
| Decisión trimming | ⏸ Diferida hasta que la clean re-run termine |
