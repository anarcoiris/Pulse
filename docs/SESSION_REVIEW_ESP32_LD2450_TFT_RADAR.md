# Registro de Sesión: Producción del Sensor de Presencia Radar ESP32-S3 + Pantalla TFT + HLK-LD2450

**Proyecto:** PulseLab Generative EDA Platform  
**Ruta del Entregable:** [`output/esp32_ld2450_tft_presence_sensor/`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/)  
**Fecha:** 2026-08-28  

---

## 1. Resumen de la Tarea

Se investigaron proyectos de hardware abierto y se ejecutó la pipeline del motor EDA `PulseLabEngine` para diseñar y producir de forma completa el paquete de fabricación de una placa **ESP32-S3 con pantalla TFT SPI (ST7789), sensor de radar mmWave HLK-LD2450 y sensor de luz ambiental I2C (BH1750)**.

### Características Principales:
* **Microcontrolador:** ESP32-S3-WROOM-1U (conector IPEX exterior para evitar interferencias con planos de tierra).
* **Radar mmWave:** HLK-LD2450 (UART: IO17 TX / IO18 RX) alimentado a 5V con filtrado en pi ($10\,\mu\text{F} + 100\text{ nF}$).
* **Pantalla TFT:** Conector de 8 pines para módulos ST7789 (240x240 / 240x280) con bus SPI nativo por hardware a 80 MHz.
* **Sensor de Luz:** Conector de 4 pines I2C para sensor BH1750 con resistencias pull-up de $4.7\text{ k}\Omega$.
* **Alimentación y Programación:** Puerto USB-C nativo con resistencias de $5.1\text{ k}\Omega$ en CC1/CC2, LDO AMS1117-3.3, botones de Reset, Boot y Usuario, más LED indicador en IO16.
* **Layout y Fabricación:** Placa de 2 capas ($75.0 \times 55.0\text{ mm}$), planos de masa dinámicos en ambas capas, 66 vías de cosido GND, Gerbers RS-274X, taladros Excellon, BOM JLCPCB/PCBWay y CPL.

---

## 2. Archivos Entregables

* [`output/esp32_ld2450_tft_presence_sensor/board.kicad_sch`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/board.kicad_sch)
* [`output/esp32_ld2450_tft_presence_sensor/board.kicad_pcb`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/board.kicad_pcb)
* [`output/esp32_ld2450_tft_presence_sensor/jlcpcb_bom.csv`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/jlcpcb_bom.csv)
* [`output/esp32_ld2450_tft_presence_sensor/pcbway_bom.csv`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/pcbway_bom.csv)
* [`output/esp32_ld2450_tft_presence_sensor/jlcpcb_cpl.csv`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/jlcpcb_cpl.csv)
* [`output/esp32_ld2450_tft_presence_sensor/MANUFACTURING_NOTES.md`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/MANUFACTURING_NOTES.md)
* [`output/esp32_ld2450_tft_presence_sensor/esp32_ld2450_tft_gerbers.zip`](file:///c:/Users/soyko/Documents/Pulse-main/output/esp32_ld2450_tft_presence_sensor/esp32_ld2450_tft_gerbers.zip)
