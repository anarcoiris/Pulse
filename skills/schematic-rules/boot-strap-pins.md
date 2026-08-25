---
rule_id: schematic.mcu.boot_strap_pins
domain: schematic
name: MCU Boot Strapping Pins & Hardware Reset
---

# MCU Boot Strapping Pins & Hardware Reset

## Contexto & Mecanismo de Muestreo

Los microcontroladores modernos (como la familia Espressif ESP32, ESP32-S3, STM32) leen el estado lógico de un conjunto específico de pines durante la inicialización de hardware para determinar:
1. **Modo de Arranque (Boot Mode):** Ejecutar desde Flash SPI interna/externa (Normal SPI Boot) vs. Descarga de firmware por ROM UART/USB (Download Boot).
2. **Voltaje de Flash / VDD_SPI:** Selección de nivel de señal $3.3\,\text{V}$ vs. $1.8\,\text{V}$ (p.ej. `GPIO45` en ESP32-S3).
3. **Impresión de Logs de ROM:** Habilitación de mensajes de debug en UART0 (p.ej. `GPIO46` en ESP32-S3).

```
                 +3.3V
                   |
                 [10kΩ] (Pull-up)
                   |
GPIO0 (BOOT) ──────+───────[ Switch ]────── GND (Pulsador para Download Boot)
```

## Diferencia Fundamental: `BOOT` vs `EN`

| Pin | Rol Semántico | Nivel Normal | Nivel Activo / Secundario | Circuito Típico |
|---|---|---|---|---|
| **EN (CHIP_PU)** | `reset_enable` | `HIGH` ($3.3\,\text{V}$) | `LOW` ($0\,\text{V}$): Chip apagado en reset | Pull-up $10\,\text{k}\Omega$ a 3.3V + condensador $1\,\mu\text{F}$ a GND (RC delay $t_{delay} \approx 10\,\text{ms}$) + botón Reset a GND |
| **GPIO0 (BOOT)** | `boot_strap` | `HIGH` ($3.3\,\text{V}$): SPI Boot | `LOW` ($0\,\text{V}$): UART Download Boot | Pull-up $10\,\text{k}\Omega$ a 3.3V + botón Boot a GND |

## Puntos Críticos de Diseño

1. **Evitar Cargas Capacitivas Pesadas en Pines de Strapping:**
   - Un condensador en paralelo en `GPIO0` ralentiza el flanco de subida y puede causar que el MCU muestree un nivel bajo espurio al liberarse el reset `EN`, entrando en modo download de forma intermitente.
2. **Nunca Cortocircuitar Strapping Directamente a GND:**
   - Si `GPIO0` está unido permanentemente a GND sin pulsador, el MCU jamás podrá arrancar la aplicación de usuario tras un reinicio de energía.
