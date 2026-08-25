---
component: tool-adapter
adapts_from: "KiCad 8.0 / 10.0 S-expressions (.kicad_sch, .kicad_pcb)"
adapts_to: "modelo intermedio neutral (ver _corpus-meta/ARCHITECTURE.md)"
---

# Adaptador: KiCad (.kicad_sch / .kicad_pcb) → Modelo Intermedio

## Responsabilidad
Este adaptador proporciona la traducción bidireccional entre los archivos nativos de KiCad y el modelo intermedio neutral utilizado por el motor de evaluación de reglas (`core/corpus_evaluator.py`).

## Mapeo de Símbolos Esquemáticos (.kicad_sch)

| Propiedad KiCad | Campo Modelo Intermedio | Regla de Conversión |
|---|---|---|
| `(property "Reference" "U1")` | `component.ref` | Identificador unívoco del componente |
| `(property "Value" "ESP32-S3")` | `component.part_value` | Nombre de parte / valor numérico |
| `(property "Footprint" "...")` | `component.package` | Identificador de footprint |
| `(symbol (pin ...))` | `component.pins` | Lista de pines del componente |
| `(pin_name (name "EN"))` | `pin.number` / `pin.name` | Nombre de pin |
| `(pin_type power_in)` | `pin.role: power_in` | Mapeo directo de tipo eléctrico KiCad |
| `(pin_type passive)` | Resuelto por biblioteca | Mapeo mediante `skills/component-library/parts/*.yaml` |

## Mapeo de Footprints y Trazas PCB (.kicad_pcb)

| Elemento KiCad S-expr | Campo Modelo Intermedio |
|---|---|
| `(footprint "..." (at X Y R))` | `component.position = [X, Y]`, `component.rotation = R` |
| `(pad "1" smd rect (at X Y))` | `pin.pad_position = [X, Y]` |
| `(segment (start X1 Y1) (end X2 Y2) (width W) (layer L) (net N))` | `track: {start, end, width, layer, net}` |
| `(via (at X Y) (size S) (drill D) (layers L1 L2) (net N))` | `via: {at, size, drill, net}` |
| `(zone (net N) (layer L) (polygon ...))` | `copper_zone: {net, layer, polygon}` |

## Normalización de Redes KiCad
- Las redes generadas por KiCad con nombres anónimos (p.ej. `Net-(C1-Pad1)`) se mapean a nombres normalizados del modelo intermedio.
- Las etiquetas globales / jerárquicas (p.ej. `+3V3`, `GND`, `I2C_SDA`) mantienen su enlace directo a los roles de red `power_rail`, `ground`, `signal`.
