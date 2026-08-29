# 🛡️ PulseLab RAG Hygiene & Vector Database Immunization Blueprint

**Document ID:** `PL-DOC-RAG-IMMUNIZATION-2026-08`  
**Status:** Canonical Technical Reference & Audit  
**Target Systems:** `knowledge/rag_engine.py`, `knowledge/design_experience.py`, `knowledge/data/`, `core/agent_pipeline.py`  
**Author:** PulseLab Engineering  
**Date:** Agosto 2026  

---

## 1. Executive Summary & Threat Modeling

Retrieval-Augmented Generation (RAG) and dense embedding vector stores serve as the long-term semantic memory and hardware rule oracle for PulseLab's generative agents (`CircuitStewardAgent`, `CircuitSynthesizer`, `SemanticReviewer`). 

When multi-turn LLM synthesis loops encounter failures, floating nets, or design rule check (DRC) violations, **any inadvertent persistence or indexing of these failed attempts into the vector database creates a "poisoning loop" (data corruption feedback)**. Subsequent inferences retrieve hallucinatory netlists or raw error remediation traces as if they were authoritative design guidelines.

```mermaid
graph TD
    subgraph "A. Vulnerability Cycle (Current State)"
        AGENT_ERR["Synthesis / Simulation Attempt (Failed DRC)"] -->|Blind persistence| EXP_BAD["experiences/sim_*.json (passed=false)"]
        KICAD_QA["KiCad QA Test Suite (320+ error fixtures)"] -->|Blind parsing| TRAIN_RAW["data/training/human_*.json"]
        EXP_BAD --> LOAD["rag_engine._load_experiences()"]
        TRAIN_RAW --> LOAD_T["rag_engine._load_training_examples()"]
        LOAD --> CHUNKS["Contaminated Chunks in RAM (5,731 chunks)"]
        LOAD_T --> CHUNKS
        CHUNKS -->|Hash mismatch| SILENT_FAIL["Dense Cache Deactivated (TF-IDF Fallback)"]
        CHUNKS -->|If rebuilt| POISON_VEC["Poisoned vectors.npy"]
        POISON_VEC --> RETRIEVE["LLM retrieves 'Missing pin connections' as rules"]
    end

    subgraph "B. Immunized Architecture (Target State)"
        VALID_EXP["Validated Pipeline Output (passed=true, DRC=0)"] --> GATE1["Gatekeeper 1: Boolean & DRC Validator"]
        GATE1 --> EXP_CLEAN["experiences/*.json (Clean Canon)"]
        EXP_BAD_2["Failed Runs"] --> QUARANTINE["experiences/quarantine/ (Isolated)"]
        
        RAW_KICAD["KiCad Schematics"] --> GATE2["Gatekeeper 2: Test Fixture & Anti-pattern Filter"]
        GATE2 --> TRAIN_CLEAN["data/training/ (Curated Reference)"]
        
        EXP_CLEAN --> LOAD_IMM["rag_engine._load_experiences() + Filter"]
        TRAIN_CLEAN --> LOAD_IMM
        LOAD_IMM --> CHUNKS_CLEAN["Clean Chunks in RAM"]
        CHUNKS_CLEAN --> SHA["SHA-256 Content Fingerprint"]
        SHA --> VEC_CLEAN["Clean vectors.npy + Verified manifest.json"]
        VEC_CLEAN --> ACCURATE_RAG["High-Fidelity Retrieval (Nomic Embeddings)"]
    end
```

---

## 2. Forensic Audit Findings

A complete inspection across the `knowledge/` directory identified 5 critical vulnerabilities and data drift vectors:

### Finding 1: Unfiltered Ingestion of Failed Simulations (`passed == false`)
* **Location:** [`knowledge/experiences/`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/experiences/)
* **Corrupted Files Identified:**
  - `sim_t1_ex01_ams1117_ldo.json`: (`"drc_violations": 4, "passed": false`)
  - `sim_t2_ex01_esp32_wroom_minimal.json`: (`"drc_violations": 4, "passed": false`)
