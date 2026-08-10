# Análisis Técnico Crítico: Conector USB-C HRO TYPE-C-31-M-12 (JLCPCB C165948) y Modelado en KiCad

**Fecha:** 10 de Agosto de 2026  
**Componente:** HRO TYPE-C-31-M-12 (Korean Hroparts Elec / LCSC C165948)  
**Footprint KiCad:** `Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12`  
**Datasheet de Referencia:** [HRO TYPE-C-31-M-12 Spec Sheet](http://www.krhro.com/uploads/soft/180320/1-1P320120243.pdf)

---

## 1. Contexto Físico del Conector

El conector **TYPE-C-31-M-12** es un receptáculo híbrido USB-C 2.0 / Power Delivery de **12 pines SMD + 4 pestañas de blindaje THT (SH)**.

Aunque la especificación estándar USB-C define 24 contactos (filas A1..A12 y B1..B12), en los conectores de 16 pines / 12 patillas de perfil reducido para USB 2.0:
* Los pines de masa superior e inferior situados en los extremos del conector se puentean **internamente dentro de la carcasa metálica del conector**.
* El patillaje físico en la placa consta de 12 contactos SMD en una sola fila.

| Pin Físico SMD | Nombre Estándar USB-C | Red Asignada en Esquema | Coordenada Local en Footprint |
| :---: | :---: | :---: | :---: |
| Lead 1 (Extremo Izq.) | **GND** (A1 + B12) | `PWR_GND` | `x = -3.25, y = -4.045` |
| Lead 2 | **VBUS** (A4 + B9) | `PWR_5V_USB` | `x = -2.45, y = -4.045` |
| Lead 3 | **CC1** (A5) | `USB_CC1` | `x = -1.25, y = -4.045` |
| Lead 4 | **D+** (A6) | `USB_ESP_DP` | `x = -0.25, y = -4.045` |
| Lead 5 | **D-** (A7) | `USB_ESP_DN` | `x = +0.25, y = -4.045` |
| Lead 6 | **SBU1** (A8) | `NC` | `x = +1.25, y = -4.045` |
| Lead 7 | **VBUS** (A9 + B4) | `PWR_5V_USB` | `x = +2.45, y = -4.045` |
| Lead 8 | **CC2** (B5) | `USB_CC2` | `x = +1.75, y = -4.045` |
| Lead 9 | **D+** (B6) | `USB_ESP_DP` | `x = +0.75, y = -4.045` |
| Lead 10 | **D-** (B7) | `USB_ESP_DN` | `x = -0.75, y = -4.045` |
| Lead 11 | **SBU2** (B8) | `NC` | `x = -1.75, y = -4.045` |
| Lead 12 (Extremo Der.) | **GND** (A12 + B1) | `PWR_GND` | `x = +3.25, y = -4.045` |

---

## 2. Por qué KiCad Superpone Pads A1 y B12 en Lugar de un Pad Unificado "A1B12"

En la biblioteca oficial de KiCad (`Connector_USB.pretty`), los ingenieros de KiCad toman una decisión de diseño estándar:

1. **Compatibilidad con Esquemas Estándar de USB-C**:
   Los símbolos esquemáticos de USB-C (ej. `Connector:USB_C_Receptacle_USB20`) tienen pines separados titulados `A1`, `B12`, `A12`, `B1`, `A4`, `B9`, `A9`, `B4`.
2. **Superposición Coincidente**:
   Para mantener la compatibilidad 1:1 entre el símbolo esquemático estándar y el footprint físico sin tener que renombrar pines a nombres no estándar como `A1B12`, **KiCad coloca dos definiciones de pad `(pad ...)` con las mismas coordenadas físicas exactas**.

Extraído del archivo oficial `.kicad_mod` de KiCad:
```sexpr
(pad "A1" smd roundrect (at -3.25 -4.045) (size 0.6 1.45) ...)
(pad "B12" smd roundrect (at -3.25 -4.045) (size 0.6 1.45) ...)
```

---

## 3. Desglose de Errores Encontrados y Soluciones Aplicadas

### Error #1: Corrupción de Redes por Expresión Regular en `pcb_layout.py`
* **Síntoma**: Al hacer clic en KiCad, aparecían cruces de redes extraños en `A1` y `B12`.
* **Causa Raíz**: En `RawFootprint.to_sexpr()`, la búsqueda regex utilizaba `r'(\(pad\s+"?' + re.escape(p_num) + r'"?...)'`. Al procesar el pad de pin de header `"1"`, la cadena `"?1"?` coincidía por subcadena con `(pad "A1"` y `(pad "B12"`. Esto inyectaba `PWR_5V_USB` sobre pads de masa `PWR_GND`.
* **Solución**: Ajustar el patrón regex a la coincidencia estricta delimitada por comillas dobles: `r'(\(pad\s+"' + re.escape(p_num) + r'"\s+...)'`.

### Error #2: Menú de Aclaración de Selección en KiCad GUI
* **Síntoma**: Al hacer clic sobre la patilla izquierda del USB-C, KiCad pregunta *"Clarify Selection: Pad A1 or Pad B12"*.
* **Conclusión**: **Comportamiento 100% normal y esperado en KiCad** debido al apilamiento intencional de dos pads en las mismas coordenadas para soportar el mapa esquemático USB-C.

### Error #3: Advertencia `[starved_thermal]` en DRC
* **Síntoma**: DRC avisa que los pads `A1` y `B12` tienen solo 1 radio de alivio térmico.
* **Causa Raíz**: El ancho del radio térmico estándar (0.35 mm) no cabe cómodamente entre los pads contiguos de 0.6 mm con separación de 0.25 mm.
* **Solución**: Configurar la conexión del vertido `PWR_GND` a **Solid Fill** (Relleno Sólido) o reducir los radios térmicos a `thermal_gap 0.15mm` y `thermal_bridge_width 0.20mm`.

---

## 4. Validación para Fabricación y Ensamble SMT en JLCPCB

* **Stencil de Pasta Solder Mask (`F.Paste`)**: Dado que `pad "A1"` y `pad "B12"` tienen exactamente la misma geometría (`size 0.6 1.45`) en `at -3.25 -4.045`, en el archivo Gerber de máscara de pasta de soldadura se genera una única ventana rectangular limpia.
* **Ensamble SMT**: JLCPCB posiciona la pieza `C165948` sin ningún problema de alineación.
