# Auditoría e Informe de Revisión Crítica de Diseño (CDR) — Flipper Killer MK II Release V4

**Proyecto:** PulseLab / Flipper Killer MK II (ESP32-S3 + CC1101 + nRF24L01+ + MicroSD)  
**Versión Auditada:** Release V4 (`output/flipper_killer_production_v4/`)  
**Fecha:** 2026-08-27  
**Calificación Global de Madurez:** **8.8 / 10** $\to$ *Apta para producción tras subsanar 2 observaciones eléctricas menores.*

---

## 1. 📋 Resumen Ejecutivo

La versión **V4** del Flipper Killer MK II representa una evolución arquitectónica sólida respecto a las versiones preliminares. El diseño consolida el pinout canónico para el Flipper Zero, desacopla limpiamente las señales SPI de alta velocidad, resuelve los problemas de cortocircuito en la huella MicroSD DM3AT y cierra geométricamente el contorno mecánico.

Este informe desglosa un análisis crítico riguroso en cinco áreas de ingeniería:
1. **Topología Eléctrica y Pinout MCU / Headers**
2. **Árbol de Potencia y Gestión Térmica**
3. **Bus SPI Compartido, Integridad de Señal y Resistencia de Aislamiento**
4. **Layout Físico PCB, RF y Reglas DFM (Design for Manufacturing)**
5. **Cadena de Suministro PCBA (BOM / CPL / LCSC)**

---

## 2. 🔍 Hallazgos Críticos y Puntos de Acción Inmediata

### 🔴 Hallazgo 1: Asignación de Redes en Pads de J2 en `board.kicad_pcb`
* **Diagnóstico:** En el script generador `build_flipper_killer_production_v4.py`, los reemplazos por expresión regular buscaron cadenas `(net ...)` preexistentes. Dado que los pines 4 (`CS_RF_CC1101`), 11 (`PWR_GND`), 17 y 18 (`PWR_GND`) estaban desconectados en la plantilla base, quedaron en el archivo `.kicad_pcb` sin la directiva `(net "NOMBRE_RED")`.
* **Impacto:** Aunque las pistas físicas están trazadas hacia las coordenadas de dichos pines, KiCad no asocia formalmente el pad con la red en el netlist interno.
* **Acción Correctiva:** Asegurar que cada pad del footprint `J2` contenga explícitamente su directiva `(net "...")` completa.

---

### 🟡 Hallazgo 2: Asignación de Pines UART del ESP32-S3 (IO1/IO2 vs IO43/IO44)
* **Diagnóstico:** En el esquemático y PCB, las líneas UART hacia el Flipper (J2 Pines 13 y 14) están conectadas a los pines 36 (GPIO2) y 37 (GPIO1) del módulo ESP32-S3-WROOM-1U.
* **Análisis de Compatibilidad:**
  * El ESP32-S3 posee matriz GPIO flexible (GPIO Matrix), lo que permite rutear `UART0` o `UART1` a cualquier pin mediante software (`Serial1.begin(115200, SERIAL_8N1, RX, TX)`).
  * Sin embargo, los firmwares oficiales precompilados de **ESP32 Marauder** que utilicen el puerto UART0 por defecto esperan el hardware nativo en `GPIO43 (TXD0)` y `GPIO44 (RXD0)` (Pines 38 y 39 del módulo).
* **Recomendación:** Mantener documentado este pinout en el firmware base o bien mapear directamente a los pines 38 (IO43) y 39 (IO44) para compatibilidad inmediata *out-of-the-box* con binarios estándar de Marauder.

---

### 🟡 Hallazgo 3: Capacidad de Corriente del Diodo Schottky D1 (BAT54C)
* **Diagnóstico:** El diodo dual `D1` es un `BAT54C` (SOT-23) con corriente continua máxima nominal de $I_F = 200\text{ mA}$ (pico $300\text{ mA}$).
* **Análisis de Carga:** El ESP32-S3 durante transmisiones intensivas de Wi-Fi en modo AP o escaneo masivo de paquetes (Beacon Flooding / Deauth) genera picos transitorios de consumo de hasta **280 – 350 mA**.
* **Recomendación de Robustez:** Reemplazar `BAT54C` por un diodo Schottky de mayor corriente como **SS14**, **B5819W** o **MBR0520** ($I_F \ge 500\text{ mA} - 1\text{ A}$, empaquetado SOD-123 o SOT-23) para garantizar menor caída de tensión ($V_F \le 0.30\text{V}$) y evitar calentamiento en sesiones prolongadas.

---

## 3. ⚡ Análisis de la Arquitectura de Potencia

```mermaid
graph TD
    USB["USB-C 5V (J1)"] -->|Anodo 1| D1["Diodo Schottky Dual (D1)"]
    FLIP_5V["Flipper 5V (J2 Pin 1)"] -->|Anodo 2| D1
    D1 -->|VSYS (~4.7V)| C1["C1 10µF"]
    C1 --> U1["LDO AMS1117-3.3 (U1)"]
    U1 -->|PWR_3V3_ESP| C2["C2 10µF"]
    U1 -->|PWR_3V3_ESP| C3["C3 100nF"]
    U1 -->|PWR_3V3_ESP| ESP["ESP32-S3 (U2)"]
    U1 -->|PWR_3V3_ESP| SD["MicroSD Hirose (J_SD)"]
    
    FLIP_3V3["Flipper 3.3V (J2 Pin 9)"] -->|PWR_3V3_FLIPPER| C_RF1["C_RF1 10µF"]
    FLIP_3V3 -->|PWR_3V3_FLIPPER| C_RF2["C_RF2 100nF"]
    FLIP_3V3 --> CC1101["CC1101 Sub-GHz (U3)"]
    FLIP_3V3 --> NRF["nRF24L01+ 2.4GHz (U4)"]
    
    GND["Plano Continuo PWR_GND"] --- ESP
    GND --- SD
    GND --- CC1101
    GND --- NRF
    GND --- U1
```

