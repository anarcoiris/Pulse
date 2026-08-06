# Sistema de reglas para auditoría y corrección de `.kicad_pcb`

Este documento define un flujo **por fases**, con reglas numeradas y
referenciables (`R001`...`R012`), para llevar un board de "sospechoso" a
"verificado". Cada regla tiene: qué detecta, por qué importa, cómo
corregirla, y cómo re-verificar. `kicad_audit.py` implementa la detección
automática de R001–R012 (excepto R007, que documenta el límite de
cobertura de esta herramienta).

## Principio de orden

Las fases están ordenadas por **dependencia**, no por severidad. No tiene
sentido revisar clearances (Fase 4) si el footprint del regulador todavía
tiene un pad duplicado (Fase 1) — cualquier corrección posterior invalida
el análisis geométrico. Siempre se avanza de fase solo cuando la anterior
queda en verde.

```
Fase 0: Integridad del archivo
Fase 1: Integridad de footprints
Fase 2: Integridad de la tabla de nets
Fase 3: Integridad de la topología del circuito
Fase 4: DRC geométrico (fuera del alcance de este script)
Fase 5: Verificación cruzada contra el esquemático
```

---

## Fase 0 — Integridad del archivo

**Objetivo:** confirmar que el archivo es un s-expression válido y que las
herramientas de KiCad (o este script) pueden parsearlo sin ambigüedad.

| Regla | Descripción | Detección |
|---|---|---|
| R000 | El archivo parsea sin error de sintaxis (paréntesis balanceados, comillas cerradas) | Falla dura del parser — no hay regla numérica, es prerequisito |

**Paso a paso:**
1. `python3 kicad_audit.py board.kicad_pcb` — si lanza `SyntaxError`, el
   archivo está corrupto a nivel de texto (edición manual rota, merge de
   git mal resuelto, encoding). Arreglar antes de continuar.
2. Abrir en KiCad y confirmar que carga sin diálogo de error.

---

## Fase 1 — Integridad de footprints

**Objetivo:** cada footprint, aisladamente, debe ser un objeto físico
coherente antes de mirar cómo se conecta al resto del board.

| Regla | Severidad | Descripción |
|---|---|---|
| **R001** | error | Pad con número duplicado dentro del mismo footprint |
| **R008** | error | Footprint SOT-223-3 con conteo de pads únicos ≠ 3 (patrón específico para reguladores tipo AMS1117) |
| **R012** | error | Dos footprints comparten la misma referencia (`Reference`) |

**Por qué importa primero:** un footprint con geometría de pads corrupta
(R001) hace que *cualquier* net que toque ese pad sea ambigua — no sabes
si una traza llega al "pad 2 de arriba" o al "pad 2 de abajo". Resolver
esto antes de tocar nets evita perseguir fantasmas en fases posteriores.

**Paso a paso:**
1. `python3 kicad_audit.py board.kicad_pcb --rule R001,R008,R012`
2. Para cada hallazgo R001/R008: abrir el footprint en el editor de
   footprints de KiCad (no el editor de PCB), comparar contra el
   datasheet del componente pin por pin.
   - En el caso concreto de `SOT-223-3_TabPin2` / AMS1117: el pinout real
     es **1=GND, 2=VOUT(+tab), 3=VIN**. El footprint debe tener pad "2"
     una sola vez, con el tab fusionado ahí (el tab comparte red con
     VOUT). Si el generador produjo dos entradas `pad "2"` con tamaños
     distintos, es una fusión mal hecha — renombra una a lo que
     corresponda o elimínala si es geometría redundante del tab.
3. Para cada R012: renombrar en el esquemático (nunca solo en el PCB) y
   re-exportar el netlist, o usar "Update PCB from Schematic" para forzar
   re-anotación.
4. Re-correr `--rule R001,R008,R012` hasta 0 hallazgos.

---

## Fase 2 — Integridad de la tabla de nets

**Objetivo:** todo pad que debería llevar señal/potencia realmente tiene
una red asignada, y toda red referenciada existe en la tabla `(net ...)`.

| Regla | Severidad | Descripción |
|---|---|---|
| **R002** | error | Pad sin ninguna cláusula `(net ...)` (excepto agujeros de montaje y pads sin numerar) |
| **R009** | error | Traza/via/pad referencia un `net_id` que no aparece en la tabla top-level `(net ...)` |

**Por qué importa:** esta es la causa raíz más probable del problema que
viste manualmente en el AMS1117 — un pad sin `(net ...)` es indistinguible
de "flotante a propósito" para KiCad, así que **no siempre aparece como
error de DRC estándar**; DRC típicamente marca "unconnected" solo cuando
el netlist del esquemático dice que *debería* haber conexión y el PCB no
la tiene ruteada, pero si el PCB nunca tuvo la red asignada al pad, el
propio concepto de "unrouted" no aplica — es un vacío silencioso.

