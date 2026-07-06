# Auditoría: funcionalidades construidas pero inactivas ("dormant features")

> Parte de [Calibration Forge](./index.md) · Referenciado desde [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §4.4

## Objetivo de este documento

Durante la revisión de julio se encontraron dos piezas de infraestructura **completamente implementadas** pero **no conectadas al flujo real** del sistema. A diferencia de los hallazgos 4.1-4.3 (bugs o límites activos que degradan resultados), estos son casos de "trabajo ya hecho que no se está aprovechando" — de menor esfuerzo para cerrar, y potencialmente rápidos de activar.

## 1. `PulseLogger` (`core/logger.py`)

### Estado
Implementado exactamente según la especificación de [`logging_strategy.md`](./logging_strategy.md): singleton, niveles `DEBUG/INFO/WARNING/ERROR/AI_REVIEW`, buffer circular `deque(maxlen=200)` para contexto de IA, salida a `logs/pulse_forge.log`.

### Evidencia de desconexión
Búsqueda de uso en el repo (`PulseLogger`, `from core.logger`, `core.logger`) solo encuentra:
- `core/logger.py` (la propia implementación)
- `tests/test_import_esp32.py` (un test aislado)
- `docs/calibration_forge/logging_strategy.md` y `docs/roadmap.md` (documentación)

**No está importado** en `bridge/pcb_layout.py`, `bridge/gerber_export.py`, `knowledge/circuit_synthesizer.py`, `knowledge/semantic_reviewer.py`, `ui/forge_controller.py`, ni `ui/editor.py` — es decir, en ninguno de los módulos que `logging_strategy.md` identifica como fuente de eventos relevantes (colocación, ruteo, DRC, decisiones de IA).

### Por qué importa
El caso de uso principal descrito en `logging_strategy.md` — inyectar el buffer de contexto reciente (`get_context()`) en el prompt de la LLM cuando hay un error o duda — **no puede funcionar hoy** porque nada está escribiendo en ese buffer. Es una pieza de la visión de "IA-aware logging" que está a mitad de camino: existe el receptor pero no los emisores.

### `docs/roadmap.md` seguía marcando esto como pendiente
El roadmap listaba `[ ] **PulseLogger**: Unified debug sink for simulation and layout events.` como no hecho, cuando en realidad el *sink* está construido — lo que falta es la instrumentación aguas arriba. Corregido en esta sincronización (ver commit) para reflejar el estado real: sink implementado, integración pendiente.

### Próximos pasos propuestos
1. Instrumentar `bridge/pcb_layout.py::autoroute()` con `logger.debug("pcb_layout", ...)` en cada intento de A* fallido/exitoso — es justo el caso de uso que `logging_strategy.md` menciona explícitamente ("DEBUG: Detalles del algoritmo A*").
2. Instrumentar `knowledge/circuit_synthesizer.py` y `knowledge/semantic_reviewer.py` con `logger.ai_review(...)` en cada llamada LLM relevante.
3. Una vez instrumentado, conectar `logger.get_context()` como contexto adicional inyectable en `_build_system_prompt()` cuando haya un retry por JSON inválido — cerraría el loop de "AI Context Buffer" descrito en la estrategia original.

## 2. Loop de experiencia de diseño (`knowledge/design_experience.py`)

### Estado
`DesignExperience` (dataclass), `record_design_outcome()`, y `ingest_to_rag()` están completos y siguen fielmente la propuesta original de `docs/reviews/pulselab_review_23042026.md` §5.3.

### Evidencia de desconexión
El código está referenciado desde `bridge/gerber_export.py` y `ui/forge_controller.py` (confirmado por búsqueda de `record_design_outcome`/`DesignExperience(`), pero:

```
knowledge/experiences/*.json → 0 archivos
```

A pesar de que ya se han generado y exportado varias placas con éxito hoy mismo (`esp32_usb_devkit_test`, `esp32_v2`, ejemplos de `bridge_pcb`), **ningún diseño ha producido todavía un registro de experiencia**. El loop de retroalimentación descrito en `docs/baseline_report.md` ("Phase 5: `design_experience.py` hooked to Forge + Gerber DRC") está *conectado* pero no *disparándose*, o está fallando silenciosamente.

### Por qué importa
Este es precisamente el mecanismo que debería, con el tiempo, reducir la necesidad de reglas fijas en el prompt (ver `prompt_vs_rag_balance.md`, propuesta 3) — lecciones aprendidas de diseños reales, alimentadas de vuelta al RAG. Si nunca se llena, esa vía de mejora simplemente no existe en la práctica, aunque el código sugiera lo contrario.

### Próximos pasos propuestos
1. Revisar el punto exacto de invocación en `bridge/gerber_export.py` / `ui/forge_controller.py`: ¿se llama solo en un flujo de UI interactivo que no se ha ejercitado, o hay una excepción silenciosa (`try/except` que traga el error)?
2. Añadir logging (ver punto 1 de `PulseLogger` arriba) alrededor de la llamada a `record_design_outcome()` para confirmar si se está invocando y fallando, o si simplemente nunca se alcanza esa línea.
3. Ejercitar manualmente el flujo completo (generar → exportar Gerbers → verificar que aparezca un archivo en `knowledge/experiences/`) como parte de `knowledge/calibration_run.py`, para que quede cubierto por la suite de calibración existente y no dependa de descubrimiento manual.
4. Una vez confirmado que genera datos, verificar que `ingest_to_rag()` efectivamente entra a `ElectronicsKnowledgeBase` como `chunk_type="design_experience"` y aparece en `kb.stats()["by_type"]`.

## 3. Duplicidad de documentos de arquitectura

No es código dormido, pero es el mismo patrón de "trabajo hecho en dos lugares sin reconciliar": `docs/Architecture.md` + `docs/Architecture_violations.md` (raíz de `docs/`) vs. `docs/architecture/APP_ARCHITECTURE.md` + `docs/architecture/ARCHITECTURE_VIOLATIONS.md` (subcarpeta). Contenido relacionado pero no idéntico — por ejemplo, solo la versión de raíz menciona el autorouter A*, y solo la de subcarpeta menciona el sistema de temas "Cyber Night". Recomendado: decidir cuál es la fuente de verdad (sugerencia: la subcarpeta `docs/architecture/`, por convención con el resto de `docs/calibration_forge/` y `docs/workflows/`) y fusionar o eliminar la duplicada, dejando un stub que redirija.

## Resumen de acciones de sincronización ya aplicadas en este ciclo

- `docs/roadmap.md`: `PulseLogger` marcado como implementado (sink), con nota de integración pendiente.
- `FORGE_STATUS.md`: conteo de MCP tools corregido (23 → 31); "Próximos Pasos" actualizado con lo ya resuelto.
- `docs/calibration_forge/index.md`: fecha de actualización y milestones sincronizados; enlaces a los nuevos documentos de investigación añadidos.
- `docs/reviews/pulselab_review_23042026.md`: banner añadido señalando que fue superado por `pulselab_review_05072026.md`, sin alterar el contenido histórico.

## Resultado (sesión de wiring, 06-jul-2026)

### Drift check

Confirmado contra el código real antes de tocar nada: `PulseLogger` seguía sin
importadores reales (solo `tests/test_import_esp32.py`), y `knowledge/experiences/`
no existía en disco (0 archivos). El diagnóstico de este documento seguía siendo
exacto — se procedió según el alcance original.

### Causa raíz real de `knowledge/experiences/` vacío (confirmada, no solo hipotetizada)

Se probó `DesignExperience.save()` y `ElectronicsKnowledgeBase().ingest_text(chunk_type="design_experience")`
de forma aislada — ambos funcionan sin excepción. El código de `design_experience.py`
no tenía ningún defecto. La causa raíz real tenía **dos partes independientes**:

1. **El código instrumentado nunca se ejercitaba en los flujos probados/automatizados.**
   `bridge/gerber_export.py::generate_all_manufacturing_files()` (donde vive el hook
   de `record_design_outcome()`) solo se invoca desde: `ui/forge_controller.py::export_gerbers()`
   (botón GUI manual), `mcp_server/server.py` (tool MCP, uso agéntico), y
   `examples/export_all_boards.py` (script standalone). Es una **acción separada**
   de "Generar PCB" — `bridge/forge_api.py::generate_pcb()` solo construye el
   `.kicad_pcb`, nunca llama a exportación de Gerbers. Ni `knowledge/validate_complex_apps.py`
   (solo ejercita síntesis LLM, nunca construye un PCB), ni `knowledge/calibration_run.py`
   (solo valida un `.kicad_pcb` ya existente), ni `tests/test_forge.py` (llamaba a
   `bridge.export_gerbers()` de `KiCadBridge`, un método distinto que evita
   `gerber_export.py` por completo) alcanzaban jamás la ruta instrumentada. Esto confirma
   exactamente la hipótesis #2 original: "a code path that's never actually reached in
   the tested flows".
2. **Defecto real adicional encontrado (no documentado originalmente):** `DesignExperience.ingest_to_rag()`
   instanciaba una `ElectronicsKnowledgeBase()` **nueva y desechable** en cada llamada.
   Esa instancia nunca se persistía — no existía un equivalente a `_load_training_examples()`
   que releyera `knowledge/experiences/*.json` al construir una `ElectronicsKnowledgeBase()`
   nueva. Es decir: incluso si `record_design_outcome()` se hubiera ejecutado con éxito,
   el chunk `design_experience` solo habría existido en memoria durante la vida de esa
   instancia desechable — una `kb.stats()` en el siguiente proceso habría seguido
   mostrando 0. Este era el gap que impedía que el loop "produjera datos" de forma
   durable, más allá de que se alcanzara la línea de código o no.
3. **Bug secundario confirmado:** ambos call sites (`bridge/gerber_export.py` L242-255,
   `ui/forge_controller.py` L140-157) envolvían la llamada en `except Exception: pass`
   desnudo — cualquier fallo transitorio se habría tragado en silencio incluso una vez
   alcanzada la ruta.

### Instrumentación aplicada (PulseLogger)

`from core.logger import logger` añadido a los 5 módulos identificados por
`logging_strategy.md` + los dos call sites de `record_design_outcome()`:

- `bridge/pcb_layout.py::autoroute()`: `logger.debug` por cada intento A* (éxito con
  nodos explorados + longitud de path, o fallo tras N nodos explorados — el caso de uso
  explícito de "DEBUG: Detalles del algoritmo A*"), `logger.warning` por segmento sin
  rutear, `logger.info`/`logger.warning` de resumen al finalizar.
- `bridge/gerber_export.py::generate_all_manufacturing_files()`: `logger.info` en cada
  paso (DRC, gerbers, drill, position, svg) y su resultado; `logger.error` en fallos;
  el `except Exception: pass` alrededor de `record_design_outcome()` ahora hace
  `logger.error(...)` con el mensaje real de la excepción.
- `knowledge/circuit_synthesizer.py::generate_circuit_json()`: `logger.ai_review` al
  iniciar, en cada reintento de parseo JSON, y al finalizar con éxito; `logger.error`
  en fallos de LLM o crashes.
- `knowledge/semantic_reviewer.py`: `logger.ai_review` con conteo de issues (y críticos)
  en `SemanticAIAgent.analyze_circuit()` y `SemanticReviewer.review_netlist()`;
  `logger.error` en fallos de LLM/JSON.
- `ui/forge_controller.py::gen_pcb()`: el `except Exception: pass` restante ahora usa
  `logger.error(...)`.

`core/logger.py` no se modificó — coincide con la especificación de
`logging_strategy.md` y no se encontró ningún defecto real en él.

### Fix de persistencia (`knowledge/rag_engine.py`)

Se añadió `ElectronicsKnowledgeBase._load_experiences()` (modelado sobre
`_load_training_examples()`), llamado desde `_load_default_data()`: lee
`knowledge/experiences/*.json` y reconstruye `lessons_learned` /
`component_placement_rules` como chunks `chunk_type="design_experience"`. Esto es lo
que hace que el loop produzca datos **durables**, no solo un acierto de un único
proceso.

### Verificación end-to-end

Nuevo test `tests/test_forge.py::test_design_experience_loop()` (se salta si KiCad no
está disponible, igual que `test_pcb_kicad_export`): construye un PCB pequeño, llama a
`generate_all_manufacturing_files()` directamente, confirma que aparece
`knowledge/experiences/<board_id>.json`, y confirma que una instancia **nueva** de
`ElectronicsKnowledgeBase()` (simulando un proceso nuevo) reporta
`stats()["by_type"]["design_experience"] > 0`. Limpia sus propios artefactos al
finalizar. Verificado: `python tests/test_forge.py` → 9/9 PASS,
`python tests/test_rag_retrieval.py` → 5/5 PASS.

También se ejercitó manualmente el flujo real una vez (ver log de
`test_design_experience_loop`): `generate_all_manufacturing_files()` con DRC OK generó
correctamente `knowledge/experiences/_test_design_experience_loop.json`, que el test
limpia automáticamente.

### Duplicidad de registro observada (no es un bug, es un hallazgo a documentar)

`ui/forge_controller.py::gen_pcb()` registra una `DesignExperience` inmediatamente tras
generar el PCB+firmware (evento "PCB generado"), y si el usuario más tarde pulsa
"Exportar Gerbers" por separado, `generate_all_manufacturing_files()` registra una
**segunda** experiencia independiente (evento "DRC/fabricación"). Son eventos de
ciclo de vida distintos — se deja documentado para que no se interprete como un bug
en una futura sesión.

### POC: migración de una regla hardcodeada a `DesignExperience`

Como preparación explícita para `prompt_vs_rag_balance.md` (propuesta #3), se creó
`knowledge/seed_poc_experience.py` (idempotente, ejecutable con
`python -m knowledge.seed_poc_experience`) que migra la regla "ESP32 EN necesita
pull-up 10k a 3.3V" (hardcodeada en `circuit_synthesizer.py` base prompt y en
`semantic_reviewer.py` `_SYSTEM_PROMPT` regla #5) a un `DesignExperience.lessons_learned`,
la persiste en `knowledge/experiences/poc_esp32_en_pullup_rule.json`, y confirma que es
recuperable vía `kb.query(..., chunk_type="design_experience")` desde una instancia
**nueva** de KB. Verificado: la lección aparece como 3er resultado en
`test_rag_esp32_component` (`tests/test_rag_retrieval.py`) sin cambio alguno en ese
test — prueba que el chunk se mezcla naturalmente con el retrieval existente.

**Importante:** esto es solo una prueba de concepto del mecanismo de recuperación. La
regla **no se eliminó** de los prompts de `circuit_synthesizer.py` /
`semantic_reviewer.py` — esa decisión requiere el experimento A/B de
`prompt_vs_rag_balance.md`, que queda fuera del alcance de esta sesión.

### Gaps restantes

- El "AI Context Buffer" completo (inyectar `logger.get_context()` en reintentos) se
  implementó como tarea opcional — ver `circuit_synthesizer.py::generate_circuit_json()`,
  rama de reintento tras `json.JSONDecodeError` (últimas 20 líneas del buffer).
- No se instrumentó cada módulo de `knowledge/` exhaustivamente — solo los 4 que
  `logging_strategy.md` y esta auditoría señalaban explícitamente, más los 2 call
  sites de `record_design_outcome()`.
- El experimento A/B de `prompt_vs_rag_balance.md` (propuesta #3, retirar/reemplazar
  reglas hardcodeadas) sigue pendiente — esta sesión solo deja la evidencia de que el
  mecanismo de recuperación funciona.
