# Verificación independiente: estado del sprint y smells arquitectónicos (06-jul-2026, tarde)

> Este documento verifica, línea por línea contra el código y el estado real del repo, un análisis externo recibido sobre qué sesión pendiente es más difícil (4b vs 5 vs "Modelo Multipin") y qué smells arquitectónicos son más relevantes. Método: lectura directa de los archivos citados, más ejecución en vivo de `ElectronicsKnowledgeBase()` y `pytest` para números que el análisis original no pudo medir (solo inspeccionó código estático). Todo lo de abajo es lo que se confirmó, corrigió o amplió — no es una repetición del análisis original.
>
> Fuentes primarias re-leídas para esta verificación: `CURENT_SPRINT.md`, `Pulse_cfg.json`, `docs/calibration_forge/index.md`, `docs/calibration_forge/prompt_vs_rag_balance.md`, `docs/calibration_forge/kicad_symbol_kb.md`, `knowledge/circuit_synthesizer.py`, `knowledge/semantic_reviewer.py`, `knowledge/rag_engine.py`, `knowledge/design_experience.py`, `knowledge/validate_complex_apps.py`, `knowledge/kicad_schematic_parser.py`, `knowledge/kicad_symbol_parser.py`, `presets/esp32_usb_devkit.py`, `ui/forge_controller.py`, `FORGE_STATUS.md`, `docs/architecture/SEGURIDAD_DEPENDENCIAS.md`, `requirements.txt`, `.gitignore`.

## Veredicto ejecutivo

El análisis externo es **mayoritariamente correcto y bien evidenciado** — casi todas las citas de línea, valores de config y descripciones de comportamiento se confirmaron exactas contra el código actual (no el snapshot de hace un día). Dos correcciones de hecho y varias ampliaciones cuantitativas se detallan abajo. El hallazgo más importante del análisis (`rag_top_k: 0.95` → `int()` → `0`) se **confirmó como bug real, activo, y no documentado en ningún doc de sesión existente** — esto es nuevo información, no solo verificación, y cambia el plan de Session 4b (ver §Acciones antes de 4b).

## 1. Estado de sesiones — confirmado, con una corrección de matiz

| Claim original | Verificado |
|---|---|
| Sesiones 1–3: Done | ✅ Confirmado — `index.md` líneas 9-11, headers con ✅ en `CURENT_SPRINT.md`. |
| 4a: "Done (nota: el header de sección aún no tiene ✅, solo el resumen superior dice completado)" | ✅ **Exacto.** `CURENT_SPRINT.md` línea 272: `### Session 4a — KiCad Symbol Knowledge Base (parser + index + RAG pinout unification)` — sin ✅, a diferencia de Sesiones 1-3 y a diferencia del propio párrafo de resumen en la línea 13 que sí dice "Session 4a completed 06-jul-2026". Corregido en este documento (ver §Acciones). |
| 4b: Next / hardest remaining | ✅ Confirmado como próxima sesión desbloqueada; ver §2 para si "hardest" sigue siendo cierto tras esta verificación (sí, y más). |
| Session 5: Pending, Low–medium | ✅ Confirmado, sin cambios de código detectados desde que se escribió `pulselab_review_05072026.md` §5. |
| "Modelo Multipin" es más grande que 5, no numerada | ✅ Confirmado — `index.md` línea 27-30 la lista bajo "Estabilización y Refactorización (Pendiente)", fuera de las seis sesiones numeradas, y su alcance (Editor + Netlist + Esquemáticos) es efectivamente más amplio que cualquier tarea de Session 5. |

## 2. Session 4b — verificación de cada punto de dificultad

### 2.1 Costo/varianza de 10 corridas LLM
No verificable sin ejecutar el experimento real; el runtime de `~7 min` para `esp32_sensors` (Session 4a, 06-jul 13:09-13:16 UTC) es consistente con los manifiestos de corridas ya en disco (`knowledge/data/validation_complex/runs/20260706_130942_.../run_manifest.json`). Aceptado como estimación razonable, sin corrección.

### 2.2 "El harness no llama a `semantic_reviewer`" — confirmado exacto

```19:22:knowledge/validate_complex_apps.py
from knowledge.circuit_synthesizer import CircuitSynthesizer
from knowledge.llm_backends import list_backends
from knowledge.llm_session_log import new_session_id
from knowledge.llm_client import get_llm_client
```

