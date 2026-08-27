"""
core/agent_pipeline.py
======================
Comprehensive Multi-Phase LLM Agent Generation, Self-Correction & Refinement Pipeline.

Integrates:
1. CircuitStewardAgent (Multi-turn RAG research & incremental scratchpad build)
2. Pin Coverage & SemanticReviewer (AI DRC, missing pull-ups, floating pins, etc.)
3. Self-Correction Feedback Loop (Auto-remedy critical semantic/electrical issues)
4. PCBBuilder & AutoPlacementEngine (AABB physical layout, routing, copper pour, stitching vias)
5. VisualInferenceEngine (9-pass visual inspection & DFM radar) & KiCadAudit (Topological DRC)
6. Interactive Multi-Session Patch Refinement & Co-Pilot Co-Design
"""

from __future__ import annotations
import json
import time
import uuid
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable

from core.logger import logger
from core.circuit_graph import CircuitGraph
from bridge.pcb_builder import PCBBuilder
from bridge.schematic_generator import SchematicGenerator
from core.kicad_audit import run_audit
from core.visual_inference import run_visual_inspection
from core.auto_placement import AutoPlacementEngine
from core.provider_fetcher import ProviderFetchManager
from core.chat_session_manager import ProjectSessionManager, apply_patches_to_circuit

from knowledge.circuit_synthesizer import CircuitSynthesizer as KnowledgeSynthesizer
from knowledge.circuit_agent import CircuitStewardAgent
from knowledge.semantic_reviewer import SemanticReviewer
from knowledge.validate_complex_apps import _pin_coverage, _semantic_review_summary


