# LLM output pipeline — investigación y hardening (06-jul-2026)

**Estado:** Abierto — **Session 4c** (guardrails + multi-turn) y **Session 4d** (orquestación dual-backend) deben completarse antes de confiar en el A/B de Session 4b.

**Documentos relacionados:**
- [Revisión inicial con evidencia de logs](./llm_truncation_review_06072026.md)
- [Session 4b preflight](./session_4b_preflight_verification.md) (`rag_top_k` bug, harness gaps)
- [Estrategia de logging](./logging_strategy.md) (AI Context Buffer en retries)

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
- [ ] Inspeccionar `output.raw.done_reason` tras cada llamada LLM en síntesis y revisión
- [ ] Tratar `length` y `stop`+`content` vacío como fallo recuperable
- [ ] Validación post-parse: MCU/IC con pinout inyectado debe tener `pins` no vacío
- [ ] Subir `semantic_reviewer.max_tokens` o desactivar thinking en revisión

### P1 (recomendado)
- [ ] Fallback: extraer JSON de `thinking` si `content` vacío/inválido
- [ ] Continuation turn: segundo mensaje user para completar JSON truncado (máx. 2)
- [ ] Unificar retry: parse error OR done_reason OR validación semántica → attempt 2+

### P2 (recomendado)
- [ ] Guard de recuento de pines vs `symbols_index` / `pinouts_library`
- [ ] Ajuste de prompt FIDELIDAD DE PINES cuando no hay tabla completa en contexto

### P3 (observabilidad)
- [ ] Campos top-level en `llm_session_log`: `done_reason`, `content_len`, `thinking_len`
- [ ] `tests/test_llm_truncation_guards.py` con fixtures de los 4 modos de fallo
- [ ] Métrica en `evaluation_metrics.md`: **Generation Completeness** (distinto de Pin Coverage)

### Verificación
- [ ] Re-correr `--case esp32_sensors` y `--case esp32_steppers` con backends activos
- [ ] Confirmar que stub MCU y reviewer vacío ya no pasan como OK
- [ ] `pytest` verde

---

## Session 4d — entregables esperados

### Routing
- [ ] `SemanticReviewer` usa `get_backend_client(resolve_backend_name(task="review"))`
- [ ] `validate_complex_apps --backend` afecta síntesis; añadir `--review-backend` o respetar `llm.routing.review_backend`
- [ ] Revisión por defecto en `atomic` (`think: none`, `json_mode: true`) si está healthy

### Harness
- [ ] Exponer en `run_manifest.json`: `generation_attempts`, `truncation_events`, backends usados por etapa
- [ ] Documentar política: casos secuenciales (no paralelizar 5× A/B hasta guardrails estables)

### Concurrencia (investigación, implementación mínima)
- [ ] Documentar en §Resultado: VRAM/perf con ambos servidores activos
- [ ] Opcional: pipeline de 2 casos (caso N review en atomic mientras caso N+1 synth en primary) — solo si 4c estable

### Verificación
- [ ] Con Ollama `:11431` y llama-server `:11439` activos, una corrida completa de un caso usa backends distintos por etapa según config
- [ ] `list_llm_backends()` / MCP reflejan el routing nuevo

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
- ✅ Clip de inputs de embedding (`llm.embed.max_prompt_chars: 2000` + `EmbedClient._clip_text`): un chunk de 3719 chars (`vme_buffers_p0_hwbyte`) devolvía HTTP 500 en `/api/embeddings` y abortaba TODO el rebuild. `rebuild_embed_index()` ahora reporta el offset del batch que falle. Pendiente: re-correr `build_embed_index` cuando Ollama esté libre (compite por GPU con la validación).

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

*(Completar al cerrar Session 4c / 4d.)*