### Fortalezas:
1. **Aislamiento de Rieles 3.3V:** El consumo dinámico del ESP32-S3 y la tarjeta MicroSD está alimentado por su propio LDO (`PWR_3V3_ESP`), protegiendo al riel interno del Flipper (`PWR_3V3_FLIPPER`) de caídas de tensión que puedan reiniciar el STM32WB55.
2. **Protección Anti-Retorno:** El diodo D1 previene que una fuente externa USB alimente destructivamente el puerto 5V del Flipper y viceversa.
3. **Disipación Térmica:** La pestaña metálica (Tab / Pad 4) del AMS1117 está conectada directamente al plano de salida `PWR_3V3_ESP` sobre cobre generoso.

---

## 4. 📶 Bus SPI Compartido e Integridad de Señal

### Configuración del Bus:
* **Líneas de Datos/Reloj:** `MOSI`, `MISO`, `SCK`.
* **Amortiguamiento / Aislamiento:** Resistencias de $330\,\Omega$ en serie (`R_ISO_MOSI`, `R_ISO_MISO`, `R_ISO_SCK`) situadas entre el bus del ESP32 y el bus del Flipper/Módulos RF.
* **Líneas de Selección de Chip (CS):**
  * `SD_SPI_CS` $\to$ Conectado exclusivamente al pin 18 (IO10) del ESP32 con resistencia pull-up de $10\text{ k}\Omega$.
  * `CS_RF_CC1101` $\to$ Conectado al Pin 4 (PC3) del Flipper (Nativo Sub-GHz).
  * `CS_RF_NRF24` $\to$ Conectado al Pin 7 (PC1 / Extra 7) del Flipper.

### Veredicto:
* La topología impide colisiones de bus en el bus SPI. Cuando el Flipper opera el CC1101 o nRF24, el MicroSD permanece deseleccionado en estado de alta impedancia (High-Z). Las resistencias de $330\,\Omega$ limitan corrientes parásitas si alguno de los dispositivos entra en conflicto temporal.

---

## 5. 🛠️ Layout Físico, DFM y Reglas de Fabricación

| Parámetro | Valor Diseñado | Estándar Fábrica | Estado |
| :--- | :--- | :--- | :---: |
| **Capas** | 2 capas (F.Cu / B.Cu) | FR-4 Estándar | ✅ Óptimo |
| **Espesor PCB** | 1.6 mm ±10% | 1.6 mm | ✅ Crítico para pines GPIO |
| **Clearance Cobre** | 0.20 mm | $\ge 0.127\text{ mm}$ (5 mil) | ✅ Muy seguro |
| **Ancho Pistas Potencia** | 0.40 – 0.50 mm | $\ge 0.30\text{ mm}$ | ✅ Robusto |
| **Ancho Pistas Señal** | 0.25 mm | $\ge 0.127\text{ mm}$ | ✅ Robusto |
| **Pads MicroSD DM3AT** | De-rotados 270° (Aislamiento 0.40 mm) | $\ge 0.20\text{ mm}$ | ✅ Corregido |
| **Vertido de Masa** | Dinámico completo en ambas caras | Polígono perimetral | ✅ 0 cortos |
| **Avisos Serigrafía** | 35 avisos cosméticos | CAM los recorta automáticamente | ℹ️ Mejorable estéticamente |

---

## 6. 📦 Validación de BOM y PCBA (JLCPCB)

1. **MicroSD DM3AT (`C114227`):** Componente estándar disponible en catálogo JLCPCB.
2. **ESP32-S3-WROOM-1U (`C2913200`):** Módulo oficial con conector IPEX/U.FL. No requiere antena trazada en PCB, eliminando pérdidas por proximidad de planos de masa.
3. **Pulsadores EVQPE1 (`C139797`):** SMD compactos para Reset y Boot.
4. **USB-C 16-pin HRO (`C165948`):** Resistencias pull-down CC1/CC2 de $5.1\text{ k}\Omega$ incluidas (`R2`, `R3`), asegurando compatibilidad con cargadores Power Delivery / USB-C a USB-C.

---

## 7. 🚀 Dictamen Final y Pasos Recomendados

1. **Paso 1:** Ejecutar parche de sincronización de `net` en los pads 4, 11, 17, 18 de J2.
2. **Paso 2:** Opcional: Reubicar textos de serigrafía (`R_SD_CS`, `C_RF1`, `LED1`) fuera de los pads de cobre para lograr **0 Warnings absolutos en DRC**.
3. **Paso 3:** Generar el paquete definitivo de Gerbers y enviar a producción en acabado **ENIG (Oro de inmersión)** o **Lead-Free HASL** con espesor estricto de **1.6 mm**.
