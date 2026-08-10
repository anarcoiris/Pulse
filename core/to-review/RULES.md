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

## Fase 3b — Conectividad real de cobre (ratsnest) y clearance de taladros

**Objetivo:** confirmar que el cobre físicamente dibujado (segments + vias)
realmente une todos los pads que declaran pertenecer a la misma red — es
decir, que el ruteo está *completo*, no solo que el modelo de netlist es
coherente (eso ya lo cubrió Fase 2/3). Esta fase vive *entre* Fase 3 y
Fase 4 porque usa geometría simple (coincidencia de coordenadas, distancia
euclidiana) sin necesitar el motor DRC completo de KiCad.

| Regla | Severidad | Descripción |
|---|---|---|
| **R013** | error | Una red con ≥2 pads tiene el cobre partido en ≥2 "islas" desconectadas entre sí — ruteo incompleto |
| **R014** | warning | Distancia borde-a-borde entre dos taladros (vía↔vía, vía↔pad, pad↔pad) por debajo de un umbral configurable (default 0.25mm) |

**Cómo funciona R013 (para que confíes en el resultado):** construye un
grafo con *union-find* donde los nodos son extremos de segmentos, vías, y
pads; dos nodos se fusionan si comparten coordenada exacta (tolerancia
0.001mm) **y capa** — las vías fusionan explícitamente sus capas
declaradas (típicamente F.Cu↔B.Cu), y los pads con capas `*.Cu` se tratan
como presentes en F.Cu y B.Cu simultáneamente (correcto para pads
pasantes, que conectan ambas caras por el barril metalizado). Al final,
para cada red se cuenta cuántas "islas" (componentes conexas) contienen
al menos un pad — más de una implica ruteo incompleto.

**Validación cruzada realizada:** el valor de R014 para el par
`IC_006 pad 3 ↔ via` coincidió **exactamente** (0.0811mm) con el valor que
reportó el DRC nativo de KiCad para el mismo par físico, confirmando que
el cálculo geométrico es correcto.

**Limitación conocida:** R013 asume rotación 0° en las coordenadas locales
de cada pad al proyectarlas al sistema global (`pad.at + footprint.at`).
Si un footprint está rotado, la posición global calculada será incorrecta
y puede producir falsos positivos (reporta desconexión donde en realidad
el pad rotado sí coincide con el extremo de una traza). Antes de confiar
ciegamente en un hallazgo de R013, verifica visualmente en KiCad si el
footprint involucrado tiene rotación ≠ 0.

**Paso a paso:**
1. `python3 kicad_audit.py board.kicad_pcb --rule R013`
2. Prioriza por número de islas — una red con 17 islas entre 17 pads
   (como `GND` en este proyecto) significa que *no hay ni una sola traza*
   uniendo dos pads de esa red; una red con 2 islas normalmente solo le
   falta un tramo puntual.
3. Para cada hallazgo, usa el "ratsnest" nativo de KiCad (vista con
   Ctrl+Shift+M o el ícono correspondiente) sobre esa red específica para
   ver visualmente qué segmento falta, y rutéalo.
4. Re-correr hasta 0 hallazgos de R013 (o hasta que los que queden sean
   intencionales — ej. un plano de cobre/zone que sustituye el ruteo
   explícito de GND, en cuyo caso confirma que la zona realmente hace
   `pour` y toca esos pads).
5. `python3 kicad_audit.py board.kicad_pcb --rule R014` — para cada par
   reportado, confirma el valor mínimo real configurado en tu proyecto
   (**Board Setup → Constraints → Hole to hole clearance**) porque el
   script usa 0.25mm por defecto al no poder leer ese valor del archivo.

---

## Fase 4 — DRC geométrico completo (fuera del alcance de `kicad_audit.py`)

**Objetivo:** clearances de cobre a cobre, courtyard overlap, ancho de
traza vs. corriente, zonas de keepout respetadas, y todo lo que necesite
el motor geométrico 2D completo (polígonos, arcos, zonas rellenas).

| Regla | Cobertura |
|---|---|
| R007 | Placeholder — requiere el motor geométrico de KiCad |

**Por qué esta herramienta no lo hace (más allá de R013/R014):** clearance
cobre-cobre con formas arbitrarias (polígonos de zona, arcos, texto de
serigrafía) requiere un motor de geometría computacional completo —
reimplementar eso de forma confiable fuera de KiCad es alto riesgo de
falsos negativos. R013/R014 cubren los dos subconjuntos de Fase 4 que sí
son tratables con aritmética simple (grafo de coincidencia de coordenadas,
distancia euclidiana entre círculos).

**Paso a paso (usando KiCad directamente):**
1. Completar Fases 1–3b primero — DRC geométrico sobre un netlist roto
   produce ruido inútil (cientos de "unconnected" que ya sabes que son
   R002/R005/R013).