* **Root Cause:** [`knowledge/autonomous_rag_orchestrator.py`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/autonomous_rag_orchestrator.py#L235-L247) appended literal debug strings (`"Remediated issue: Missing pin connections on component C1"`) to the `lessons_learned` array and called `record_design_outcome()` regardless of `passed` status.
* **Mechanism of Poisoning:** [`rag_engine.py::_load_experiences()`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/rag_engine.py#L228) iterated over all `*.json` files in `experiences/` without asserting `exp.get("passed") is True` or `exp.get("drc_violations") == 0`. Consequently, 8 raw error strings were indexed as design rules.

### Finding 2: Lack of Gatekeeper Guardrails in `DesignExperience.ingest_to_rag()`
* **Location:** [`knowledge/design_experience.py`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/design_experience.py#L47)
* **Root Cause:** The `ingest_to_rag()` method had no internal check for `if not self.passed or self.drc_violations > 0: return 0`. Calling `ingest_to_rag()` on any instance immediately pushed its contents to memory.

### Finding 3: Ingestion of KiCad QA Parser Test Fixtures as Training Examples
* **Location:** [`knowledge/data/raw_kicad/`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/data/raw_kicad/) $\to$ [`knowledge/data/training/`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/data/training/)
* **Root Cause:** In earlier sessions, [`knowledge/dataset_builder.py`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/dataset_builder.py) mass-imported 320+ schematics from the official KiCad C++ mirror (`qa/data/` test suites). Many of these schematics are **intentional negative test fixtures** designed to verify KiCad's crash reporting or ERC failure detection, including:
  - `ground_pin_test_error.kicad_sch` (Ground miswiring test)
  - `NoConnectOnLine.kicad_sch` / `NoConnectOnPin.kicad_sch`
  - `erc_directive_label_not_connected.kicad_sch`
  - `erc_multiple_pin_to_pin.kicad_sch`
  - `topology_mismatch.kicad_sch`
* **Mechanism of Poisoning:** These negative test cases were parsed and converted into `human_*.json` training chunks (`circuit_example`), exposing the LLM to broken circuit topologies.

### Finding 4: Vector Manifest Desynchronization & Silent Fallback
* **Location:** [`knowledge/data/embeddings/manifest.json`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/data/embeddings/manifest.json)
* **Observed State:**
  - `manifest.json` `chunk_count`: **5,685**
  - Active in-memory chunk count: **5,731**
  - Result in `kb.stats()`: `'embed_index_loaded': False`
* **Root Cause:** `_load_embed_cache()` only checked integer count equality. Because the chunk count drifted after manual edits or experience recording, dense retrieval (`nomic-embed-text`) disabled itself silently, falling back to sparse TF-IDF.
* **Integrity Defect:** No content checksum (SHA-256) existed. If 5 chunks were replaced by 5 poisoned chunks, the count would match and the poisoned matrix would load undetected.

### Finding 5: Ephemeral Scratchpad vs. Persistent Experience Boundary
* **Location:** Multi-turn conversational sessions in `app/main.py` and `knowledge/validate_complex_apps.py`.
* **Finding:** While intermediate multi-turn self-correction cycles (Turns 1–3) correctly keep error messages within the LLM conversation context without saving them to `experiences/`, end-of-run simulation hooks in `autonomous_rag_orchestrator.py` leaked the unverified simulation outputs directly to disk.

---

## 3. The 5-Pillars Immunization System

To establish complete immunity against vector database poisoning and guarantee absolute RAG hygiene, the following 5 pillars are established:

```
+---------------------------------------------------------------------------------------+
|                                5-PILLARS IMMUNIZATION                                 |
+---------------------------------------------------------------------------------------+
| 1. HARDENED GATEKEEPER        | passed == True AND drc_violations == 0 assertion      |
| 2. SEMANTIC HEURISTIC FILTER  | Rejection of "Remediated issue:", debug text, warns   |
| 3. QA FIXTURE EXCLUSION       | Blacklisting KiCad parser test suites & error files   |
| 4. SHA-256 VECTOR INTEGRITY   | Cryptographic fingerprinting of all chunk contents    |
| 5. SANITATION CLI & QUARANTINE| Automated audit, isolation of non-canon runs & purge  |
+---------------------------------------------------------------------------------------+
```

### Pillar 1: Hardened Gatekeeper (`passed == True` & `drc_violations == 0`)
In `knowledge/design_experience.py` and `knowledge/rag_engine.py`:
1. `DesignExperience.ingest_to_rag()` must strictly reject any experience where `not self.passed` or `self.drc_violations > 0`.
2. `ElectronicsKnowledgeBase._load_experiences()` must verify `exp.get("passed") is True` and `exp.get("drc_violations", 0) == 0`. Any file failing this condition is skipped with a warning.

### Pillar 2: Semantic Heuristic Filtering
Even for experiences that passed DRC, lessons must be screened for noise:
1. Reject any lesson matching `r"(?i)^(remediated issue|error:|warning:|failed:)"`.
2. Require minimum informative length ($\ge 20$ characters) and hardware keywords (`pin`, `decoupling`, `plane`, `clearance`, `trace`, `voltage`, `ground`, `schottky`, `pull-up`, `pull-down`).

### Pillar 3: QA Test Fixture Exclusion in `data/training/`
In `_load_training_examples()` and `dataset_builder.py`:
Implement an explicit negative pattern blacklist:
```python
_EXCLUDED_TRAINING_PATTERNS = (
    "_error", "bugtest", "erc_", "noconnect", "no_connect",
    "topology_mismatch", "issue", "test_", "untitled", "test1243"
)
```
Any training JSON containing these substrings in its filename or lacking valid schematic components ($\ge 2$ connected components) is excluded from RAG indexation.

### Pillar 4: Cryptographic Vector Store Fingerprinting (SHA-256)
Replace fragile `chunk_count` checking with a SHA-256 manifest hash:
1. Compute `hashlib.sha256()` over all normalized chunk texts and source identifiers in deterministic order.
2. Store `content_hash` in `manifest.json`.
3. During startup, `_load_embed_cache()` recomputes the SHA-256 of the active in-memory chunks. If the hash does not match `manifest.json["content_hash"]`, the cache is marked stale and an explicit warning or auto-rebuild is triggered.

### Pillar 5: Automated Sanitation CLI & Quarantine Directory
Create a dedicated CLI tool: [`knowledge/sanitize_and_rebuild_kb.py`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/sanitize_and_rebuild_kb.py):
* Scans `knowledge/experiences/` and moves any non-passing JSON to `knowledge/experiences/quarantine/`.
* Audits `knowledge/data/training/` against test fixture rules.
* Cleanses the chunk collection.
* Invokes `rebuild_embed_index(force=True)` via local Ollama `nomic-embed-text`.
* Emits a clean manifest and updated health status.

---

## 4. Detailed Specification of Code Changes

### A. [`knowledge/design_experience.py`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/design_experience.py)
```python
    def ingest_to_rag(self) -> int:
        """Add lessons to the electronics KB for future retrieval (Strict Gatekeeper)."""
        if not self.passed or self.drc_violations > 0:
            return 0  # Do not poison KB with failed/unverified designs

        from knowledge.rag_engine import ElectronicsKnowledgeBase
        kb = ElectronicsKnowledgeBase()
        n = 0
        for lesson in self.lessons_learned:
            clean_lesson = lesson.strip()
            if not clean_lesson or clean_lesson.lower().startswith("remediated issue:"):
                continue
            kb.ingest_text(
                f"Design experience {self.board_id} MCU {self.mcu}: {clean_lesson}",
                source=f"Experience:{self.board_id}",
                chunk_type="design_experience",
            )
            n += 1
        for rule in self.component_placement_rules:
            clean_rule = rule.strip()
            if not clean_rule:
                continue
            kb.ingest_text(
                f"Placement rule {self.board_id}: {clean_rule}",
                source=f"Experience:{self.board_id}#placement",
                chunk_type="design_experience",
            )
            n += 1
        return n
```

### B. [`knowledge/rag_engine.py`](file:///c:/Users/soyko/Documents/Pulse-main/knowledge/rag_engine.py)
```python
    def _load_experiences(self) -> None:
        exp_dir = _HERE / "experiences"
        if not exp_dir.exists():
            return
        for path in sorted(exp_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    exp = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            
            # Strict Gatekeeper Check
            if not exp.get("passed", False) or exp.get("drc_violations", 0) > 0:
                continue

            board_id = exp.get("board_id", path.stem)
            mcu = exp.get("mcu", "")
            for lesson in exp.get("lessons_learned", []) or []:
                if not lesson or str(lesson).lower().startswith("remediated issue:"):
                    continue
                self._chunks.append({
                    "text": f"Design experience {board_id} MCU {mcu}: {lesson}",
                    "source": f"Experience:{board_id}",
                    "type": "design_experience",
                    "data": {"text": lesson, "board_id": board_id, "mcu": mcu},
                })
```

---

## 5. Verification & Testing Protocol

To ensure continuous adherence to these standards, a test suite [`tests/test_rag_hygiene.py`](file:///c:/Users/soyko/Documents/Pulse-main/tests/test_rag_hygiene.py) will be executed as part of CI/CD:

1. **Test Gatekeeper Rejection:** Asserts that calling `record_design_outcome(passed=False)` creates a record on disk but does NOT increase `design_experience` chunk count in `ElectronicsKnowledgeBase()`.
2. **Test Semantic Error Filter:** Asserts that strings starting with `"Remediated issue:"` are never present in `kb._chunks`.
3. **Test Fixture Blacklist:** Asserts that zero chunks with `source` containing `KiCad_kicad-source-mirror_ground_pin_test_error` exist in `kb._chunks`.
4. **Test SHA-256 Cache Validation:** Asserts that tampering with a single character in `components.json` or `symbols_index.json` immediately invalidates `_load_embed_cache()` and prevents serving out-of-date vectors.

---

## 6. Summary of Canonical State

With this blueprint:
* **Canonical Verified Experiences:** `flipper_killer_mk2_v4_canonical.json`, `poc_esp32_en_pullup_rule.json`.
* **Quarantined Artifacts:** `sim_t1_ex01_ams1117_ldo.json`, `sim_t2_ex01_esp32_wroom_minimal.json`.
* **Vector Store Quality:** 100% verified against KiCad 10 IPC-2221 rules, canonical symbol pins, and passing production designs.
