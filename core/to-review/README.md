# kicad_audit — auditoría estructural de `.kicad_pcb`

Herramienta sin dependencias externas (solo Python 3 estándar) para
detectar problemas de integridad de netlist y footprints en archivos
KiCad PCB, antes de llegar al DRC geométrico nativo de KiCad.

## Archivos

- `sexp.py` — parser genérico de s-expressions (formato nativo de KiCad).
- `kicad_audit.py` — extrae footprints/pads/nets del PCB y corre las reglas R001–R014.
- `sch_pcb_crosscheck.py` — compara `.kicad_sch` contra `.kicad_pcb`: cobertura de referencias, cobertura de nombres de red, y (crítico) si los símbolos del esquemático tienen pines reales definidos.
- `test_kicad_audit.py` — suite de regresión del auditor de PCB con boards sintéticos mínimos.
- `test_sch_pcb_crosscheck.py` — suite de regresión del cross-check esquemático↔PCB.
- `RULES.md` — sistema de reglas por fases, con pasos de corrección para cada una.

## Uso rápido

Auditoría de PCB:

```bash
python3 kicad_audit.py mi_placa.kicad_pcb
```

Cross-check esquemático↔PCB (Fase 5):

```bash
python3 sch_pcb_crosscheck.py mi_placa.kicad_sch mi_placa.kicad_pcb
```

Con salida JSON para tracking entre sesiones:

```bash
python3 kicad_audit.py mi_placa.kicad_pcb --json audit_2026-08-05.json
```

Filtrando por fase (ver `RULES.md` para el mapeo fase→reglas):

```bash
python3 kicad_audit.py mi_placa.kicad_pcb --rule R001,R008,R012
```

## Tests

```bash
python3 test_kicad_audit.py
python3 test_sch_pcb_crosscheck.py
```

## Flujo recomendado

Ver `RULES.md` — resumen: Fase 1 (footprints) → Fase 2 (nets asignadas) →
Fase 3 (topología del circuito) → Fase 3b (conectividad real de cobre +
clearance de taladros, R013/R014) → Fase 4 (DRC nativo de KiCad) → Fase 5
(sincronía con esquemático). No saltar fases; cada una asume que la
anterior está en verde.

## Reglas implementadas

R001–R012: integridad de footprints y modelo de netlist (no requieren
geometría). R013: simula el ratsnest (¿el cobre dibujado realmente une
los pads de cada red?) mediante union-find sobre coordenadas. R014:
clearance taladro-a-taladro por distancia euclidiana. R013/R014 fueron
validadas contra un DRC report real de KiCad — el valor de clearance
calculado coincidió exactamente (0.0811mm) con el reportado por KiCad
para el mismo par físico.

**Nota de integridad importante:** si comparas la salida de este script
contra un DRC report generado en otra sesión, primero confirma que ambos
corresponden al mismo estado guardado del archivo — un board editado
entre la generación del DRC y la ejecución de este script producirá
hallazgos que ya no coinciden 1:1 (esto ocurrió durante el desarrollo:
un DRC report tenía a `Header_000` en coordenadas ~15mm distintas al
archivo `.kicad_pcb` finalmente analizado).
