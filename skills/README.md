# Electronic Design Knowledge Base & Skills — Pulse

## Start Here
1. [`_corpus-meta/ARCHITECTURE.md`](_corpus-meta/ARCHITECTURE.md) — Architecture, decoupling rules, and the neutral intermediate model.
2. [`_corpus-meta/ROADMAP.md`](_corpus-meta/ROADMAP.md) — Phased roadmap, rule priorities, and real case evidence.
3. [`_case-studies/`](_case-studies/) — Annotated real runs (e.g. [`_case-studies/pulselab_zero_run2.md`](_case-studies/pulselab_zero_run2.md)).

## Directory Structure
```
skills/
├── _corpus-meta/          ← Knowledge base architecture & roadmap
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
├── _case-studies/         ← Annotated real synthesis runs
│   └── pulselab_zero_run2.md
├── ee-fundamentals/       ← Physics & calculations (decoupling, pull-up/down)
│   └── decoupling-per-ic.md
├── schematic-rules/       ← ERC, topology & functional patterns
│   └── power-on-reset-esp32.md
├── tool-adapter/          ← Adapters translating tool JSON to neutral intermediate model
│   └── netlist-propio/
│       └── SKILL.md
├── evaluation/            ← Finding schemas & feedback evaluation rules
│   └── SKILL.md
└── pcb-rules/             ← DRC, stack-up, SI/EMC rules (roadmap Phase 3)
```

## Active Rules & Skills Status

- `schematic.power_on_reset.en_pullup` — [`schematic-rules/power-on-reset-esp32.md`](schematic-rules/power-on-reset-esp32.md) (Critical)
- `ee_fundamentals.decoupling.per_ic_100nf` — [`ee-fundamentals/decoupling-per-ic.md`](ee-fundamentals/decoupling-per-ic.md) (Warning / MCU Critical)
- `tool_adapter.netlist_propio` — [`tool-adapter/netlist-propio/SKILL.md`](tool-adapter/netlist-propio/SKILL.md)
- `evaluation` — [`evaluation/SKILL.md`](evaluation/SKILL.md)