2. En KiCad: **Inspeccionar → Verificador de reglas de diseño (DRC)**.
3. **Importante — sincronía de archivo:** antes de comparar el reporte de
   DRC contra hallazgos de este script, confirma que ambos provienen del
   mismo archivo guardado. Un DRC generado sobre una revisión anterior
   (footprints en otras coordenadas, ruteo distinto) producirá hallazgos
   que ya no aplican a la versión actual — compara al menos una
   coordenada de un footprint fijo (ej. un mounting hole) entre el reporte
   y el archivo antes de fiarte del resto.
4. Prestar atención específica a:
   - Courtyard overlap entre ESP32-S3-WROOM-1 y el header CC1101.
   - Las 3 zonas `keepout` con `copperpour not_allowed` solo declaradas en
     `F.Cu` — si hay plano de tierra en `B.Cu` bajo la antena del ESP32,
     confirma si necesita el mismo keepout ahí (ver nota RF más abajo).
   - `lib_footprint_mismatch`: el DRC nativo compara la copia embebida en
     el `.kicad_pcb` contra la librería instalada localmente — estas
     diferencias no son necesariamente errores (pueden ser ediciones
     intencionales de footprint), pero documenta cuáles son intencionales
     para no perder el rastro en la próxima sincronización de librerías.

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
esquemático (no solo "internamente consistente"), y detectar cuando el
propio esquemático es la fuente del problema, no el PCB.

**Herramienta:** `sch_pcb_crosscheck.py board.kicad_sch board.kicad_pcb`

Esta fase se añadió después de auditar el esquemático real de este
proyecto y encontrar que **era la causa raíz** de la mayoría de los
síntomas detectados en Fases 2/3/3b. El script hace 4 verificaciones,
en orden de prioridad diagnóstica:

### 5.1 — ¿Los símbolos del esquemático tienen pines reales?

Antes de confiar en cualquier análisis de conectividad basado en
etiquetas/wires del esquemático, hay que confirmar que los símbolos
usados (`(lib_symbols ...)`) contienen sub-elementos `(pin ...)` reales.
Un símbolo de KiCad normal tiene, dentro de su definición, uno o más
sub-símbolos de unidad (ej. `"Device:R_0_1"`) que a su vez contienen
`(pin passive line (at x y angle) (name ...) (number ...))` por cada
terminal físico. **Sin esto, el símbolo es una cáscara gráfica sin
electricidad** — los wires y labels dibujados alrededor son cosméticos,
no forman parte de ningún netlist real, y KiCad no puede exportar un
netlist, correr ERC, ni sincronizar PCB↔esquemático de forma significativa
a partir de ese archivo.

**Hallazgo en este proyecto:** los 6 símbolos de librería del esquemático
(`Conn_02x09_Odd_Even`, `AMS1117-3.3`, `Device:C`, `ESP32-S3-WROOM-1`,
`Device:R`, `Conn_02x04_Odd_Even`) tienen **0 pines** cada uno. Esto es
consistente con que tanto el `.kicad_sch` como el `.kicad_pcb` fueron
generados por la misma herramienta no estándar (`generator
"PulseLab_Forge"` / `"PulseLab Forge"`) — el esquemático parece ser un
**mockup visual generado programáticamente**, no un netlist funcional de
KiCad.

**Implicación práctica:** cualquier intento de "Update PCB from
Schematic" contra este archivo no aportará ninguna información de
conectividad nueva ni corregirá nada en el PCB — el esquemático, tal
como existe, no tiene nada que sincronizar a nivel de pines.

### 5.2 — Cobertura de referencias (símbolos del esquemático vs. footprints del PCB)

Compara el conjunto de referencias (`Reference`) entre ambos archivos.

**Hallazgo en este proyecto:** **0 referencias en común** entre 8 símbolos
del esquemático (`J_FLIPPER, U1, U2, U3, U4, C1, C2, R1`) y 17 footprints
no-mecánicos del PCB (`Header_000, IC_001, MCU_004, IC_006, IC_007,
C_IC_001_H/L, C_MCU_004_H/L, C_IC_006_H/L, C_IC_007_H/L, C_002, C_003,
R_005`). Los esquemas de nomenclatura son completamente distintos —
confirma que PCB y esquemático se generaron como **dos salidas
independientes** del mismo script, no mediante el flujo bidireccional
normal de KiCad (anotación → netlist → PCB). Además, **9 de los 10
condensadores de desacoplo y la resistencia de pull-up del PCB no existen
en absoluto en el esquemático** — confirma la hipótesis de la Fase 2
(pasivos añadidos directamente en el editor de PCB, nunca diseñados).