No hay `import` de `knowledge.semantic_reviewer` en todo el archivo (confirmado con grep de todo `validate_complex_apps.py`). `_pin_coverage()` es la única métrica automática; el conteo de issues de `semantic_reviewer` que Session 4b necesita como señal primaria **no existe hoy en el harness** — habría que instrumentarlo o correrlo como post-paso manual, exactamente como afirma el análisis.

### 2.3 "No existe toggle A/B" — confirmado
Búsqueda de variables de entorno o perfiles de config para alternar reglas/rag_top_k: no se encontró ningún flag (`os.environ` relacionado a "rules"/"ab_test"/similar) en `circuit_synthesizer.py`, `semantic_reviewer.py` ni `pulse_config.py`. El experimento tendría que implementarse desde cero (editar `base_system_prompt` a mano entre corridas, o parametrizar). Confirmado.

### 2.4 "El baseline documentado ya podría estar mal" — confirmado y ampliado significativamente

Esta es la parte más importante de la verificación. El análisis dice:

> "Docs still describe `rag_top_k: 1` and `temperature: 0.1`, but live `Pulse_cfg.json` has `temperature: 0.6` and `rag_top_k: 0.95`. Because the code does `int(cfg(...))`, `int(0.95) == 0`, so circuit-example RAG is effectively disabled right now."

Verificación línea por línea:

- `Pulse_cfg.json` (líneas 24-25, sección `llm.agents.circuit_synthesizer`): `"temperature": 0.6, "rag_top_k": 0.95` — **valores exactos confirmados**.
- `prompt_vs_rag_balance.md` líneas 68-75 (evidencia #3) documenta explícitamente `rag_top_k: 1` como el valor vigente al momento de escribir ese doc, y línea 97 (propuesta #5) referencia `temperature=0.1` — ambos ahora **desactualizados** frente al `Pulse_cfg.json` real.
- `circuit_synthesizer.py` línea 340 (confirmado en el archivo actual, sin drift de línea):

```338:341:knowledge/circuit_synthesizer.py
rag_results = self.rag.query(
    description,
    top_k=int(cfg("llm.agents.circuit_synthesizer.rag_top_k", 1)),
    chunk_type="circuit_example",
```

`int(0.95)` en Python trunca a `0`, no redondea — confirmado con intérprete. **Esto significa que en cada corrida de `validate_complex_apps.py` hecha hasta ahora (incluyendo las corridas de Session 3 y 4a citadas como "baseline confirmado" en `index.md` y `pin_model_coverage.md`), el ejemplo de `chunk_type="circuit_example"` nunca se inyectó** — `rag_results` es siempre `[]` porque `kb.query(..., top_k=0, ...)` devuelve una lista vacía antes de llegar a ningún filtro de score. Esto **no está mencionado en ningún §Resultado de Session 3 o 4a**, ni en `prompt_vs_rag_balance.md`, pese a que ambas sesiones citan el 100% de pin coverage como si el pipeline completo (reglas + pinouts + ejemplo RAG) estuviera activo. En realidad, todo ese 100% se logró **sin ningún ejemplo `circuit_example` de RAG en el prompt** — solo con las reglas fijas + el ejemplo dinámico de `presets/esp32_usb_devkit.py` + el pinout RAG (que no depende de este `top_k`, ver nota abajo).

  **Nota de alcance importante que el análisis original no distingue:** este bug de `int(0.95)==0` **solo afecta la inyección de `chunk_type="circuit_example"`** en `_build_system_prompt()` (línea 340). **No afecta** `_match_pinouts()` — la migración de Session 4a a `chunk_type="pinout"` calcula su propio `top_k` internamente:

```214:215:knowledge/circuit_synthesizer.py
pool_size = max(self._max_pinout_entries * 5, 10)
results = self.rag.query(description, top_k=pool_size, chunk_type="pinout")
```

  `pool_size` viene de `_max_pinout_entries` (`int(cfg(..., "max_pinout_entries", 2))`, config real = `2`), no de `rag_top_k`. Es decir: **el pinout RAG de Session 4a funciona correctamente y no está comprometido por este bug** — solo el mecanismo de "ejemplo de circuito similar" de Session 1/pre-4a lo está. Esto matiza (sin invalidar) la frase del análisis "circuit-example RAG is effectively disabled" — es precisa tal cual está escrita (dice "circuit-example", no "pinout"), pero vale la pena dejarlo explícito para que Session 4b no asuma que *todo* el RAG está roto.

- **Consecuencia directa para Session 4b:** la variante (a) "reglas actuales + `rag_top_k=1`" que describe `prompt_vs_rag_balance.md` tarea 1 **no es lo que corre hoy**. Hoy corre efectivamente "reglas actuales + `rag_top_k=0`" (cero ejemplos de circuito). Si Session 4b arranca el A/B sin arreglar esto primero, la variante (a) que se mida no será la variante (a) que el documento cree estar midiendo, y la comparación con la variante (b) ("`rag_top_k=3-5`") quedará confundida por dos cambios simultáneos (retiro de reglas + arreglo del bug de config) en vez de uno. **Confirma exactamente la alerta del análisis original, con evidencia en vivo, no solo lectura estática.**

### 2.5 "Embeddings densos obsoletos (`vectors.npy`)" — confirmado con números exactos en vivo

El análisis afirma esto por inferencia de código; se verificó ejecutando la KB real:

```
manifest chunk_count (knowledge/data/embeddings/manifest.json): 358
chunks reales cargados por ElectronicsKnowledgeBase() ahora mismo: 5685
  by_type: {'component': 10, 'support_circuit': 9, 'design_rule': 13,
            'circuit_example': 326, 'design_experience': 1, 'pinout': 5326}
embed_index_loaded: False
```

`_load_embed_cache()` compara `manifest.get("chunk_count") != len(self._chunks)` (358 vs 5685) y descarta el índice denso silenciosamente, exactamente como describe el análisis:

```356:361:knowledge/rag_engine.py
if manifest.get("chunk_count") != len(self._chunks):
    return
self._embed_matrix = np.load(_EMBED_MATRIX)
```

El backend configurado es `hybrid` (`dense_weight: 0.6, tfidf_weight: 0.4` en `Pulse_cfg.json`), pero con `embed_index_loaded=False` el motor cae a TF-IDF puro para *todo* — no solo para pinouts, sino también para `circuit_example` (cuando el bug de 2.4 se arregle) y `design_experience`. Esto es un segundo confounder independiente del bug de `rag_top_k`, y ambos afectan a Session 4b simultáneamente. **Confirmado y cuantificado exactamente** (el análisis original no tenía estos números porque no ejecutó código, solo lo leyó).

### 2.6 Duplicación de reglas en 3 capas — confirmado exacto
- `circuit_synthesizer.py` líneas 60-65 (`REGLAS UART / USB (OBLIGATORIAS)`) — confirmado, texto idéntico al citado.
- `semantic_reviewer.py` líneas 25-33 (`_SYSTEM_PROMPT`, 7 reglas numeradas) — confirmado, texto idéntico, incluye la misma regla de "ESP32 EN necesita pull-up 10k" (regla 5) y el mismo crossover CH340 (regla 7) que en `circuit_synthesizer.py`.
- `knowledge/experiences/poc_esp32_en_pullup_rule.json` — confirmado existente en el repo (aparece en `git status` como archivo nuevo de Session 2).

### 2.7 Tail de Session 4a diferido — confirmado
`kicad_symbol_kb.md` §Próximos pasos, últimos dos ítems sin marcar (líneas 207-208): deprecar `pinouts_library.json` (explícitamente decidido NO hacer, con justificación) y resolver `ESP8266_Node` contra `ESP-12F`. Ambos confirmados como abiertos, con la nota explícita de que `ESP-12F` **ya está indexado** pero nadie verificó si `ESP8266_Node` (el nombre inventado en `presets/mcu_uart.py`) resuelve contra él.

## 3. Session 5 — confirmado, con una corrección de matiz sobre `scratch/`

Todos los ítems de la tabla original se confirmaron sin cambios: `requirements.txt` sigue sin ninguna versión pinneada (10 paquetes, ninguno con `==`), `SEGURIDAD_DEPENDENCIAS.md` sigue advirtiendo sobre numpy/pygame, y los cuatro docs de arquitectura duplicados (`docs/Architecture.md`, `docs/Architecture_violations.md` vs `docs/architecture/APP_ARCHITECTURE.md`, `docs/architecture/ARCHITECTURE_VIOLATIONS.md`) siguen sin fusionar.

**Corrección de matiz:** `scratch/test_drc_fail.py` **sí existe** en el filesystem (confirmado con listado directo), pero el directorio `scratch/` está en `.gitignore` (línea 40) — por lo tanto **no está trackeado por git** pese a estar físicamente en el repo local. Esto no invalida el ítem de limpieza (sigue siendo higiene válida borrarlo del disco), pero significa que no aparecerá en `git status`/`git log` y que "sigue en el repo" debe leerse como "sigue en el checkout local", no "sigue versionado". Vale la pena que quien corra Session 5 lo sepa para no perder tiempo buscándolo con `git log --follow`.

## 4. Smells arquitectónicos — verificación punto por punto

| # | Smell | Verificado | Nota |
|---|---|---|---|
| 1 | Triple resolución de pinouts descentralizada | ✅ Exacto | Confirmadas las 3 rutas citadas y el gate de `_get_pinouts_context()` en líneas 275-277 (idénticas). El post-LLM enrichment en líneas 484-491 también confirmado exacto (solo consulta `self.pinouts_db`, nunca resultados de RAG). |
| 2 | Reglas duplicadas en 3 capas | ✅ Exacto | Ver §2.6. |
| 3 | `ElectronicsKnowledgeBase` no-singleton, se reconstruye seguido | ✅ Confirmado y ampliado | Grep confirma **9 sitios** que instancian `ElectronicsKnowledgeBase()` fresca: `circuit_synthesizer.py`, `design_experience.py` (`ingest_to_rag()`), `seed_poc_experience.py`, `build_embed_index.py`, `dataset_builder.py`, `mcp_server/server.py`, más 3 en `tests/`. `ui/forge_controller.py` línea 284 confirma `threading.Thread(target=task, daemon=True).start()` — cada generación de circuito desde la UI efectivamente reconstruye TF-IDF sobre 5685 chunks en un hilo de fondo. |
| 4 | `design_experience` split-brain | ✅ Confirmado, con matiz positivo | `DesignExperience.ingest_to_rag()` (líneas 47-67) en efecto solo toca una `ElectronicsKnowledgeBase()` desechable de módulo. **Pero** `rag_engine.py::_load_experiences()` (añadido en Session 2) sí releé `knowledge/experiences/*.json` en cada `__init__` nuevo — por lo que el dato **sí persiste** entre procesos vía disco, solo que `ingest_to_rag()` es una llamada redundante/sin efecto duradero por sí misma. El análisis ya lo enmarca correctamente ("durability depends on `_load_experiences()`... easy to regress if someone calls only `ingest_to_rag()`"), confirmado tal cual. |
| 5 | Parsers duplicados sin core S-expression compartido | ⚠️ **Corrección de hecho** | El análisis dice que ambos parsers "implementan tokenización por profundidad de paréntesis independientemente". Esto es **impreciso**: `kicad_symbol_parser.py` (Session 4a) sí implementa un tokenizer real de profundidad de paréntesis con manejo de escapes de comillas (`_find_matching_paren()`, líneas 30-60) — documentado explícitamente en `kicad_symbol_kb.md` §Resultado como necesario porque "una regex greedy/no-greedy simple se confunde con la anidación". `kicad_schematic_parser.py`, en cambio, **no tiene ningún tokenizer de profundidad** — usa regex `DOTALL` con cuantificadores perezosos (`re.findall(r'\(symbol\s+\(lib_id\s+"([^"]+)".*?\(property\s+"Reference"\s+"([^"]+)".*?\(property\s+"Value"\s+"([^"]+)"', content, re.DOTALL)`, línea 36) y regex simples para notas/labels. **La duplicación real no es "mismo patrón, dos copias" — es "un parser frágil (regex ingenua) y uno robusto (paréntesis balanceados), sin que el primero se haya beneficiado nunca del enfoque del segundo".** Esto es en realidad un smell *más* preocupante que el descrito: `kicad_schematic_parser.py` podría fallar silenciosamente ante esquemáticos reales con símbolos anidados o valores con paréntesis internos, algo que `kicad_symbol_parser.py` ya resuelve. Recomendación añadida: si se prioriza consolidar un core común, debe ser extrayendo `_find_matching_paren()`/`_extract_blocks()` de `kicad_symbol_parser.py` hacia un módulo compartido (`knowledge/kicad_sexpr.py`) y *migrar* `kicad_schematic_parser.py` a usarlo — no solo "compartir estilo". |
| 6 | Layer/coupling leaks | ✅ Confirmado, con número exacto | `circuit_synthesizer.py` líneas 116-117 confirma `from presets.esp32_usb_devkit import load as load_golden_preset`. El preset (`presets/esp32_usb_devkit.py`) define `esp_pins` con exactamente **8 entradas** (pines `1,2,3,25,24,35,34,38`) de 39 pines físicos del ESP32-WROOM-32 → **20.5% de cobertura**, confirmando el "~20%" citado con precisión (no solo aproximado). `validate_complex_apps.py` línea 266 confirma `_pin_coverage(components, synth.pinouts_db)` — acceso directo al atributo interno del sintetizador. `semantic_reviewer.py` confirma exactamente 2 clases públicas (`SemanticAIAgent`, `SemanticReviewer`) sin deprecación documentada de ninguna. |
| 7 | Fallas silenciosas de config/índice | ✅ Confirmado y cuantificado en vivo | Ver §2.4 y §2.5 arriba — con los números reales (358 vs 5685 chunks; `int(0.95)==0`) que el análisis original no pudo medir directamente. **Adicionalmente confirmado:** `FORGE_STATUS.md` línea 24 sigue diciendo `test_rag_engine ✅ 32 chunks TF-IDF` y línea 19 dice `Tests: 7/7 PASS` — corrida real de `pytest tests/` en este momento da **79 passed** (0 fallos), y la KB real tiene **5685** chunks, no 32. El doc-rot es aún mayor que "documentado como riesgo": son números concretos y verificablemente obsoletos, no solo una sospecha. |
| 8 | "Modelo Multipin" transversal, fuera de las 6 sesiones | ✅ Confirmado | `index.md` líneas 27-30, confirmado sin cambios de alcance. |

## 5. Acciones recomendadas antes de arrancar Session 4b (nuevo, derivado de esta verificación)

Estas no estaban en el análisis original como lista accionable — se derivan directamente de los números confirmados en vivo arriba:

1. **Arreglar `Pulse_cfg.json → llm.agents.circuit_synthesizer.rag_top_k`** de `0.95` a un entero ≥ 1 (el propio `prompt_vs_rag_balance.md` propone 3-5 para la variante (b); la variante (a) necesita al menos `1` para representar honestamente "comportamiento actual con RAG"). Sin este fix, la variante (a) del A/B mide "sin ejemplos de circuito" por accidente, no por diseño.
2. **Rebuild de `vectors.npy`** (`python -m knowledge.build_embed_index` con Ollama activo) antes de correr el A/B — el manifiesto actual (358 chunks) es de antes de Session 1; con 5685 chunks reales hoy, el índice denso está descartado al 100% del tiempo, y el "híbrido" configurado se ejecuta como TF-IDF puro sin que ningún log lo advierta.
3. **Documentar explícitamente en el handoff de 4b** que ninguna corrida de `esp32_sensors` citada como "100% pin coverage confirmado" (Session 3 y 4a) tuvo un ejemplo de `chunk_type="circuit_example"` en el prompt — el 100% se logró solo con reglas fijas + ejemplo dinámico embebido + pinout RAG. Esto es relevante porque Session 4b evaluará "reglas fijas vs. RAG más rico" y necesita saber que el "RAG" de las corridas anteriores nunca incluyó el componente de ejemplos de circuito completo, solo pinouts.
4. Considerar loguear (aunque sea un `logger.warning` de una línea) cuando `int(cfg(...))` resulte en `0` para un `top_k` que se usará en una query — habría detectado este bug en el momento en que se cambió `rag_top_k` a `0.95` en vez de silenciosamente.

## 6. Resumen de correcciones sobre el análisis original

1. **Smell #5 (parsers duplicados):** el análisis sobre-generaliza — no es "mismo patrón, dos copias", es un parser robusto (paréntesis balanceados, `kicad_symbol_parser.py`) y uno fragil (regex `DOTALL` ingenua, `kicad_schematic_parser.py`) sin que el segundo se beneficie del enfoque del primero. Ver §4 fila 5 para el detalle y una recomendación de consolidación concreta.
2. **`scratch/test_drc_fail.py`:** existe en disco pero está gitignored — no aparecerá en herramientas basadas en git (`git log`, `git status`), aunque la recomendación de limpieza sigue siendo válida.
3. **Alcance del bug `int(0.95)==0`:** afecta solo `chunk_type="circuit_example"` (línea 340), no `chunk_type="pinout"` (que usa su propio `pool_size` en línea 214, no `rag_top_k`). El análisis original no lo distingue explícitamente aunque su frase ("circuit-example RAG") ya es técnicamente correcta.

Todo lo demás en el análisis original — el ranking práctico, los ocho smells, y la conclusión de que Session 4b es la sesión más difícil pendiente — se confirma sin cambios sustanciales.
