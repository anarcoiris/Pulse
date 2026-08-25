# 🔍 Auditoría Crítica de Arquitectura y Discrepancias — PulseLab
**Fecha:** 2026-08-25T15:58 UTC+2  
**Alcance:** Recapitulación de decisiones clave desde `d7092f9f3292c453b8e212ef592dc8181ea2f589` hasta el estado actual.

---

## 1. Recapitulación de Decisiones Clave desde `d7092f9f`

Desde el commit `d7092f9f` (*Release ready: KiCad S-expr generation*), la plataforma evolucionó a través de hitos fundamentales:

| Commit / Hito | Decisión Arquitectural | Impacto / Estado |
|---|---|---|
| **7e56ec6 / c6f8069** | Generación programática directa de archivos KiCad 10 `.kicad_pcb` y `.kicad_sch` vía S-Expressions. | Eliminó dependencias de scripts externos obsoletos. Estableció sintaxis KiCad 10. |
| **31707f6** | Unificación SSOT (*Single Source of Truth*): el `CircuitGraph` se convirtió en la fuente única compartida para esquemático, PCB y simulación. | Reducción de DRC de 504 a 55 violaciones (-89%). |
| **7b21edc** | Motor de auditoría KiCad nativo con reglas topológicas R001–R014 y crosscheck SCH ↔ PCB. | Validación estricta de paridad de referencias y conectividad neta. |
| **c720932** | Introducción de `CircuitDesignSchema` (Pydantic) y `AutoPlacementEngine` 2D con relajación de fuerzas dirigidas y campos de repulsión. | Capacidad de síntesis automática a partir de prompts sin coordenadas manuales. |
| **d625225 / 6eaf96c** | Pasarela de proveedores de componentes (JLCPCB + PCBWay) y puente de autorouting FreeRouting. | Cotización BOM en tiempo real y enrutamiento automatizado. |
| **Trabajo Reciente (Web Studio & Vision)** | Motor de inspección visual 9-Pass (`visual_inference.py`), visores interactivos 2D SVG / 3D Three.js, y gateway LLM multi-proveedor (Ollama/llama.cpp/OpenAI). | Plataforma web interactiva con drag-and-drop, DRC en vivo y síntesis asistida por IA. |

---

## 2. Análisis Crítico de Disonancias y Discordancias

### 🅰️ Meta `n1` / `n2` vs Diccionario `pins` (Conectividad)

#### Origen de la discordancia:
El código legacy de simulación analógica (MNA) heredó la convención de 2 terminales (`n1`, `n2`) para componentes pasivos ($R, C, L, D, V$). Al expandir el sistema a microcontroladores e ICs multipin, se añadió `pins: Dict[str, str]`.

#### Problemas detectados:
1. **Ambigüedad de precedencia:** En `core/circuit_graph.py` (`from_component_dicts`), si un componente no define `pins`, se puebla `pins["1"] = n1` y `pins["2"] = n2`. Sin embargo, componentes como conectores USB, botones táctiles de 4 pads, headers de 4 pines o reguladores SOT-223 tienen más de 2 terminales. Si se declaran con `n1`/`n2`, los pines 3, 4, etc., quedan flotantes sin asignar.
2. **Asignación en `pcb_builder.py`:** Al crear resistencias o condensadores, `pcb_builder.py` invoca `pcb.add_resistor(ref, val, x, y, net1=c.n1, net2=c.n2)`. Si un prompt LLM estructurado genera `pins: {"1": "VCC", "2": "GND"}` pero omite `n1`/`n2`, `c.n1` queda vacío hasta la pasada de enlace posterior.

#### Directriz y Solución:
- **`pins: Dict[str, str]` es el estándar canónico universal (SSOT):** Todos los componentes (incluyendo pasivos de 2 pines) deben mapear sus terminales a `pins={"1": ..., "2": ...}`.
- **`n1` y `n2` quedan restringidos exclusivamente como *azúcar sintáctico* para componentes bipolares ($R, C, L, D, LED, V, S$):** Si un componente tiene más de 2 pines físicos (IC, MCU, Connector, Header, SOT-223), el uso de `n1`/`n2` queda prohibido y se exige el diccionario `pins`.

---

### 🅱️ Patios de Componentes (*Courtyards* IPC-7351B) y Zonas Reservadas

#### Problemas detectados:
1. **Divergencia entre motores de geometría:**
   - `AutoPlacementEngine.get_component_bounds` utilizaba un intercambio simple de ancho/alto para rotaciones de 90°, sin proyectar la caja envolvente OBB real bajo cualquier ángulo.
   - `VisualInferenceEngine` utiliza `CourtyardBox.rotated_bounds` con la fórmula $(W \cdot \cos\theta + H \cdot \sin\theta, W \cdot \sin\theta + H \cdot \cos\theta)$.
   - `PCBBuilder._get_courtyard_aabb` fue actualizado recientemente para unificarse con `VisualInferenceEngine`, pero `AutoPlacementEngine` aún calculaba dimensiones menores.
