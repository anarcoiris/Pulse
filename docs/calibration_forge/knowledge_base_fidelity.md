# Investigación: Pérdida de fidelidad en la ingesta del Knowledge Base

> Parte de [Calibration Forge](./index.md) · Referenciado desde [`pulselab_review_05072026.md`](../reviews/pulselab_review_05072026.md) §4.2
> Relacionado con [Ingesta de Referencias (Parsing)](./kicad_parsing.md) y [Investigación de Datasets](./dataset_research.md)

## Problema observado

El RAG (`knowledge/rag_engine.py`) indexa 358 chunks, de los cuales 326 son `circuit_example` provenientes de `knowledge/data/training/*.json`. Pero el texto que efectivamente se indexa para cada ejemplo es mucho más pobre que la información realmente disponible en los archivos fuente: se pierde tanto **la intención de diseño en lenguaje natural** como **cualquier anotación textual de los esquemáticos humanos**. Reemplazar TF-IDF por embeddings densos (como ya se hizo) no soluciona esto — mejora cómo se busca, no qué hay para encontrar.

Hay dos bugs/gaps independientes, cada uno con una fuente de datos distinta.

## Hallazgo 1 — El prompt original de las muestras auto-generadas se descarta al indexar

Las muestras en `knowledge/data/training/sample_*.json` (generadas por el propio `IA_Generator` del proyecto) sí contienen una descripción en lenguaje natural del circuito, capturada en el momento de creación:

```json
{
  "timestamp": "20260501_064720_181247",
  "metadata": {
    "source": "IA_Generator",
    "prompt": "RLC con LED, funcionando como receptor de pulsos o RF para encender el LED por induccion"
  },
  "circuit": { "components": [ /* 18 componentes */ ], "wires": [] }
}
```

Pero `_summarize_circuit_data()` en `knowledge/rag_engine.py` construye el texto indexado así:

```106:123:knowledge/rag_engine.py
def _summarize_circuit_data(data: dict) -> str:
    """Build searchable text from a training/ingested circuit dict."""
    circuit = data.get("circuit", data)
    parts = [data.get("source", ""), data.get("original_file", "")]
    if isinstance(circuit, dict):
        comps = circuit.get("components", [])
        if comps:
            for c in comps[:40]:
                parts.append(
                    f"{c.get('etype', '?')} {c.get('label', c.get('uid', ''))} "
                    f"{c.get('value_raw', c.get('value', ''))} {c.get('lib_id', '')}"
                )
        else:
            parts.append(_text_from_dict(circuit)[:2000])
    ...
```

`data.get("source", "")` busca la clave `source` **en la raíz** del JSON. En las muestras auto-generadas esa clave no existe en la raíz — está anidada en `metadata.source`, y el campo más valioso, `metadata.prompt`, **no se lee en absoluto**. El resultado es que el chunk indexado para este ejemplo es solamente:

```
V PSU 5kV 5000.0  S S1 Carga 0.0  R R_lim 10kΩ 10000.0  C C 0.6µF ...
```

— una bolsa de etiquetas y valores, sin ninguna palabra de "RF", "pulso", "inducción" o "receptor", que son justamente los términos por los que un usuario buscaría este ejemplo. Es un bug puntual y acotado: dos claves mal indexadas, no una limitación de arquitectura.

## Hallazgo 2 — El parser de esquemáticos KiCad humanos nunca captura texto/anotaciones

Para los ~280 archivos `human_*.json` (mayoritariamente `KiCad_kicad-source-mirror_*`, mirror de esquemáticos reales de KiCad), la extracción ocurre en `knowledge/kicad_schematic_parser.py`:

```25:60:knowledge/kicad_schematic_parser.py
def parse_schematic(self, file_path: str) -> dict:
    content = Path(file_path).read_text(encoding="utf-8")
    symbol_blocks = re.findall(
        r'\(symbol\s+\(lib_id\s+"([^"]+)".*?\(property\s+"Reference"\s+"([^"]+)".*?\(property\s+"Value"\s+"([^"]+)"',
        content, re.DOTALL,
    )
    components = []
    for lib_id, ref, value in symbol_blocks:
        ...
    return {"source": Path(file_path).name, "components": components, "version": "1.0"}
```

Esto explica el resultado observado en, por ejemplo, `knowledge/data/training/human_scottbez1_splitflap_sensor_smd_kicad_sch.json`: 13 componentes, cada uno con solo `{uid, etype, value, value_raw, label, lib_id}`. La clase documenta esta limitación en su propio docstring ("Extraer la topología (nets) de esquemáticos... requiere análisis geométrico de los cables, por lo que nos enfocamos en los componentes y valores como base"), pero eso deja fuera:

- `(title_block (title ...) (comment ...))` — en muchos esquemáticos reales de KiCad esto contiene una descripción del propósito de la hoja/circuito.
- `(text "...")` — notas de diseño libres que los autores dejan en el esquemático (ej. "cuidado con polaridad", "footprint alternativo si no hay stock").
- `(label ...)` / `(hierarchical_label ...)` / `(global_label ...)` — nombres semánticos de red (`I2C_SDA`, `USB_DP`, `VBUS_5V`) que son oro puro para retrieval semántico y que hoy se descartan por completo.
- Conectividad real vía `(wire ...)` — sin esto, cada ejemplo recuperado es literalmente una lista desordenada de piezas sin relación entre sí.

## Por qué importa

