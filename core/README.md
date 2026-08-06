# kicad_audit — auditoría estructural de `.kicad_pcb`

Herramienta sin dependencias externas (solo Python 3 estándar) para
detectar problemas de integridad de netlist y footprints en archivos
KiCad PCB, antes de llegar al DRC geométrico nativo de KiCad.

## Archivos

- `sexp.py` — parser genérico de s-expressions (formato nativo de KiCad).
- `kicad_audit.py` — extrae footprints/pads/nets y corre las reglas R001–R012.
- `test_kicad_audit.py` — suite de regresión con boards sintéticos mínimos.
- `RULES.md` — sistema de reglas por fases, con pasos de corrección para cada una.

## Uso rápido

```bash
python3 kicad_audit.py mi_placa.kicad_pcb
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
```

## Flujo recomendado

Ver `RULES.md` — resumen: Fase 1 (footprints) → Fase 2 (nets asignadas) →
Fase 3 (topología del circuito) → Fase 4 (DRC nativo de KiCad) → Fase 5
(sincronía con esquemático). No saltar fases; cada una asume que la
anterior está en verde.