**Paso a paso:**
1. `python3 kicad_audit.py board.kicad_pcb --rule R002,R009`
2. Para cada R002: la causa casi siempre es una de estas tres:
   - (a) El componente se colocó en el PCB manualmente sin pasar por
     "Update PCB from Schematic", así que nunca heredó las redes del
     esquemático → **solución: correr esa sincronización**.
   - (b) El componente no existe en el esquemático en absoluto (se generó
     directamente en el PCB por script/herramienta externa, como sugiere
     el generador `"PulseLab Forge"` no estándar en tu archivo) →
     **solución: crear el símbolo correspondiente en el esquemático,
     conectarlo, y re-sincronizar**, o eliminar el footprint si es un
     duplicado/prototipo abandonado.
   - (c) Ediciones manuales del `.kicad_pcb` en texto plano que omitieron
     la cláusula `(net ...)` por error → **solución: añadirla a mano
     apuntando al `net_id` correcto, verificado contra la tabla**.
3. Para cada R009: el `net_id` fue probablemente reasignado o el archivo
   fue editado a mano con un ID que nunca se declaró. Verificar en la
   tabla `(net ...)` cuál era el ID correcto y corregir la referencia.
4. Re-correr hasta 0 hallazgos.

---

## Fase 3 — Integridad de la topología del circuito

**Objetivo:** cada red tiene sentido eléctrico — conecta ≥2 puntos reales,
no hay componentes completamente aislados, no hay cortos evidentes.

| Regla | Severidad | Descripción |
|---|---|---|
| **R003** | warning | Red que solo toca UN pad de footprint |
| **R004** | error | Red con cobre (tracks/vias) pero CERO pads de footprint asociados |
| **R005** | error | Componente completo (todos sus pads) aislado del resto del circuito |
| **R006** | error | Pasivo de 2 pads (condensador/resistencia) con ambos pads en la misma red (corto) |
| **R010** | info (heurística) | Nombres de red sugieren que deberían fusionarse (ej. `3.3V_ESP` vs `3.3V_FLIPPER`) pero son IDs distintos sin puente |
| **R011** | info | Huecos en la numeración de referencias (ej. `IC_001` → `IC_006`) sugieren piezas eliminadas sin re-anotar |
| **R013** | warning | Zona de restricción (keepout) definida en una sola capa (ej. solo F.Cu) en lugar de multicapa |
| **R014** | warning | Regulador lineal (ej. AMS1117) con una riel de alimentación (VIN/VOUT) sin capacitor de desacoplo a GND |

**Por qué importa — y por qué exactamente aquí encaja tu hallazgo del
regulador:** Fase 1 garantiza que el footprint del AMS1117 es geométricamente
válido. Fase 2 garantiza que sus pads tienen redes asignadas. Fase 3 es
donde confirmas que esas redes realmente **cierran el circuito** — es
decir, que la salida del regulador (`3.3V_ESP` o como se llame tras Fase 2)
efectivamente alimenta al ESP32 y no es un nombre que "suena" correcto pero
nunca se conectó a nada más.

**Paso a paso:**
1. `python3 kicad_audit.py board.kicad_pcb --rule R003,R004,R005,R006,R010,R011`
2. **R005 es la señal de alarma principal** — cualquier componente aquí
   necesita inspección manual inmediata en el esquemático: ¿existe ahí?
   ¿tiene conexiones ahí? Si sí, el problema es sincronización
   PCB↔esquemático (volver a Fase 2). Si no, el componente nunca fue
   diseñado correctamente y necesita trabajo de esquemático real.
3. **R006** — nunca ignorar, siempre es un corto real. Verificar footprint
   (¿los dos pads están mal posicionados y tocando la misma red por
   accidente de layout?) o verificar el netlist (¿el esquemático
   realmente cablea así, lo cual sería un error de diseño aguas arriba?).
4. **R010** — esta regla requiere juicio humano. Para tu caso específico:
   - Si `3.3V_ESP` y `3.3V_FLIPPER` deben ser el mismo rail: añade una
     conexión física (ej. resistencia de 0Ω o track directo) entre ambas,
     **o mejor**, renombra ambas al mismo net en el esquemático para que
     KiCad las trate como una sola red desde el origen — evita duplicar
     nombres para la misma señal.
   - Si deben permanecer aisladas (ej. por razones de aislamiento de
     ruido RF entre ESP32 y la lógica CC1101/nRF24), esto es
     intencional, pero entonces **cada rail necesita su propio camino
     completo hasta una fuente real** (ver Fase 2b más abajo) — no basta
     con que existan como nombres separados si ambas dependen del mismo
     regulador físico.
5. **R003** — revisar caso por caso; algunos son legítimos (ej. una red
   que termina en un test point de un solo pin es normal). Las que
   correspondan a periféricos reales del CC1101/nRF24/ESP32 casi
   seguro indican que falta la traza al segundo extremo.
6. Re-correr hasta que solo queden R003 confirmados como intencionales y
   R010/R011 revisados y documentados (no necesitan llegar a cero, son
   informativos).

### Fase 2b (sub-paso específico para tu regulador) — Verificación de cadena de alimentación

Esta no es una regla automatizable en general (depende de la topología
específica de cada board), pero para el caso concreto que identificaste,
documento el procedimiento manual:

