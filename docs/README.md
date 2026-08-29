# PulseLab Master Documentation Index

> **Role:** entry / master map  
> **Status:** active  
> **Source of truth for:** complete repository documentation hierarchy and structural navigation  
> **Last verified:** 2026-08-30  

---

## 🚀 Quick Navigation

| Need | Document / Location | Description |
|------|---------------------|-------------|
| **Current Sprint** | [`status/CURRENT_SPRINT.md`](./status/CURRENT_SPRINT.md) | Active sprint roadmap, completion matrix, and next actions |
| **System Status & Metrics** | [`status/FORGE_STATUS.md`](./status/FORGE_STATUS.md) | Verified metrics (198 unit tests, RAG chunks, 36 FastMCP tools) |
| **Product Roadmap** | [`roadmap.md`](./roadmap.md) | Multi-phase development roadmap and milestone progression |
| **System Architecture** | [`architecture/APP_ARCHITECTURE.md`](./architecture/APP_ARCHITECTURE.md) | Core component isolation, solver pipelines, and data flow |
| **Agent Knowledge & Skills** | [`../skills/README.md`](../skills/README.md) | Structured domain knowledge, EE rules, and intermediate models |

---

## 🏗️ Architecture & Engineering Blueprints

| Category | Document | Description |
|---|---|---|
| **Docker & Cloud Deployment** | [`DEPLOYMENT_DOCKER_GHCR.md`](./DEPLOYMENT_DOCKER_GHCR.md) | GHCR container publishing, Docker Compose stack, and Caddy reverse proxy. |
| **Hardware Design Rules** | [`DESIGN_RULES_AND_TROUBLESHOOTING_GUIDE.md`](./DESIGN_RULES_AND_TROUBLESHOOTING_GUIDE.md) | IPC-2221 design rules, clearances, thermal dissipation, and DRC troubleshooting. |
| **Canonical Pinouts & Coexistence** | [`FLIPPER_ZERO_CANONICAL_PINOUT_AND_MULTIBOARD_COEXISTENCE.md`](./FLIPPER_ZERO_CANONICAL_PINOUT_AND_MULTIBOARD_COEXISTENCE.md) | Pin maps, SPI bus isolation, and multi-radio coexistence guidelines. |
| **Backend Consolidation** | [`UNIFIED_BACKEND_CONSOLIDATION_BLUEPRINT.md`](./UNIFIED_BACKEND_CONSOLIDATION_BLUEPRINT.md) | Master EDA service kernel architecture and unified lifecycle. |
| **RAG Hygiene & Immunization** | [`RAG_HYGIENE_AND_IMMUNIZATION_BLUEPRINT.md`](./RAG_HYGIENE_AND_IMMUNIZATION_BLUEPRINT.md) | Vector database hygiene, anti-hallucination guards, and verification protocols. |
| **Domain Audits & Degradation** | [`CODEBASE_AUDIT_DOMAINS_AND_ARCHITECTURAL_DEGRADATION.md`](./CODEBASE_AUDIT_DOMAINS_AND_ARCHITECTURAL_DEGRADATION.md) | Architectural boundary audits and technical debt controls. |
| **Pipelines & Web API** | [`PIPELINES_INVENTORY_AND_WEB_API_AUDIT.md`](./PIPELINES_INVENTORY_AND_WEB_API_AUDIT.md) | Complete inventory of backend endpoints and synthesis pipelines. |
| **Autonomous Learning** | [`autonomous_learning_curriculum.md`](./autonomous_learning_curriculum.md) | Curriculum for autonomous reinforcement and RAG experience ingestion. |

---

## 🛠️ Workflows & How-To Guides

| Task | Guide |
|------|-------|
| **Gerber / CAM Export & DRC** | [`workflows/howto/fabrication_pipeline.md`](./workflows/howto/fabrication_pipeline.md) |
| **ESP32 DevBoard Synthesis** | [`workflows/howto/esp32_devboard_mcp.md`](./workflows/howto/esp32_devboard_mcp.md) |
| **Component & Footprint DB** | [`workflows/howto/component_management.md`](./workflows/howto/component_management.md) |
| **Forge Studio Debug REPL** | `python -m studio` (Session transcripts stored under `knowledge/data/llm_sessions/`) |

---

## 🧠 Knowledge Base & Agent Skills (`skills/`)

The [`skills/`](../skills/README.md) directory houses domain-isolated rules and skills for LLM hardware synthesis:

- **Corpus Architecture**: [`../skills/_corpus-meta/ARCHITECTURE.md`](../skills/_corpus-meta/ARCHITECTURE.md)
- **Skill Roadmap**: [`../skills/_corpus-meta/ROADMAP.md`](../skills/_corpus-meta/ROADMAP.md)
- **Schematic Rules**: [`../skills/schematic-rules/power-on-reset-esp32.md`](../skills/schematic-rules/power-on-reset-esp32.md)
- **EE Fundamentals**: [`../skills/ee-fundamentals/decoupling-per-ic.md`](../skills/ee-fundamentals/decoupling-per-ic.md)
- **Tool Adapter**: [`../skills/tool-adapter/netlist-propio/SKILL.md`](../skills/tool-adapter/netlist-propio/SKILL.md)
- **Evaluation Rules**: [`../skills/evaluation/SKILL.md`](../skills/evaluation/SKILL.md)
- **Annotated Case Studies**: [`../skills/_case-studies/pulselab_zero_run2.md`](../skills/_case-studies/pulselab_zero_run2.md)

---

## 🔬 Research & Specialized Studies (`docs/research/`)

| Document | Purpose |
|---|---|
| **Electromagnetic Coupling Report** | [`research/electromagnetic_coupling_report.tex`](./research/electromagnetic_coupling_report.tex) | High-frequency pulse and near-field resonant inductive coupling physics. |
| **Steward Validation Experience Bridge** | [`research/steward_validation_experience_bridge.md`](./research/steward_validation_experience_bridge.md) | Automatic conversion of validation runs into persistent RAG design experiences. |
| **USB-C High-Speed Routing** | [`research/usb_c_hro_analysis.md`](./research/usb_c_hro_analysis.md) | USB-C 16-pin impedance control and differential pair routing parameters. |