*Nota:* los 4 agujeros de montaje (`H`) aparecen como "solo en PCB" — esto
es **normal y esperado**, las piezas mecánicas no llevan símbolo
esquemático.

### 5.3 — Cobertura de nombres de red (labels del esquemático vs. tabla de nets del PCB)

**Hallazgo en este proyecto:** de 52 nombres de red en la tabla del PCB,
solo 15 tienen una etiqueta correspondiente en el esquemático. La mayoría
de los 37 restantes son los pines `NC_MCU_004_*` (no-conectados del
ESP32-S3, esperable que no lleven etiqueta), pero también faltan `SIO` y
`SWC` (pines de depuración de un solo cable del Flipper) — confirmar si
son omisiones intencionales o gaps reales de diseño.

### 5.4 — Frecuencia de cada label (¿aparece ≥2 veces?)

En KiCad, una etiqueta de red (`label`) solo une dos puntos si el mismo
nombre aparece en ≥2 ubicaciones (o coincide con un pin). Una etiqueta que
aparece una sola vez, por definición, no puede estar unida a nada más.

**Hallazgo en este proyecto:** 10 nombres de red aparecen **exactamente
una vez**: `5V_USB, EN, UART_TX_ESP, UART_RX_ESP, NC_GDO2, GDO0_CC,
CS_CC1101, CE_NRF, CS_NRF, NC_IRQ`. Combinado con el hallazgo 5.1 (cero
pines reales), esto significa que ninguna de estas señales tiene una
conexión esquemática funcional, ni siquiera a nivel cosmético de una sola
etiqueta — son literalmente texto flotante en el lienzo.

### 5.5 — Componentes sin wire cercano (heurística)

Como proxy aproximado (sin geometría de pines real, no se puede hacer
mejor), el script busca si algún extremo de wire cae dentro de 6mm de la
posición del símbolo.

**Hallazgo en este proyecto:** `J_FLIPPER`, `C2` (10uF, ubicado en
`60.87, 131.67` — lejos de cualquier otro elemento del esquemático) y
`R1` (10k, la resistencia EN) no tienen ningún wire cerca. Esto coincide
exactamente con los hallazgos R003/R005 del lado PCB (red `EN` con solo 2
pads aislados entre sí; condensadores sin conexión real).

### Veredicto y camino de corrección recomendado

Dado que el esquemático carece de conectividad eléctrica real a nivel
estructural (5.1), **la corrección no es "añadir un wire que falta aquí o
allá"** — el archivo necesita ser reconstruido con símbolos reales de
KiCad. Dos caminos posibles:

**Opción A — Reconstruir el esquemático desde cero (recomendado):**
1. Sustituir cada símbolo placeholder por su equivalente real de librería
   KiCad (`Device:C`, `Device:R`, `Regulator_Linear:AMS1117-3.3`,
   `Connector_Generic:Conn_02x04_Odd_Even`/`02x09_Odd_Even`, y un símbolo
   real o custom para el ESP32-S3-WROOM-1 con sus 40+ pines numerados).
2. Re-anotar con el mismo esquema de referencias que ya usa el PCB
   (`Header_000, IC_001, MCU_004, IC_006, IC_007, C_IC_001_H`, etc.) para
   que la sincronización futura funcione sin fricción.
3. Cablear cada red real usando wires + labels que SÍ toquen pines reales
   (verificable con este mismo script: pin count > 0 y cada label con
   ≥2 apariciones).
4. Correr ERC nativo de KiCad — con símbolos reales, esto detectará
   automáticamente pines sin conectar, conflictos de tipo eléctrico, etc.
5. Una vez el esquemático pase ERC limpio, usar "Update PCB from
   Schematic" en modo de comparación (sin aplicar aún) para ver el diff
   completo contra el PCB actual antes de aceptar cambios.

**Opción B — Tratar el PCB como fuente de verdad y generar el
esquemático hacia atrás (más manual, KiCad no lo automatiza
completamente):** dado que el PCB ya pasó Fases 1–3b con la mayoría de
sus problemas de netlist-model resueltos, se podría exportar el netlist
del PCB actual y usarlo como referencia para reconstruir el esquemático
manualmente, en vez de partir de cero. Requiere más trabajo manual de
verificación pero preserva las decisiones de layout ya tomadas.

**Paso a paso general:**
1. `python3 sch_pcb_crosscheck.py board.kicad_sch board.kicad_pcb`
2. Revisar la Sección 5.1 primero — si reporta símbolos con 0 pines,
   detente ahí: no tiene sentido revisar 5.2–5.5 en detalle hasta
   decidir Opción A vs B, porque cualquier corrección incremental sobre
   un esquemático sin pines no se propagará realmente.
3. Si 5.1 pasa (símbolos con pines reales), usar 5.2–5.5 como checklist
   de gaps de cobertura, igual que las fases anteriores.

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
