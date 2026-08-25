# Roadmap — knowledge base PulseLab

Prioridad ordenada por evidencia real observada en las corridas
adjuntas, no por cobertura teórica del dominio. Cada ítem indica qué
lo motiva y cuál es el criterio de "hecho".

## ✅ Hecho y Verificado

- [x] `_corpus-meta/ARCHITECTURE.md` — decisión de desacoplo y modelo
      intermedio v0.
- [x] `evaluation/schemas/finding.schema.json` + `evaluation/skills/SKILL.md`
      — contrato de feedback, reemplaza prosa libre de `semantic_review`.
- [x] `schematic-rules/{rules,skills}/power_on_reset*` — bug de EN
      observado 2/2 corridas.
- [x] `ee-fundamentals/{rules,skills}/decoupling_per_ic*` — 7 findings
      redundantes colapsados en 1 regla por componente.
- [x] `tool-adapter/netlist-propio/SKILL.md` — frontera del netlist propio,
      incluye normalización de alias de red (`3.3V`/`3V3`, `GND`/`GND_PAD`)
      y distinción `ic` real vs. `connector` bajo el mismo `etype: IC`.
- [x] `pcb-rules/skills/decoupling-placement.md` — implementado en
      `core/visual_inference.py` (Pass 3: proximidad Manhattan $\le 8.0\,\text{mm}$
      entre pines de alimentación de ICs y condensadores de desacoplo).
- [x] `core/visual_inference.py` + `core/auto_placement.py` — dimensiones físicas
      normalizadas para 50+ packages, hitboxes de courtyard IPC-7351B,
      detección de solapamiento OBB/AABB, keepouts de perímetro y vía stitching.
- [x] `core/chat_session_manager.py` + `webapp/src/components/AIChatDrawer.tsx` —
      asistente co-pilot conversacional multi-sesión con inyección de contexto
      y aplicación de patches de circuito en 1-click.

---

## 🚀 Próximas Fases de Ejecución

### Fase A: Reglas de Esquemático, Biblioteca de Componentes y Adaptadores (Próximo)
*Motivado por los hallazgos restantes del review y la formalización de periféricos:*

- [ ] **Fase 1: Reglas de Topología de Señal y Strapping**:
  - `schematic-rules/rules/i2c_bus_pullups.yaml` + skill: Modelar pull-up de I2C (resistencias hacia VCC, no hacia GND).
  - `schematic-rules/rules/boot_strap_pins.yaml` + skill: Formalizar pines strap (GPIO0/BOOT) vs reset (EN).
  - `component-library/parts/esp32-s3.yaml`: Pinout de referencia con roles funcionales de cada pin.
- [ ] **Fase 2: Biblioteca de Componentes Periféricos**:
  - `component-library/parts/{ssd1306,pn532,cc1101}.yaml`: Mapeo formal de pines y periféricos.
  - `component-library/skills/led-modeling-gap.md`: Documentar heurísticas de soporte para transiciones de modelos.
- [ ] **Fase 3: Reglas Físicas de Stackup**:
  - `pcb-rules/rules/stackup_basics.yaml`: Validación de apilamiento de capas cuando existan casos de prueba reales.
- [ ] **Fase 4: Adaptador Neutral KiCad**:
  - `tool-adapter/kicad/SKILL.md`: Capa de traducción directa entre `.kicad_sch`/`.kicad_pcb` y el modelo intermedio neutral.
- [ ] **Fase 5: Orquestación de Agente**:
  - `orchestration/skills/iteration-loop.md`: Criterio de parada formal y orden de severidad (`ee_fundamentals` → `schematic` → `pcb`).
  - **Promoción de Corpus**: Umbral de repetición $N$ para promover reglas aprendidas al corpus canónico.

---

### Fase B: Calibration Forge, Benchmarking y Limpieza Arquitectónica (Fase Posterior)
*Motivado por la optimización de contexto del LLM y la robustez del netlist:*

- [ ] **Clean Session 4b A/B Benchmark** (`docs/calibration_forge/prompt_vs_rag_balance.md`):
  - Ejecutar corrida limpia de 10 benchmarks (Prompt Rules vs RAG Injection) con doble backend.
  - Resolver anomalía de cobertura de pines ($12.5\times$) en módulos periféricos densos.
  - Reducir reintentos de síntesis a $<3$ intentos.
- [ ] **Limpieza de RAG y Símbolos**:
  - Deprecar entradas manuales duplicadas en `pinouts_library.json` conforme el índice KiCad cubre los componentes.
- [ ] **Refactorización de Netlist y Estado**:
  - Migrar a objetos `Net` tipados de primera clase en `CircuitGraph`.
  - Unificar `FootprintRegistry` centralizado.
  - Implementar serialización transaccional de historial (undo/redo) para los visores 2D/3D.