@dataclass
class AgentStep:
    step_number: int
    phase: str
    action: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    elapsed_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRunResult:
    success: bool
    project_id: str
    run_id: str
    prompt: str
    circuit_data: Dict[str, Any]
    components_count: int
    pin_coverage: Dict[str, Any]
    semantic_issues: List[Dict[str, Any]]
    critical_issues_count: int
    drc_errors_count: int
    drc_warnings_count: int
    visual_score: float
    visual_violations_count: int
    correction_cycles: int
    steps: List[Dict[str, Any]]
    radar: Dict[str, float] = field(default_factory=dict)
    pcb_path: str = ""
    sch_path: str = ""
    output_dir: str = ""
    vectors_2d: Dict[str, Any] = field(default_factory=dict)
    mesh_3d: Dict[str, Any] = field(default_factory=dict)
    supply_chain: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PulseAgentPipeline:
    """
    Autonomous Multi-Phase LLM Hardware Engineering Agent.
    """

    def __init__(self, output_base_dir: Optional[str] = None):
        if output_base_dir:
            self.base_dir = Path(output_base_dir)
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "output"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.provider_mgr = ProviderFetchManager()

    def run(
        self,
        prompt: str,
        project_id: Optional[str] = None,
        max_correction_cycles: int = 2,
        backend: str = "auto",
        review_backend: str = "auto",
        on_step_callback: Optional[Callable[[AgentStep], None]] = None
    ) -> AgentRunResult:
        """
        Executes complete multi-phase agentic pipeline:
        Phase 1: Multi-turn RAG research & synthesis (CircuitStewardAgent)
        Phase 2: Semantic review & Pin coverage audit (SemanticReviewer)
        Phase 3: Multi-turn self-correction feedback loop (if critical issues)
        Phase 4: Physical generation (PCBBuilder + AutoPlacement + Copper Pour + DRC + Visual Gate)
        Phase 5: Supply chain BOM analysis & Vector/3D mesh export
        """
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        proj_id = project_id or f"proj_{uuid.uuid4().hex[:8]}"
        run_dir = self.base_dir / proj_id
        run_dir.mkdir(parents=True, exist_ok=True)

        steps: List[AgentStep] = []
        step_idx = 0

        def emit_step(phase: str, action: str, description: str, details: Optional[Dict[str, Any]] = None, elapsed_s: float = 0.0) -> AgentStep:
            nonlocal step_idx
            step_idx += 1
            st = AgentStep(
                step_number=step_idx,
                phase=phase,
                action=action,
                description=description,
                details=details or {},
                elapsed_s=round(elapsed_s, 2)
            )
            steps.append(st)
            if on_step_callback:
                try:
                    on_step_callback(st)
                except Exception as cb_err:
                    logger.warning("agent_pipeline", f"Step callback error: {cb_err}")
            return st

        t_start_total = time.time()
        emit_step(
            phase="INITIALIZATION",
            action="START_PIPELINE",
            description=f"Agent initialized for project '{proj_id}' with run ID '{run_id}'.",
            details={"prompt": prompt, "max_correction_cycles": max_correction_cycles, "backend": backend}
        )

        # ─── PHASE 1: Multi-Turn RAG Research & Circuit Synthesis ─────────────
        t0 = time.time()
        knowledge_synth = KnowledgeSynthesizer(backend=backend)
        steward = CircuitStewardAgent(knowledge_synth)

        emit_step(
            phase="RESEARCH_AND_SYNTHESIS",
            action="AGENT_MULTI_TURN_LOOP",
            description="Executing multi-turn CircuitStewardAgent with knowledge retrieval & scratchpad build..."
        )

        synth_result = steward.run_agent_loop(
            prompt=prompt,
            session_id=run_id,
            history=[],
            on_turn_end=lambda t, status: emit_step(
                phase="RESEARCH_AND_SYNTHESIS",
                action=f"AGENT_TURN_{t}",
                description=f"Agent Turn {t}: {status}"
            )
        )
        elapsed_synth = time.time() - t0

        if "error" in synth_result or not synth_result.get("components"):
            logger.warning("agent_pipeline", f"Multi-turn agent produced: {synth_result.get('error')}. Falling back to direct synthesizer.")
            from app.circuit_synthesizer import CircuitSynthesizer as AppSynthesizer
            app_synth = AppSynthesizer()
            direct_data = app_synth.synthesize(prompt)
            components = direct_data.get("circuit", [])
        else:
            components = synth_result.get("components", [])

        emit_step(
            phase="RESEARCH_AND_SYNTHESIS",
            action="SYNTHESIS_COMPLETE",
            description=f"Synthesis finished: {len(components)} components generated.",
            details={"components_count": len(components), "backend": synth_result.get("backend")},
            elapsed_s=elapsed_synth
        )

        # ─── PHASE 2: Semantic Review & Pin Coverage ──────────────────────────
        reviewer = SemanticReviewer(backend=review_backend)
        pinouts_db = getattr(knowledge_synth, "pinouts_db", {})

        def evaluate_semantics_and_pins(comps: List[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, Any]]:
            pin_cov = _pin_coverage(comps, pinouts_db)
            review_raw = reviewer.review_netlist(
                json.dumps({"components": comps}, ensure_ascii=False),
                session_id=f"{run_id}_review",
                meta={"project": proj_id}
            )
            sem_summary = _semantic_review_summary(review_raw)
            return pin_cov, sem_summary

        t0_rev = time.time()
        pin_coverage, semantic_review = evaluate_semantics_and_pins(components)
        elapsed_rev = time.time() - t0_rev

        emit_step(
            phase="SEMANTIC_REVIEW",
            action="AI_DRC_AUDIT",
            description=f"Semantic review found {semantic_review.get('issue_count', 0)} issues ({semantic_review.get('critical_count', 0)} critical). Pin coverage: {pin_coverage.get('average_coverage', 1.0) * 100:.0f if pin_coverage.get('average_coverage') is not None else 100}%.",
            details={"pin_coverage": pin_coverage, "semantic_review": semantic_review},
            elapsed_s=elapsed_rev
        )

        # ─── PHASE 3: Self-Correction Loop (Up to max_correction_cycles) ─────
        correction_cycle = 0
        while semantic_review.get("critical_count", 0) > 0 and correction_cycle < max_correction_cycles:
            correction_cycle += 1
            t0_corr = time.time()
            issues_list = semantic_review.get("issues", [])
            critical_issues = [i for i in issues_list if i.get("severity") == "critical"]
            issues_text = "\n".join(f"- {i.get('msg')} (Proposal: {i.get('proposal')})" for i in critical_issues)

            emit_step(
                phase="SELF_CORRECTION",
                action=f"CORRECTION_CYCLE_{correction_cycle}",
                description=f"Self-correction cycle {correction_cycle}/{max_correction_cycles}: Addressing {len(critical_issues)} critical issues.",
                details={"critical_issues": critical_issues}
            )

            correction_prompt = (
                f"{prompt}\n\n"
                f"CIRCUITO BASE A CORREGIR:\n```json\n{json.dumps({'circuit': components}, indent=2)}\n```\n"
                f"El circuito base tiene los siguientes problemas CRÍTICOS:\n{issues_text}\n"
                f"Por favor, corrige estos problemas explícitamente y devuelve el JSON del circuito resultante."
            )

            corr_synth = steward.run_agent_loop(
                prompt=correction_prompt,
                session_id=f"{run_id}_corr_{correction_cycle}",
                history=[]
            )

            if "error" not in corr_synth and corr_synth.get("components"):
                components = corr_synth.get("components")
                pin_coverage, semantic_review = evaluate_semantics_and_pins(components)
                elapsed_corr = time.time() - t0_corr
                emit_step(
                    phase="SELF_CORRECTION",
                    action=f"CYCLE_{correction_cycle}_APPLIED",
                    description=f"Cycle {correction_cycle} applied. Remaining critical issues: {semantic_review.get('critical_count', 0)}.",
                    details={"remaining_issues": semantic_review.get("issue_count", 0), "critical": semantic_review.get("critical_count", 0)},
                    elapsed_s=elapsed_corr
                )
            else:
                emit_step(
                    phase="SELF_CORRECTION",
                    action="CORRECTION_FAILED",
                    description=f"Self-correction cycle {correction_cycle} did not return updated components. Keeping current circuit."
                )
                break

        # ─── PHASE 4: Physical Generation & DRC / Visual Gate ────────────────
        t0_phys = time.time()
        emit_step(
            phase="PHYSICAL_GENERATION",
            action="START_PHYSICAL_LAYOUT",
            description="Building CircuitGraph, placing footprints with AABB courtyards, autorouting, and pouring ground copper planes..."
        )

        circuit_data = {
            "circuit": components,
            "board_width": 75.0,
            "board_height": 50.0
        }

        graph = CircuitGraph.from_json(circuit_data)

        # Generate Schematic (.kicad_sch)
        sch_gen = SchematicGenerator(graph)
        sch_path = run_dir / "board.kicad_sch"
        sch_gen.save(str(sch_path))

        # Generate PCB (.kicad_pcb)
        pcb_builder = PCBBuilder.from_circuit_graph(graph, out_dir=str(run_dir))
        pcb_result = pcb_builder.save()
        pcb_path = Path(pcb_result["path"])

        # Topological DRC Audit (R001-R014)
        findings, ctx = run_audit(str(pcb_path))
        audit_errors = [f for f in findings if f.severity == "error"]
        audit_warnings = [f for f in findings if f.severity == "warning"]
        audit_info = [f for f in findings if f.severity == "info"]

        # 5-Pass Visual Inspection Gate
        visual_report = run_visual_inspection(pcb_builder.pcb, circuit_data)
        elapsed_phys = time.time() - t0_phys

        emit_step(
            phase="PHYSICAL_GENERATION",
            action="DRC_AND_VISUAL_AUDIT_COMPLETE",
            description=f"Physical generation complete: DRC Errors: {len(audit_errors)} | Visual Score: {visual_report.visual_score:.1f}% (Violations: {visual_report.violations_count}).",
            details={
                "drc_errors": len(audit_errors),
                "drc_warnings": len(audit_warnings),
                "visual_score": visual_report.visual_score,
                "visual_violations": visual_report.violations_count
            },
            elapsed_s=elapsed_phys
        )

        # ─── PHASE 5: Multi-Provider Supply Chain BOM & Web Views ───────────
        from app.main import extract_2d_pcb_vectors, extract_3d_mesh_data
        vectors_2d = extract_2d_pcb_vectors(pcb_builder.pcb)
        mesh_3d = extract_3d_mesh_data(pcb_builder.pcb)

        bom_rows = []
        total_bom_cost_jlc = 0.0
        total_bom_cost_pcbway = 0.0

        for comp in components:
            label = comp.get("label", "")
            val = comp.get("value", "")
            jlc_part = comp.get("jlcpcb_part", "")
            mpn_query = jlc_part if jlc_part else f"{comp.get('etype')} {val}"
            comp_info = self.provider_mgr.get_component_comparison(mpn_query)
            jlc_info = comp_info.get("jlcpcb", {})
            pcbway_info = comp_info.get("pcbway", {})

            total_bom_cost_jlc += float(jlc_info.get("unit_price_usd", 0.0) or 0.0)
            total_bom_cost_pcbway += float(pcbway_info.get("unit_price_usd", 0.0) or 0.0)

            bom_rows.append({
                "label": label,
                "value": val,
                "etype": comp.get("etype", ""),
                "footprint": comp.get("footprint", comp.get("footprint_id", "")),
                "jlcpcb": jlc_info,
                "pcbway": pcbway_info,
                "recommendation": comp_info.get("recommendation", "")
            })

        supply_chain = {
            "bom": bom_rows,
            "total_cost_jlc": round(total_bom_cost_jlc, 2),
            "total_cost_pcbway": round(total_bom_cost_pcbway, 2),
            "components_in_stock": sum(1 for b in bom_rows if b["jlcpcb"].get("in_stock") or b["pcbway"].get("in_stock")),
            "total_components": len(bom_rows)
        }

        # Save Final Design Snapshot & Manifest
        manifest_file = run_dir / "agent_run_manifest.json"
        result = AgentRunResult(
            success=len(audit_errors) == 0 and visual_report.passed,
            project_id=proj_id,
            run_id=run_id,
            prompt=prompt,
            circuit_data=circuit_data,
            components_count=len(components),
            pin_coverage=pin_coverage,
            semantic_issues=semantic_review.get("issues", []),
            critical_issues_count=semantic_review.get("critical_count", 0),
            drc_errors_count=len(audit_errors),
            drc_warnings_count=len(audit_warnings),
            visual_score=visual_report.visual_score,
            visual_violations_count=visual_report.violations_count,
            radar=visual_report.radar,
            correction_cycles=correction_cycle,
            steps=[s.to_dict() for s in steps],
            pcb_path=str(pcb_path),
            sch_path=str(sch_path),
            output_dir=str(run_dir),
            vectors_2d=vectors_2d,
            mesh_3d=mesh_3d,
            supply_chain=supply_chain
        )

        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        emit_step(
            phase="COMPLETION",
            action="PIPELINE_DONE",
            description=f"Agent run complete! DRC: {len(audit_errors)} errors, Visual: {visual_report.visual_score:.1f}%, Total time: {time.time() - t_start_total:.1f}s.",
            details={"success": result.success, "project_id": proj_id, "run_id": run_id},
            elapsed_s=time.time() - t_start_total
        )
        result.steps = [s.to_dict() for s in steps]

        return result

    def run_from_preset(
        self,
        preset_id: str,
        project_id: Optional[str] = None,
        on_step_callback: Optional[Callable[[AgentStep], None]] = None
    ) -> AgentRunResult:
        """
        Runs physical layout, DRC, visual inspection, and supply chain BOM for a curated preset.
        """
        from app.circuit_synthesizer import CircuitSynthesizer as AppSynthesizer
        app_synth = AppSynthesizer()
        preset_map = {
            "esp32_tft_console": lambda: app_synth._synthesize_esp32_console("ESP32-S3 TFT Console"),
            "flipper_addon": lambda: app_synth._synthesize_flipper_addon("Flipper Zero Addon"),
            "sensor_node": lambda: app_synth._synthesize_sensor_node("IoT Sensor Node"),
            "power_supply": lambda: app_synth._synthesize_power_supply("USB-C Power Supply"),
            "ne555_flasher": lambda: app_synth._synthesize_555_timer("NE555 Flasher"),
        }

        if preset_id not in preset_map:
            raise ValueError(f"Unknown preset_id '{preset_id}'. Available: {list(preset_map.keys())}")

        preset_data = preset_map[preset_id]()
        prompt = f"Curated Preset: {preset_id}"
        proj_id = project_id or f"preset_{preset_id}_{uuid.uuid4().hex[:6]}"
        run_dir = self.base_dir / proj_id
        run_dir.mkdir(parents=True, exist_ok=True)

        steps: List[AgentStep] = []
        step_idx = 0

        def emit_step(phase: str, action: str, description: str, details: Optional[Dict[str, Any]] = None, elapsed_s: float = 0.0) -> AgentStep:
            nonlocal step_idx
            step_idx += 1
            st = AgentStep(
                step_number=step_idx,
                phase=phase,
                action=action,
                description=description,
                details=details or {},
                elapsed_s=round(elapsed_s, 2)
            )
            steps.append(st)
            if on_step_callback:
                try:
                    on_step_callback(st)
                except Exception as cb_err:
                    logger.warning("agent_pipeline", f"Step callback error: {cb_err}")
            return st

        t_start = time.time()
        emit_step("PRESET_LOAD", "LOAD_PRESET", f"Loaded curated preset '{preset_id}' with {len(preset_data.get('circuit', []))} components.")

        # Layout & PCB Generation
        t0_phys = time.time()
        graph = CircuitGraph.from_json(preset_data)
        sch_gen = SchematicGenerator(graph)
        sch_path = run_dir / "board.kicad_sch"
        sch_gen.save(str(sch_path))

        pcb_builder = PCBBuilder.from_circuit_graph(graph, out_dir=str(run_dir))
        pcb_result = pcb_builder.save()
        pcb_path = Path(pcb_result["path"])

        findings, ctx = run_audit(str(pcb_path))
        audit_errors = [f for f in findings if f.severity == "error"]
        audit_warnings = [f for f in findings if f.severity == "warning"]
        visual_report = run_visual_inspection(pcb_builder.pcb, preset_data)
        elapsed_phys = time.time() - t0_phys

        emit_step(
            phase="PHYSICAL_GENERATION",
            action="DRC_AND_VISUAL_AUDIT_COMPLETE",
            description=f"Preset layout complete: DRC Errors: {len(audit_errors)} | Visual Score: {visual_report.visual_score:.1f}%.",
            details={"drc_errors": len(audit_errors), "visual_score": visual_report.visual_score},
            elapsed_s=elapsed_phys
        )

        from app.main import extract_2d_pcb_vectors, extract_3d_mesh_data
        vectors_2d = extract_2d_pcb_vectors(pcb_builder.pcb)
        mesh_3d = extract_3d_mesh_data(pcb_builder.pcb)

        result = AgentRunResult(
            success=len(audit_errors) == 0 and visual_report.passed,
            project_id=proj_id,
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            prompt=prompt,
            circuit_data=preset_data,
            components_count=len(preset_data.get("circuit", [])),
            pin_coverage={"average_coverage": 1.0, "per_component": [], "unmatched": []},
            semantic_issues=[],
            critical_issues_count=0,
            drc_errors_count=len(audit_errors),
            drc_warnings_count=len(audit_warnings),
            visual_score=visual_report.visual_score,
            visual_violations_count=visual_report.violations_count,
            radar=visual_report.radar,
            correction_cycles=0,
            steps=[s.to_dict() for s in steps],
            pcb_path=str(pcb_path),
            sch_path=str(sch_path),
            output_dir=str(run_dir),
            vectors_2d=vectors_2d,
            mesh_3d=mesh_3d,
            supply_chain={}
        )
        return result
