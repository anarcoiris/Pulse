---
component: orchestration
name: Agent Iteration Loop, Stopping Criteria & Fix Prioritization
---

# Agent Iteration Loop, Stopping Criteria & Fix Prioritization

## Principio de Iteración Determinista

El bucle de refinamiento de hardware asistido por IA opera sobre un ciclo cerrado de generación, auditoría estructurada y remediación:

```
[ Generación / Modificación de Circuito ]
                   │
                   ▼
       [ Evaluación de Reglas ] ──► (finding.schema.json)
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
 ¿Hay Errores Críticos?   ¿Solo Warnings / Info?
         │                   │
      [ SI ]               [ NO ]
         │                   │
 [ Priorizar Fixes ]         ▼
         │           [ CRITERIO DE PARADA ALCANZADO ✅ ]
         ▼
[ Aplicar Patch de Circuito ]
```

## Criterio de Parada Formal

El agente finaliza la iteración de síntesis cuando se satisfacen simultáneamente las siguientes tres condiciones:

1. **Cero Hallazgos Críticos:** `len([f for f in findings if f.severity == 'critical']) == 0`.
2. **100% SCH $\leftrightarrow$ PCB Parity:** Todos los componentes del esquemático poseen su correspondiente footprint ubicado y conectado en PCB (`crosscheck.parity_match == True`).
3. **Puntuación de Inspección Visual $\ge 90\%$:** No existen colisiones de courtyards ni violaciones de keepout de borde.

## Orden de Prioridad de Remediación

Cuando existen múltiples hallazgos simultáneos, el agente debe aplicar los fixes en el siguiente orden estricto de dominios:

| Prioridad | Dominio | Justificación |
|---|---|---|
| **1 (Máxima)** | `ee_fundamentals` | Un error eléctrico fundamental (cortocircuito VCC-GND, falta de desacoplo) invalida cualquier análisis posterior. |
| **2** | `schematic` | Errores de topología lógica (I2C pull-down, EN invertido, strapping flotante). |
| **3** | `component_library` | Pines no coincidentes o números de pin desconocidos. |
| **4** | `pcb` | Separación de pistas, radios de curvatura o proximidad física. |
| **5 (Mínima)** | `dfm` | Advertencias de coste, tipo de componente o sugerencias de optimización. |

## Mecanismo de Promoción de Corpus

Cuando un error de diseño con el mismo `rule_id` se detecta repetidamente en $N \ge 3$ corridas consecutivas sin que el generador LLM lo evite espontáneamente:
1. Se genera un nuevo caso de estudio en `skills/_case-studies/`.
2. Se inyecta la regla correspondiente en el RAG de contexto de síntesis.
3. Se añade una prueba unitaria determinista en `tests/` para bloquear futuras regresiones.
