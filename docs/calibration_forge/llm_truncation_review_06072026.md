# LLM output truncation & retry gaps — review (06-jul-2026)

**Status:** Open — blocks reliable Session 4b A/B runs until mitigated  
**Sessions examined:** `validate_20260706_180421_48b2fa28`, `validate_20260706_182955_b47ed4ea`  
**Related code:** `knowledge/llm_client.py`, `knowledge/circuit_synthesizer.py`, `knowledge/semantic_reviewer.py`, `knowledge/llm_json.py`, `knowledge/ollama_native.py`

---

## Executive summary

Session 4b validation runs are failing or producing misleading “success” because the pipeline treats **any parseable JSON** as a win, while **never inspecting Ollama’s `done_reason`**, **never continuing truncated outputs**, and giving the **semantic reviewer only 4096 tokens** on a reasoning model that spends its entire budget in `thinking`.

Three distinct failure modes were observed in production logs (not hypothetical):

| Mode | Example log | Symptom | Pipeline response |
|------|-------------|---------|-------------------|
| **Thinking budget exhaustion** | `558a7e5ad3f2.json` | `content` = 872-char stub MCU; `thinking` ≈ 49k chars ends with *"Now I'll output exactly that..."*; `done_reason: stop` | **Accepted as OK** (9 components) |
| **Hard output truncation** | `3654463beaa0.json` | `content` empty; `thinking` cut mid-JSON; `done_reason: length`; `eval_count: 16384` | Should retry on parse fail — **run may not have completed attempt 2** |
| **Semantic reviewer truncation** | `2ee7bbcf5034/cc055f242a27.json` | `content` empty; `thinking` hits 4096; `done_reason: length` | **No retry** → `JSON inválido` |
| **Pin enumeration hallucination** | `ae86f93ab97c.json` | Valid JSON with MCU pins `1`–`1000` all `NC`; `done_reason: stop` | **Accepted as OK** — no semantic validation |

Aggregate over 22 `knowledge/data/llm_sessions/sessions/**/*.json` call logs at time of review:

- `done_reason: "length"` → **10 calls**
- **empty `content`** → **10 calls** (near 1:1 with `length`)
- `"attempt": 2` → **1 call** (only `validate_20260705_192012_.../e84d0a200d77.json`)

There is **no multi-turn continuation** anywhere in the codebase.

---

## Evidence: `esp32_sensors` run (`validate_20260706_182955_b47ed4ea`)

### Circuit generation (`558a7e5ad3f2`)

```
content len:     872
thinking tail:   ...{"etype":"MCU","value":"ESP32","label":"MCU"},...]}
                 Now I'll output exactly that, without any markdown...
done_reason:     stop
eval_count:      14974 / max_tokens 16384
attempt:         1
```

Parsed circuit saved to `esp32_sensors.json` — MCU component has **no `pins`**, only:

```json
{"etype": "MCU", "value": "ESP32", "label": "MCU"}
```

Pin coverage correctly flags ESP32 as unmatched; OLED/BME280 at 100%.

**Root cause:** With `think: low` on `qwythos-9b-96k`, `num_predict` is shared between `thinking` and `content`. The model “finished” (`stop`) after planning the full circuit in `thinking`, but emitted a minimal stub in `content`. Because the stub is **valid JSON**, `circuit_synthesizer.generate_circuit_json()` does not enter the JSON-decode retry path.

### Semantic review (`2ee7bbcf5034/cc055f242a27` — same run, reviewer session)

Reviewer input shows the broken netlist the synthesizer accepted:

```
- ? (MCU): value=ESP32, n1=?, n2=?
```

```
content len:     0
thinking len:    ~4096 (truncated mid-sentence)
done_reason:     length
max_tokens:      4096
attempt:         0 (semantic_reviewer does not pass attempt meta)
```

Terminal output: `Semantic review ERROR: LLM devolvió JSON inválido`

**Root cause chain:** stub MCU → reviewer netlist incomplete → long reasoning → budget exhausted before any JSON reaches `content`.

### Stepper generation (`3654463beaa0` — same run)

```
content len:     0
thinking tail:   ..."footprint":"Module   (cut mid-string)
done_reason:     length
eval_count:      16384 (= max_tokens)
attempt:         1
```

True hard cap. Incomplete JSON exists only in `thinking`, not `content`. Manifest shows only this one call for steppers (no `attempt: 2` logged) — either the run was interrupted before retry or retry never fired.

---