- El usuario intuía correctamente: el sistema **sí recolectó** buena información (metadata de intención, potencialmente notas de diseño en los esquemáticos fuente), pero la **tira en el camino de ingesta**. No es un problema de "hace falta más data" — es un problema de "la data que ya tenemos se procesa con pérdidas".
- Esto degrada exactamente la pieza que iba a resolver el punto 4.3 (`prompt_vs_rag_balance.md`): si el RAG recupera ejemplos sin contexto de intención, el sistema seguirá dependiendo de reglas fijas en el prompt porque el RAG no aporta suficiente señal.
- Cuantitativamente: de 326 chunks `circuit_example`, un número no determinado pero probablemente significativo pierde su única pista de intención de diseño (los `sample_*.json` con `metadata.prompt`); los `human_*.json` (la mayoría, ~280) nunca tuvieron esa pista extraída aunque podría existir en el `.kicad_sch` original.

## Líneas de investigación / próximos pasos propuestos

1. [x] **Fix inmediato y de bajo riesgo en `_summarize_circuit_data()`:** … — **Implementado y verificado** (05-jul-2026).

2. [x] **Extender `KiCadSchematicParser`** … — **Implementado** (parser v1.1 + self-test PASS). Parser geométrico de `wire` **sigue fuera de alcance**.

3. [x] **Re-ingestar el corpus existente** … — **Ejecutado**: 320/320 `human_*.json` regenerados desde `knowledge/data/raw_kicad/`; backup en `knowledge/data/training_backup_20260705/`.

4. [x] **Añadir comprobación de "densidad de descripción"** … — **Implementado y medido**: ratio **0.8006** (261/326) post-fix.

5. [ ] **Auditar `_chunk_component()` y `_chunk_ipc()`** … — **No hecho**, fuera de alcance.

## Resultado (sesión de fix, 05–06-jul-2026)

### Implementación (código)

- **`knowledge/rag_engine.py::_summarize_circuit_data()`**: lee `metadata.prompt` (`design_intent: …`), `metadata.source` como fallback, y `description`/`notes`/`net_labels` del parser — todos *antes* de la rama de componentes.
- **`knowledge/kicad_schematic_parser.py`**: extrae `description`, `notes` (filtradas ≤2 chars), `net_labels` (dedup, cap 60); schema `"1.1"`. Self-test en `__main__` contra `usb_dp.kicad_sch`.
- **`ElectronicsKnowledgeBase.stats()`**: `circuit_example_description_density` vía marcadores literales (`design_intent:`, `description:`, `notes:`, `nets:`).
- **`tests/test_rag_retrieval.py`**: nuevo `test_rag_design_intent_retrieval` para el ejemplo RLC/RF.

### Ejecución verificada (06-jul-2026, Windows + Python 3.12.10)

| Paso | Resultado |
|------|-----------|
| Backup `training/` → `training_backup_20260705/` | 320 `human_*.json` preservados |
| `python -m knowledge.kicad_schematic_parser` | **Self-test: PASS** — 100 componentes, 59 net_labels, description "Antmicro Baseboard…", notes incl. "USB Display port alt mode" |
| `python -m knowledge.dataset_builder` | **320 muestras** regeneradas (requiere `$env:PYTHONIOENCODING='utf-8'` en Windows por emojis en prints del builder) |
| `python -m knowledge.build_embed_index` | **Ollama no disponible** (`WinError 10061`); índice denso previo en disco sigue cargado; TF-IDF re-entrenado al cargar KB |
| `python -m knowledge.rag_engine` | `total_chunks=358`, `circuit_example_description_density: {total: 326, with_description: 261, ratio: 0.8006}` |
| `python tests/test_rag_retrieval.py` | **5 passed, 0 failed** (antes: 3 passed, 1 failed) |

### Mejora de retrieval (antes → después)

| Query / test | Antes (baseline 2026-07-05) | Después (2026-07-06) |
|---|---|---|
| `test_rag_usb_retrieval` | **FAIL** — top hits sin USB en nombre/excerpt | **PASS** — `usb_hub`, `USB`, `usb_dp` en top-3 |
| RLC/RF design intent | Excerpt solo `etype label value` | Top hit `sample_20260501_064720_181247` con `design_intent: RLC con LED… RF… induccion` |
| `circuit_example_description_density` | ~0 (326 chunks mayormente component-only) | **80.06%** (261/326) |
| Chunk count | 358 total, 326 `circuit_example` | Sin cambio (358/326) |

### Discrepancias vs. hipótesis original

- Corpus real: **320** `human_*.json` (no ~280), 320 `.kicad_sch` en `raw_kicad/` — re-ingesta 1:1 confirmada.
- Los **6** `sample_*.json` tienen `metadata.prompt`.
- Mejora **mayor de lo esperado** en densidad (80% vs. estimación conservadora de "mayoría con title/labels"): muchos esquemáticos KiCad mirror tienen `title_block` y/o net labels ricos.
- Mejora **menor de lo esperado** en queries genéricas de "design intent prose": queries amplias como "RF pulse receiver induction LED" pueden rankear human schematics con net names `LEDs*` por encima de `sample_*` — el `design_intent` funciona bien con queries más específicas (ver test dedicado).
- Rebuild denso pendiente cuando Ollama + `nomic-embed-text` estén disponibles; híbrido actual usa índice denso **stale** (pre-fix) + TF-IDF **fresh** (post-fix).

### Nota operativa Windows

`dataset_builder.py` falla con `UnicodeEncodeError` en consola cp1252 por emojis en `print()`. Workaround: `$env:PYTHONIOENCODING='utf-8'` antes de ejecutar.

## Alcance de la investigación

Debería coordinarse con [`dataset_research.md`](./dataset_research.md): si se retoma el crawler de GitHub para ampliar el corpus (`Open-Schematics` de Hugging Face, SparkFun, Adafruit — fuentes ya identificadas allí), el parser mejorado de este hallazgo debe aplicarse *antes* de esa ingesta masiva, no después, para no tener que re-procesar dos veces.
