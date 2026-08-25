---
rule_id: pcb.stackup.two_layer_reference_plane
domain: pcb
name: PCB Layer Stackup & Ground Return Plane Basics
---

# PCB Layer Stackup & Ground Return Plane Basics

## Principios Físicos de Retorno de Corriente

En circuitos de alta frecuencia o con transistores de conmutación rápida (como microcontroladores a 240 MHz o radios RF a 433/915 MHz), la corriente de retorno de señal **no sigue la ruta de menor resistencia DC**, sino **la ruta de menor inductancia AC**, que es el plano conductor situado directamente debajo de la traza de señal.

```
F.Cu (Top Layer)   :   [Signal Track] ─────────────► Current I_signal
Dielectric (FR-4)  :   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ (h = 1.6mm / 0.2mm)
B.Cu (Bottom Layer):   ◄──────────────────────────── Return Current I_return (0V GND)
```

## Comparativa de Stackups Estándar

### 1. Stackup 2 Capas ($1.6\,\text{mm}$ FR-4)
- **Top Layer (F.Cu):** Señales prioritarias, alimentación y componentes SMD.
- **Bottom Layer (B.Cu):** Plano de masa (GND) continuo.
- **Regla de Oro:** Evitar ranuras largas en el plano inferior que obliguen a la corriente de retorno a rodear la ranura, incrementando el área de bucle y la radiación EMI.

### 2. Stackup 4 Capas ($1.6\,\text{mm}$ / $1.0\,\text{mm}$ JLC04161H)
- **L1 (Top / F.Cu):** Señales de alta velocidad (SPI, USB D+/D-, RF).
- **L2 (Inner 1 / In1.Cu):** Plano de masa GND ininterrumpido (0V Reference Plane).
- **L3 (Inner 2 / In2.Cu):** Plano de potencia (3.3V / 5V Power Plane).
- **L4 (Bottom / B.Cu):** Señales de baja velocidad y componentes auxiliares.

## Recomendaciones de Diseño en PulseLab
1. Todo diseño genera automáticamente planos de masa en ambas capas (`core/copper_zone_manager.py`).
2. Se inyecta una matriz de vías de cosido inter-capa (Via Stitching) con paso de $5.0\,\text{mm}$ para mantener top y bottom al mismo potencial de referencia.