## Evidence: prior run (`validate_20260706_180421_48b2fa28`)

### `ae86f93ab97c.json` — 1000-pin MCU (not truncation)

- `content` = 11,876 chars, **valid JSON**, `done_reason: stop`
- MCU `pins` map runs `"1"` … `"1000"`, nearly all `"NC"`
- `PINOUTS RELEVANTES` in that call included **SSD1306 + BME280 only** — no ESP32 pin table
- Prompt **FIDELIDAD DE PINES** + golden example (39 pins) pushed the model to “declare everything” without an authoritative ESP32 table → runaway enumeration

`_normalize_unconnected_pins()` would rewrite 1000 `NC` entries into `NC_U1_1` … `NC_U1_1000` unique nets — electrically wrong and token-wasteful.

### `99efeb5bbbf5.json` — healthy case

- `thinking` ends with *"Now I'll produce the final answer"* — same end-of-thinking phrase pattern
- `content` contains complete, well-formed stepper JSON (39 ESP32 pins)
- Demonstrates the thinking tail text is **not** a reliable failure signal by itself

---

## How truncation is handled today (code audit)

### 1. Transport retries only (`llm_client.py`)

`MAX_RETRIES` (default 2) retries **HTTP/connection errors**, not truncated generations. Each `chat()` call is a **single turn** (`system` + `user` → one response). No “continue from offset” logic exists.

### 2. Circuit synthesizer — one application retry (`circuit_synthesizer.py`)

Retry (`attempt: 2`) triggers **only** on `json.JSONDecodeError` from `parse_json_object()`:

- Does **not** check `raw.done_reason`
- Does **not** reject semantically incomplete circuits (stub MCU)
- Does **not** reject absurd pin counts
- Does **not** fall back to `thinking` when `content` is empty but thinking contains parseable JSON

Session 2 added `logger.get_context()` injection into the retry prompt — useful, but retry rarely fires.

### 3. Semantic reviewer — no retry (`semantic_reviewer.py`)

Single shot. `max_tokens: 4096` (from `Pulse_cfg.json` → `llm.agents.semantic_reviewer.max_tokens`). No `done_reason` check. No thinking-disabled path for review.

### 4. `done_reason` logged, never acted on (`ollama_native.py`)

Ollama returns `done_reason: "stop" | "length"` in `output.raw`. Nothing downstream reads it.

### 5. JSON extraction (`llm_json.py`)

`extract_json_text()` strips `` blocks and greedy-matches `{...}` from **`content` only**. It does not consult `thinking`. For native API, thinking is a separate field — good — but empty `content` still fails.

### 6. Input-side truncation (Session 3 fix — separate concern)

`_compact_pinout(full=True)` and `prompt_max_chars` cap **prompt** size. That fix is working for pinout **injection**; this review is about **output** truncation and acceptance logic.

---

## Why logs show ≤2 checkpoints

| `attempt` value | Caller | Meaning |
|---------------|--------|---------|
| `0` | `semantic_reviewer` | Default — not passed in meta |
| `1` | `circuit_synthesizer` | First generation call |
| `2` | `circuit_synthesizer` | JSON parse retry only |

No turn 3, no continuation checkpoints, no resume-from-truncation.

---

## Impact on Session 4b

The A/B experiment (`prompt_vs_rag_balance.md`) uses `validate_complex_apps.py` quality signals:

- **Pin Coverage Fidelity** — can read 100% on peripherals while MCU is stubbed (182955 run)
- **Semantic review issue counts** — fail entirely when reviewer truncates
- **Run duration** — 793s generation + 196s failed review for a misleading “success”

Until output guardrails exist, A/B comparisons will confound **prompt/RAG changes** with **LLM budget / reasoning-model behavior**.

---

## Recommended mitigations (priority order)

### P0 — Unblock validation

1. **Check `done_reason`** in `circuit_synthesizer` and `semantic_reviewer` after every call. Treat `length` as failure; optionally treat `stop` + empty `content` as failure.
2. **Raise `semantic_reviewer.max_tokens`** to at least `8192`–`16384`, or route review through `atomic` backend with `think: none` / `json_mode: true`.
3. **Post-parse semantic validation** in `generate_circuit_json()`: for any `MCU`/`IC` where pinout context was injected, require non-empty `pins` (or `unconnected_pins`) before accepting attempt 1.

### P1 — Recover truncated outputs