2. **Footprints no registrados en `PACKAGE_PHYSICAL_SPECS`:**
   Footprints críticos como:
   - `Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm` (CP2102N USB-UART)
   - `Module:Pololu_Breakout-16_15.2x20.3mm` (Driver TMC2209 / A4988)
   - `TerminalBlock:TerminalBlock_bornier-2_P5.08mm` (Entrada de alimentación VMOT)
   - `Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical` (Conector motor NEMA)
   
   Al no estar explícitamente en el diccionario `PACKAGE_PHYSICAL_SPECS`, caían al fallback genérico de **3.0 × 2.0 mm**. Como resultado, el motor de auto-colocación asumió que el módulo Pololu (15.2 × 20.3 mm) medía sólo 3 × 2 mm, provocando posibles solapamientos.

---

### 🅲️ Aclaración: Los "3 MCUs" en la Síntesis del Driver NEMA-17

En la síntesis para el prompt *"Un driver para motores de pasos NEMA-17 controlado por un ESP32 con micro USB (y el controlador USB-UART adecuado) para instalar firmware y programar el ESP32"*, se generaron los siguientes chips:

1. **`U_ESP32` (`ESP32-WROOM-32E`):** El microcontrolador principal (MCU de 38 pines + thermal pad).
2. **`U_UART` (`CP2102N`):** El puente USB-a-UART en encapsulado QFN-24 necesario para programar el ESP32 desde el puerto Micro-USB.
3. **`U_STEPPER` (`TMC2209 / A4988`):** El circuito integrado/módulo controlador de potencia para las bobinas del motor paso a paso.
4. **`U_REG` (`AMS1117-3.3`):** El regulador LDO para alimentar la lógica de 3.3V desde los 5V del USB.

#### Por qué parecía haber "3 MCUs duplicados":
- En el visor 2D/3D, los tres componentes (`U_UART`, `U_ESP32`, `U_STEPPER`) tenían `package_type: "IC"` o `"MCU"` y se renderizaron con el mismo cuerpo negro rectangular y muesca de pin 1, sin diferenciar visualmente un módulo breakout DIP-16 de un encapsulado QFN-24 o de un módulo de radio ESP32.
- Además, la regla `CircuitGraph.apply_design_rules()` inyectó automáticamente pares de condensadores de desacoplo para cada uno (`C_U_UART_H/L`, `C_U_ESP32_H/L`, `C_U_STEPPER_H/L`), lo que dio la impresión de una replicación de infraestructura de soporte de MCU.
- **Conclusión:** La selección de componentes fue eléctricamente correcta según el prompt, pero la representación geométrica y visual carecía de especificidad de encapsulado.

---

### 🅳️ Reglas de Diseño (DRC): Márgenes, Ancho de Pistas y Mounting Holes

1. **Superposición de Mounting Holes:**
   - En `bridge/pcb_builder.py`, `add_mounting_holes_corners()` coloca 4 taladros M3 a 3.5 mm de las esquinas del origen de la placa (`ox + 3.5`, `oy + 3.5`).
   - El taladro tiene 3.2 mm de broca y 6.0 mm de pad de cobre.
   - `AutoPlacementEngine` no reservaba zonas de exclusión en las esquinas, lo que permitía que conectores de esquina o condensadores se ubicaran a menos de 6.0 mm de la esquina y se solaparan con la cabeza del tornillo M3.
2. **Anchos mínimos de pista por Netclass:**
   - Señales estándar: mínimo 0.20 mm (clearance 0.15 mm).
   - Alimentación (`PWR_12V_VMOT`, `PWR_5V_USB`, `PWR_3V3_ESP`, `PWR_GND`): mínimo 0.50–0.60 mm.
   - Bobinas del motor (`M_1A`, `M_1B`, `M_2A`, `M_2B`): mínimo 0.50 mm (clase `MotorCoil`).
   - Pistas USB diferenciales (`USB_D+`, `USB_D-`): par diferencial a 0.25 mm de ancho y 0.20 mm de separación.

---

## 3. Plan de Acción de Correcciones

1. **Actualizar `PACKAGE_PHYSICAL_SPECS`:** Añadir dimensiones reales para `QFN-24`, `Pololu_Breakout-16`, `JST_XH_4pin`, `TerminalBlock_5.08mm`.
2. **Unificar cálculo de Courtyard en `AutoPlacementEngine`:** Implementar proyección OBB completa para cualquier ángulo de rotación.
3. **Zonas de Exclusión para Mounting Holes:** Inyectar keepouts en las 4 esquinas durante la colocación de macro-componentes para evitar colisiones con tornillos M3.
4. **Validación estricta `n1`/`n2` vs `pins`:** Asegurar que `PlacedComponent` y `CircuitDesignSchema` sincronicen bidireccionalmente y rechacen `n1`/`n2` para componentes de más de 2 terminales.