1. Desde el pad "5V_USB" (net 1) del conector Flipper GPIO, sigue la
   traza/via hasta su destino final. Debe llegar al pad VIN (pad "3" tras
   corregir R008) del AMS1117.
2. Desde el pad VOUT (pad "2") del AMS1117, sigue la traza hasta donde
   termine. Debe llegar simultáneamente a los pads VDD del ESP32 y a
   cualquier rail de 3.3V que alimente CC1101/nRF24 — si esos rails son
   nombres de red distintos (R010), aquí es donde decides fusionarlos o
   no.
3. Si en el paso 1 o 2 la traza termina en un via "muerto" (sin otro
   endpoint), eso es exactamente R004 — la traza existe visualmente pero
   no llega a ningún pad real.

---

## Fase 4 — DRC geométrico (fuera del alcance de `kicad_audit.py`)

**Objetivo:** clearances, courtyard overlap, ancho de traza vs. corriente,
zonas de keepout respetadas.

| Regla | Cobertura |
|---|---|
| R007 | Placeholder — requiere el motor geométrico de KiCad |

**Por qué esta herramienta no lo hace:** clearance/overlap necesita
geometría 2D completa (polígonos, arcos, curvas de Bézier en algunos
footprints) y las reglas de diseño del stackup (ancho mínimo, separación
mínima por capa) — reimplementar esto de forma confiable fuera de KiCad es
alto riesgo de falsos negativos.

**Paso a paso (usando KiCad directamente):**
1. Completar Fases 1–3 primero — DRC geométrico sobre un netlist roto
   produce ruido inútil (mil "unconnected" que ya sabes que son R002/R005).
2. En KiCad: **Inspeccionar → Verificador de reglas de diseño (DRC)**.
3. Prestar atención específica a:
   - Courtyard overlap entre ESP32-S3-WROOM-1 y el header CC1101 (están
     físicamente cerca según las coordenadas: MCU en `115.25,105`, CC1101
     header en `163,102` — probablemente OK, pero verificar).
   - Las 3 zonas `keepout` con `copperpour not_allowed` solo declaradas en
     `F.Cu` — si hay plano de tierra en `B.Cu` bajo la antena del ESP32,
     confirma si necesita el mismo keepout ahí (ver nota RF más abajo).

### Nota específica RF (relacionada con tu dominio de trabajo)

El footprint `ESP32-S3-WROOM-1` trae su propia keepout zone embebida
(`(zone (keepout ...))` dentro del footprint, capas `F.Cu` + `B.Cu` +
todas las internas) — **esa sí está bien declarada multicapa**. Las 3
zonas de keepout *adicionales* a nivel de board (`83fa5f79...`,
`501b0fe0...`, `f2f029a8...`) están **solo en F.Cu**. Si el propósito de
esas 3 zonas es proteger el patrón de radiación de las antenas de
CC1101/nRF24 (no solo el ESP32, que ya tiene su propia zona), confirma si
necesitas espejarlas en B.Cu — sobre todo si el plano de GND de referencia
vive en una capa distinta a F.Cu.

---

## Fase 5 — Verificación cruzada contra el esquemático

**Objetivo:** confirmar que el PCB corregido sigue siendo fiel al diseño
esquemático (no solo "internamente consistente").

**Paso a paso:**
1. KiCad → **Herramientas → Actualizar PCB desde esquemático**. Si reporta
   diferencias, cada una es una fuente potencial de los mismos síntomas
   que cazamos en Fase 2/3.
2. Generar el netlist desde el esquemático (`.net` o `.xml`) y comparar
   contra un netlist exportado del PCB corregido — deben ser
   equivalentes red por red.
3. Solo después de este paso considerar el board "verificado" para pasar
   a generación de gerbers.

---

## Uso recomendado del script en este flujo

```bash
# Fase 1
python3 kicad_audit.py board.kicad_pcb --rule R001,R008,R012

# Fase 2
python3 kicad_audit.py board.kicad_pcb --rule R002,R009

# Fase 3
python3 kicad_audit.py board.kicad_pcb --rule R003,R004,R005,R006,R010,R011

# Reporte completo + JSON para tracking de progreso entre sesiones
python3 kicad_audit.py board.kicad_pcb --json audit_$(date +%Y%m%d).json
```

Guardar el JSON de cada corrida con fecha permite diffear el progreso
(cuántos errores de cada regla quedan) sin depender de memoria manual del
estado del board — útil dado que este proyecto ya lleva varias sesiones de
trabajo iterativo.

## Límites conocidos de esta herramienta

- No valida geometría (Fase 4) — usar DRC nativo de KiCad.
- No entiende semántica de bus/diferencial (ej. no detecta si SPI_MISO y
  SPI_MOSI están intercambiados — eso requiere comparar contra el
  esquemático o el datasheet, no es inferible del PCB solo).
- La heurística R010 (nombres de red similares) puede dar falsos positivos
  en boards con convenciones de nombres legítimamente parecidas — siempre
  requiere confirmación humana, por eso está marcada `info` y no `error`.
- No sigue jerarquía de esquemático multi-hoja ni resuelve alias de red
  globales/locales — opera puramente sobre lo que ya está en el `.kicad_pcb`.