4. **Thinking fallback:** if `content` is empty/invalid and `thinking` contains a complete `{ "circuit": [...] }` or `{ "issues": [...] }`, try `parse_json_object(thinking)` before failing.
5. **Continuation turn (new):** on `done_reason: length` with partial JSON in `content`, send a second user message: *"Continue the JSON from exactly where you stopped. No prose."* Cap at 1–2 continuations.

### P2 — Prevent runaway pin tables

6. **Pin count guard:** after parse, if any component has `len(pins) > N` (e.g. 64) and `N` exceeds known symbol pin count from `symbols_index.json` / `pinouts_library.json`, reject and retry with a corrective prompt.
7. **Tighten FIDELIDAD DE PINES prompt:** when no full pin table is in `PINOUTS RELEVANTES`, instruct model to declare **only used pins + explicit `unconnected_pins` array**, not enumerate to 1000.

### P3 — Observability

8. Log `done_reason`, `eval_count`, `content_len`, `thinking_len` in `record_llm_exchange` top-level fields (not only buried in `raw`).
9. Add `tests/test_llm_truncation_guards.py` with fixture responses for each failure mode.

---

## Files to change (when implementing)

| File | Change |
|------|--------|
| `knowledge/circuit_synthesizer.py` | `done_reason` check, semantic validation, optional thinking fallback / continuation |
| `knowledge/semantic_reviewer.py` | `done_reason` check, retry or higher budget, disable thinking |
| `knowledge/llm_json.py` | Optional `parse_json_object_from_llm_result(content, thinking)` |
| `knowledge/llm_client.py` | Optional `chat_continue()` helper |
| `knowledge/llm_session_log.py` | Surface truncation metadata |
| `Pulse_cfg.json` | `semantic_reviewer.max_tokens`, possibly separate `num_predict` for thinking vs content if Ollama supports it |
| `docs/calibration_forge/evaluation_metrics.md` | Document “generation accepted but MCU incomplete” as a distinct failure class |

---

## Session log index (reviewed)

| Session ID | Call ID | Caller | Result |
|------------|---------|--------|--------|
| `validate_20260706_182955_b47ed4ea` | `558a7e5ad3f2` | circuit_synthesizer | Stub MCU, accepted |
| `validate_20260706_182955_b47ed4ea` | `3654463beaa0` | circuit_synthesizer | `length`, empty content |
| `validate_20260706_182955_b47ed4ea` | (reviewer) | semantic_reviewer | `length`, empty content |
| `validate_20260706_180421_48b2fa28` | `ae86f93ab97c` | circuit_synthesizer | 1000-pin hallucination |
| `validate_20260706_180421_48b2fa28` | `99efeb5bbbf5` | circuit_synthesizer | Healthy stepper JSON |

---

## Addendum (06-jul-2026, evening — independent re-audit during the live A/B run)

Two precisions to the code audit above, plus status of mitigations that already landed (full detail in [`llm_output_pipeline.md`](./llm_output_pipeline.md) §Auditoría de código adicional):

1. **`done_reason` availability is path-dependent.** Section "4. `done_reason` logged, never acted on" is accurate for the **native** path only. On the **OpenAI path** (`LLMClient._chat_openai()` — the only path the `atomic` backend can use), `choice.finish_reason` is discarded and no `raw` is returned, so there is nothing to act on even if downstream code wanted to. Session 4c must normalize both paths into one field before any guardrail can be trusted across backends.
2. **A partial thinking-fallback already exists.** Section 5 says extraction "does not consult `thinking`" — true for `llm_json.py`, but `_chat_openai()` itself already copies `msg.thinking`/`msg.reasoning` into `content` when content is empty. The native path (where all of today's failures occurred) has no such fallback. The P1 mitigation should unify these, not add a third behavior.

**Mitigations already landed (06-jul harness session, before Session 4c):** `rag_top_k` 0.95→1 fix + clamp warning; A/B variant toggle + `--variant`; `semantic_review` counts + `ab_variant` persisted in run manifests; reviewer switched from raw `json.loads` to `parse_json_object()` (tolerates fenced/prose-wrapped JSON — does NOT fix the empty-content truncation, which remains 4c P0); UTF-8-safe harness output (the `UnicodeEncodeError` crash on `Ω` in run `180421` is fixed); embed-input clipping (`llm.embed.max_prompt_chars`) unblocking `build_embed_index`.

*Review authored 06-jul-2026 from live session logs and code audit. Implementation tracked in [`llm_output_pipeline.md`](./llm_output_pipeline.md) (Sessions **4c**, **4d**). Update this doc when mitigations land.*
