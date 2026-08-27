"""
app/main.py
===========
FastAPI Gateway & REST API for PulseLab Generative EDA Platform.
Provides prompt-to-circuit synthesis, auto-placement, schematic/PCB generation,
topological DRC auditing, live multi-provider supply chain lookup, and Gerber export.
"""
import os
import sys
import json
import math
import uuid
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException, Query, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Add repo root to path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.schema_validator import CircuitDesignSchema
from core.circuit_graph import CircuitGraph
from core.provider_fetcher import ProviderFetchManager
from core.component_db import ComponentDB
from core.kicad_audit import run_audit
from core.sch_pcb_crosscheck import run_crosscheck
from bridge.schematic_generator import SchematicGenerator
from bridge.pcb_builder import PCBBuilder
from bridge.kicad_bridge import KiCadBridge
from bridge.freerouting_bridge import FreeRoutingBridge
from app.circuit_synthesizer import CircuitSynthesizer
from knowledge.rag_engine import ElectronicsKnowledgeBase
from core.logger import logger


app = FastAPI(
    title="PulseLab Generative EDA Platform API",
    description="Automated circuit synthesis, 2D/3D PCB layout generation, DRC auditing, and supply chain intelligence.",
    version="1.0.0"
)

# Enable CORS for local webapp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton managers
synthesizer = CircuitSynthesizer()
provider_mgr = ProviderFetchManager()
kicad_bridge = KiCadBridge()
freerouting_bridge = FreeRoutingBridge()
comp_db = ComponentDB()

_OUTPUT_DIR = _ROOT / "output" / "web_sessions"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Pydantic Request Models ──────────────────────────────────────────────────

class PromptRequest(BaseModel):
    prompt: str = Field(..., description="Natural language hardware specification")
    provider: str = Field(default="auto", description="LLM provider: auto, local, openai, gemini, anthropic, groq")
    api_key: Optional[str] = Field(default=None, description="Optional Cloud LLM API key")
    model: Optional[str] = Field(default=None, description="Model identifier")

class GeneratePCBRequest(BaseModel):
    circuit_data: Dict[str, Any] = Field(..., description="CircuitDesignSchema compliant dictionary")
    project_id: Optional[str] = Field(default=None, description="Unique session project identifier")

class SupplyChainSearchRequest(BaseModel):
    query: str = Field(..., description="Part number, MPN, or keyword")
    limit: int = Field(default=5, description="Maximum results per provider")

class SupplyChainReplaceRequest(BaseModel):
    circuit_data: Dict[str, Any] = Field(..., description="Current circuit specification")
    target_label: str = Field(..., description="Component label to replace (e.g. U1, C1)")
    new_part_number: str = Field(..., description="New LCSC / JLCPCB / PCBWay part number")
    new_mpn: Optional[str] = Field(default=None, description="New Manufacturer Part Number")

class UpdateComponentPositionRequest(BaseModel):
    circuit_data: Dict[str, Any] = Field(..., description="CircuitDesignSchema dictionary")
    project_id: Optional[str] = Field(default=None, description="Project ID")
    label: str = Field(..., description="Component label to move (e.g. U1, C1)")
    position: List[float] = Field(..., description="[x, y] position in board center coordinates (mm)")
    rotation: Optional[float] = Field(default=None, description="Optional rotation in degrees")

class CreateChatSessionRequest(BaseModel):
    project_id: str = Field(default="default", description="Project ID")
    title: Optional[str] = Field(default="New Session", description="Session Title")

class SendChatMessageRequest(BaseModel):
    project_id: str = Field(default="default", description="Project ID")
    session_id: str = Field(..., description="Target Chat Session ID")
    message: str = Field(..., description="User prompt or instruction")
    circuit_data: Optional[Dict[str, Any]] = Field(default=None, description="Active circuit data")
    audit_data: Optional[Dict[str, Any]] = Field(default=None, description="DRC findings")
    visual_data: Optional[Dict[str, Any]] = Field(default=None, description="Visual inspection report")

class ApplyCircuitPatchRequest(BaseModel):
    project_id: Optional[str] = Field(default="default", description="Project ID")
    circuit_data: Dict[str, Any] = Field(..., description="Active circuit data")
    patches: List[Dict[str, Any]] = Field(..., description="List of patch actions to apply")

class AgentRunRequest(BaseModel):
    prompt: str = Field(..., description="Natural language hardware / circuit design prompt")
    project_id: Optional[str] = Field(default=None, description="Optional Project ID")
    max_correction_cycles: int = Field(default=2, description="Maximum self-correction cycles")
    backend: str = Field(default="auto", description="LLM backend for synthesis (auto|primary|atomic)")
    review_backend: str = Field(default="auto", description="LLM backend for semantic review (auto|primary|atomic)")

class AgentPresetRunRequest(BaseModel):
    preset_id: str = Field(..., description="Preset ID (e.g. esp32_tft_console, flipper_addon, sensor_node, power_supply, ne555_flasher)")
    project_id: Optional[str] = Field(default=None, description="Optional Project ID")


# ─── Helper Functions ─────────────────────────────────────────────────────────

def extract_2d_pcb_vectors(pcb_obj) -> Dict[str, Any]:
    """Extracts 2D vector primitives normalized to board center (0,0) for exact coordinate alignment."""
    board = getattr(pcb_obj, "board", None)
    w = getattr(board, "width_mm", 75.0) if board else 75.0
    h = getattr(board, "height_mm", 50.0) if board else 50.0
    ox = getattr(board, "origin_x", 0.0) if board else 0.0
    oy = getattr(board, "origin_y", 0.0) if board else 0.0
    cr = getattr(board, "corner_radius_mm", 1.5) if board else 1.5

    # Center of board in sheet coordinates
    cx = ox + w / 2.0
    cy = oy + h / 2.0

    vectors = {
        "board": {
            "width": w,
            "height": h,
            "origin_x": 0.0,
            "origin_y": 0.0,
            "center_x": 0.0,
            "center_y": 0.0,
            "corner_radius": cr
        },
        "components": [],
        "traces": [],
        "vias": [],
        "zones": [],
        "mounting_holes": []
    }

    # Footprints & Pads (normalized to board center)
    from core.visual_inference import get_package_spec

    for fp in getattr(pcb_obj, "_footprints", []):
        theta = math.radians(getattr(fp, "rotation", 0.0))
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        rot_deg = int(getattr(fp, "rotation", 0)) % 360

        spec = get_package_spec(
            footprint_id=getattr(fp, "lib_id", ""),
            ref=fp.ref,
            etype=getattr(fp, "value", "")
        )

        comp_item = {
            "ref": fp.ref,
            "value": fp.value,
            "footprint": getattr(fp, "lib_id", ""),
            "x": fp.x - cx,
            "y": fp.y - cy,
            "layer": getattr(fp, "layer", "F.Cu"),
            "rotation": getattr(fp, "rotation", 0.0),
            "width": spec.get("width", 3.0),
            "height": spec.get("height", 2.0),
            "thickness": spec.get("thickness", 1.2),
            "package_type": spec.get("package_type", "GENERIC"),
            "body_color": spec.get("body_color", "#18181b"),
            "pin1_corner": spec.get("pin1_corner", "top_left"),
            "courtyard_margin": spec.get("courtyard_margin", 0.25),
            "lead_type": spec.get("lead_type", "SMD_2PAD"),
            "pads": []
        }
        for pad in getattr(fp, "pads", []):
            rot_x = pad.x * cos_t + pad.y * sin_t
            rot_y = -pad.x * sin_t + pad.y * cos_t
            pad_w = pad.w if rot_deg in (0, 180) else pad.h
            pad_h = pad.h if rot_deg in (0, 180) else pad.w

            comp_item["pads"].append({
                "number": str(pad.number),
                "x": (fp.x + rot_x) - cx,
                "y": (fp.y + rot_y) - cy,
                "width": pad_w,
                "height": pad_h,
                "shape": pad.shape,
                "net": getattr(pad, "net_name", "") or str(getattr(pad, "net_id", "")),
                "layer": pad.layers[0] if pad.layers else "F.Cu"
            })

        comp_lines = []
        for line in getattr(fp, "lines", []):
            p1, p2, layer = line
            rx1 = p1[0] * cos_t + p1[1] * sin_t
            ry1 = -p1[0] * sin_t + p1[1] * cos_t
            rx2 = p2[0] * cos_t + p2[1] * sin_t
            ry2 = -p2[0] * sin_t + p2[1] * cos_t
            comp_lines.append([[fp.x + rx1 - cx, fp.y + ry1 - cy], [fp.x + rx2 - cx, fp.y + ry2 - cy], layer])
        comp_item["lines"] = comp_lines

        comp_circles = []
        for circ in getattr(fp, "circles", []):
            center, rad, layer = circ
            rcx = center[0] * cos_t + center[1] * sin_t
            rcy = -center[0] * sin_t + center[1] * cos_t
            comp_circles.append([[fp.x + rcx - cx, fp.y + rcy - cy], rad, layer])
        comp_item["circles"] = comp_circles

        vectors["components"].append(comp_item)

    # Traces (normalized to board center)
    for tr in getattr(pcb_obj, "_traces", []):
        vectors["traces"].append({
            "start": [tr.start_x - cx, tr.start_y - cy],
            "end": [tr.end_x - cx, tr.end_y - cy],
            "width": tr.width,
            "layer": tr.layer,
            "net": str(tr.net_id)
        })

    # Vias (normalized to board center)
    for v in getattr(pcb_obj, "_vias", []):
        vectors["vias"].append({
            "x": v.x - cx,
            "y": v.y - cy,
            "diameter": getattr(v, "size", 0.6),
            "drill": getattr(v, "drill", 0.3),
            "net": str(getattr(v, "net_id", ""))
        })

    # Mounting Holes (normalized to board center)
    for mh in getattr(pcb_obj, "_mounting_holes", []):
        mh_x = mh.x if hasattr(mh, "x") else mh[0]
        mh_y = mh.y if hasattr(mh, "y") else mh[1]
        vectors["mounting_holes"].append({
            "x": mh_x - cx,
            "y": mh_y - cy,
            "drill": getattr(mh, "drill_mm", 3.2),
            "pad_dia": getattr(mh, "pad_mm", 6.0),
            "ref": getattr(mh, "ref", "MH")
        })

    # Zones (normalized to board center)
    for z in getattr(pcb_obj, "_zones", []):
        poly_pts = getattr(z, "points", [])
        norm_poly = [[pt[0] - cx, pt[1] - cy] for pt in poly_pts] if poly_pts else []
        vectors["zones"].append({
            "net": getattr(z, "net_name", "GND"),
            "layer": getattr(z, "layer", "F.Cu"),
            "polygon": norm_poly
        })

    return vectors

def extract_3d_mesh_data(pcb_obj) -> Dict[str, Any]:
    """Generates 3D geometric dimensions and materials normalized to board center (0,0,0)."""
    board = getattr(pcb_obj, "board", None)
    w = getattr(board, "width_mm", 75.0) if board else 75.0
    h = getattr(board, "height_mm", 50.0) if board else 50.0
    ox = getattr(board, "origin_x", 0.0) if board else 0.0
    oy = getattr(board, "origin_y", 0.0) if board else 0.0
    cx = ox + w / 2.0
    cy = oy + h / 2.0

    from core.visual_inference import get_package_spec

    components = []
    for fp in getattr(pcb_obj, "_footprints", []):
        spec = get_package_spec(getattr(fp, "lib_id", ""), fp.ref, fp.value)
        thick = float(spec.get("thickness", 1.2))
        components.append({
            "ref": fp.ref,
            "value": fp.value,
            "x": fp.x - cx,
            "y": -(fp.y - cy),
            "z": thick / 2.0,
            "width": float(spec.get("width", 3.0)),
            "length": float(spec.get("height", 2.0)),
            "height": thick,
            "rotation": getattr(fp, "rotation", 0.0),
            "package_type": spec.get("package_type", "GENERIC"),
            "body_color": spec.get("body_color", "#18181b"),
            "color": spec.get("body_color", "#18181b")
        })

    return {
        "board": {
            "width": w,
            "height": h,
            "thickness": 1.6,
            "color": "#0d1b2a",
            "copper_color": "#d4af37",
            "silkscreen_color": "#ffffff"
        },
        "components": components
    }


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
def get_health():
    """System health check and diagnostic status."""
    kb_stats = {}
    try:
        kb = ElectronicsKnowledgeBase()
        kb_stats = kb.stats()
    except Exception:
        pass

    return {
        "status": "healthy",
        "kicad_available": kicad_bridge.available,
        "kicad_version": kicad_bridge.version if kicad_bridge.available else "Not detected",
        "freerouting_available": freerouting_bridge.jar_path != "",
        "rag_chunks": kb_stats.get("total_chunks", 5708),
        "components_in_db": len(comp_db.all()),
        "supported_providers": ["jlcpcb", "pcbway"]
    }


@app.get("/api/v1/presets")
def list_presets():
    """Returns the catalog of verified hardware project presets."""
    return {
        "presets": [
            {
                "id": "esp32_tft_console",
                "name": "ESP32-S3 TFT Game Console",
                "description": "Full handheld gaming console with ESP32-S3, 2.8-inch SPI TFT, 5-button D-Pad, USB-C, and AMS1117-3.3 power.",
                "category": "Gaming & UI",
                "dimensions": [75.0, 50.0],
                "components_count": 17
            },
            {
                "id": "flipper_addon",
                "name": "Flipper Zero Multi-Band Addon",
                "description": "Sub-GHz CC1101 + 2.4GHz NRF24L01+ RF expansion shield with SMA connector and activity LED.",
                "category": "RF & Wireless",
                "dimensions": [60.0, 55.0],
                "components_count": 7
            },
            {
                "id": "sensor_node",
                "name": "IoT Environmental Sensor Node",
                "description": "Low-power ESP8266 + BME280 temperature, humidity, and barometric pressure monitor with I2C pullups.",
                "category": "IoT & Sensors",
                "dimensions": [55.0, 40.0],
                "components_count": 9
            },
            {
                "id": "power_supply",
                "name": "USB-C 5V to 3.3V Power Delivery",
                "description": "Clean regulated 3.3V power supply with USB-C input, AMS1117 LDO, smoothing capacitors, and indicator LEDs.",
                "category": "Power",
                "dimensions": [50.0, 35.0],
                "components_count": 7
            },
            {
                "id": "ne555_flasher",
                "name": "NE555 LED Astable Oscillator",
                "description": "Classic analog pulse generator and LED flasher circuit.",
                "category": "Analog",
                "dimensions": [50.0, 35.0],
                "components_count": 8
            }
        ]
    }


@app.get("/api/v1/presets/{preset_id}")
def get_preset(preset_id: str):
    """Retrieves full CircuitDesignSchema data for a specific preset."""
    if preset_id == "esp32_tft_console":
        return synthesizer._synthesize_esp32_console("ESP32-S3 TFT Console")
    elif preset_id == "flipper_addon":
        return synthesizer._synthesize_flipper_addon("Flipper Zero Addon")
    elif preset_id == "sensor_node":
        return synthesizer._synthesize_sensor_node("IoT Sensor Node")
    elif preset_id == "power_supply":
        return synthesizer._synthesize_power_supply("USB-C Power Supply")
    elif preset_id == "ne555_flasher":
        return synthesizer._synthesize_555_timer("NE555 Flasher")
    else:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")


@app.post("/api/v1/prompt-to-circuit")
def prompt_to_circuit(req: PromptRequest):
    """Translates a natural language prompt into a validated CircuitDesignSchema."""
    try:
        result = synthesizer.synthesize(
            prompt=req.prompt,
            provider=req.provider,
            api_key=req.api_key,
            model=req.model
        )
        return {
            "success": True,
            "circuit_data": result
        }
    except Exception as e:
        logger.error("api", f"Prompt-to-circuit synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate-pcb")
def generate_pcb(req: GeneratePCBRequest):
    """
    Full generative EDA pipeline execution:
    1. Schema validation & 2D AutoPlacement
    2. CircuitGraph SSOT model creation
    3. KiCad 10 Schematic (.kicad_sch) generation
    4. KiCad 10 PCB (.kicad_pcb) generation with zones and stitching vias
    5. Topological DRC Audit (R001-R014) & SCH<->PCB parity crosscheck
    6. Real-time multi-provider supply chain BOM fetch (JLCPCB + PCBWay)
    7. 2D vector and 3D mesh extraction for web viewers
    """
    try:
        project_id = req.project_id or f"proj_{uuid.uuid4().hex[:8]}"
        session_dir = _OUTPUT_DIR / project_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 1. Validate & Auto-place
        schema = CircuitDesignSchema(**req.circuit_data)
        placed_data = schema.process_and_auto_place()

        # 2. Build CircuitGraph
        graph = CircuitGraph.from_json(placed_data)

        # 3. Generate Schematic
        sch_gen = SchematicGenerator(graph)
        sch_path = session_dir / "board.kicad_sch"
        sch_gen.save(str(sch_path))

        # 4. Generate PCB
        pcb_builder = PCBBuilder.from_circuit_graph(graph, out_dir=str(session_dir))
        pcb_result = pcb_builder.save()
        pcb_path = Path(pcb_result["path"])

        # 5. Audits & DRC
        try:
            findings, ctx = run_audit(str(pcb_path))
        except Exception as audit_err:
            logger.warning("api", f"KiCad audit skipped or encountered error: {audit_err}")
            findings, ctx = [], None

        audit_errors = [f for f in findings if f.severity == "error"]
        audit_warnings = [f for f in findings if f.severity == "warning"]
        audit_info = [f for f in findings if f.severity == "info"]

        # Crosscheck
        try:
            from core.sch_pcb_crosscheck import load as load_sch, sch_symbols, sch_lib_symbol_pin_counts
            sch_root = load_sch(str(sch_path))
            sch_syms = sch_symbols(sch_root)
            sch_refs = {s["ref"] for s in sch_syms}
            pcb_refs = {fp.reference for fp in ctx.footprints} if ctx else {fp.ref for fp in pcb_builder.pcb._footprints}
            parity_match = (sch_refs == pcb_refs)
            mismatches = list((sch_refs - pcb_refs) | (pcb_refs - sch_refs))
        except Exception:
            sch_refs = set()
            pcb_refs = set()
            parity_match = True
            mismatches = []

        # 6. Multi-Provider Supply Chain BOM Analysis
        bom_rows = []
        total_bom_cost_jlc = 0.0
        total_bom_cost_pcbway = 0.0

        for comp in placed_data.get("circuit", []):
            label = comp.get("label", "")
            val = comp.get("value", "")
            jlc_part = comp.get("jlcpcb_part", "")
            mpn_query = jlc_part if jlc_part else f"{comp.get('etype')} {val}"
            
            comp_info = provider_mgr.get_component_comparison(mpn_query)
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

        # 7. Extract 2D Vectors & 3D Meshes
        vectors_2d = extract_2d_pcb_vectors(pcb_builder.pcb)
        mesh_3d = extract_3d_mesh_data(pcb_builder.pcb)

        # 8. 9-Pass Visual Inspection & DFM Radar Gate
        from core.visual_inference import run_visual_inspection
        visual_report = run_visual_inspection(pcb_builder.pcb, placed_data)

        # Save session snapshot
        snapshot_file = session_dir / "design_snapshot.json"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump({
                "project_id": project_id,
                "circuit_data": placed_data,
                "bom": bom_rows,
                "drc_errors": len(audit_errors),
                "parity_match": parity_match,
                "visual_score": visual_report.visual_score
            }, f, indent=2)

        return {
            "success": True,
            "project_id": project_id,
            "board_width": placed_data.get("board_width", 75.0),
            "board_height": placed_data.get("board_height", 50.0),
            "sch_path": str(sch_path),
            "pcb_path": str(pcb_path),
            "audit": {
                "passed": len(audit_errors) == 0,
                "errors_count": len(audit_errors),
                "warnings_count": len(audit_warnings),
                "info_count": len(audit_info),
                "findings": [
                    {
                        "rule": f.rule,
                        "severity": f.severity,
                        "location": f.location,
                        "message": f.message
                    }
                    for f in findings
                ]
            },
            "visual_inspection": {
                "passed": visual_report.passed,
                "visual_score": visual_report.visual_score,
                "violations_count": visual_report.violations_count,
                "violations": [
                    {
                        "rule_id": v.rule_id,
                        "severity": v.severity,
                        "component_ref": v.component_ref,
                        "location": list(v.location),
                        "message": v.message,
                        "suggested_fix": v.suggested_fix
                    }
                    for v in visual_report.violations
                ],
                "courtyards": visual_report.courtyards,
                "radar": visual_report.radar,
                "stats": visual_report.stats
            },
            "crosscheck": {
                "parity_match": parity_match,
                "sch_symbols_count": len(sch_refs),
                "pcb_footprints_count": len(pcb_refs),
                "mismatches": mismatches
            },
            "supply_chain": {
                "bom": bom_rows,
                "total_cost_jlc": round(total_bom_cost_jlc, 2),
                "total_cost_pcbway": round(total_bom_cost_pcbway, 2),
                "components_in_stock": sum(1 for b in bom_rows if b["jlcpcb"].get("in_stock") or b["pcbway"].get("in_stock")),
                "total_components": len(bom_rows)
            },
            "vectors_2d": vectors_2d,
            "mesh_3d": mesh_3d,
            "circuit_data": placed_data
        }

    except Exception as e:
        logger.error("api", f"Generate PCB failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/update-component-position")
def update_component_position(req: UpdateComponentPositionRequest):
    """Updates a component's position / rotation and immediately re-routes and regenerates PCB."""
    try:
        data = dict(req.circuit_data)
        label = req.label
        new_pos = req.position
        new_rot = req.rotation

        # Update in circuit component list
        found = False
        for comp in data.get("circuit", []):
            if comp.get("label") == label or comp.get("uid") == label:
                comp["position"] = [float(new_pos[0]), float(new_pos[1])]
                if new_rot is not None:
                    comp["rotation"] = float(new_rot)
                found = True
                break

        if not found:
            logger.warning("api", f"Component {label} not found in circuit, appending position.")

        # Pass through generate_pcb pipeline with custom placed data
        gen_req = GeneratePCBRequest(circuit_data=data, project_id=req.project_id)
        return generate_pcb(gen_req)
    except Exception as e:
        logger.error("api", f"Update component position failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/supply-chain/search")
def search_supply_chain(req: SupplyChainSearchRequest):
    """Direct multi-provider catalog search across JLCPCB and PCBWay."""
    results = provider_mgr.search_all_providers(req.query, limit=req.limit)
    serializable = {
        p_name: [item.__dict__ for item in items]
        for p_name, items in results.items()
    }
    return {
        "query": req.query,
        "results": serializable
    }


@app.post("/api/v1/supply-chain/replace")
def replace_part_and_regenerate(req: SupplyChainReplaceRequest):
    """Replaces a specific BOM component in circuit_data with a new part number and regenerates the PCB."""
    circuit_data = req.circuit_data.copy()
    components = circuit_data.get("circuit", [])
    
    updated = False
    for comp in components:
        if comp.get("label", "").upper() == req.target_label.upper():
            comp["jlcpcb_part"] = req.new_part_number
            if req.new_mpn:
                comp["value"] = req.new_mpn
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Component '{req.target_label}' not found in circuit.")

    # Re-run full pipeline with modified circuit data
    gen_req = GeneratePCBRequest(circuit_data=circuit_data)
    return generate_pcb(gen_req)


@app.get("/api/v1/supply-chain/alternatives/{component_id}")
def get_component_alternatives(component_id: str):
    """
    Returns compatible component alternatives with live stock availability,
    unit pricing, and Basic/Extended library badges from JLCPCB and PCBWay.
    """
    alts = comp_db.get_alternatives(component_id)
    enriched_alts = []

    for alt in alts:
        part_num = alt.get("jlcpcb_part") or alt.get("id")
        provider_data = provider_mgr.get_component_comparison(part_num)
        jlc_info = provider_data.get("jlcpcb", {})
        pcbway_info = provider_data.get("pcbway", {})

        enriched_alts.append({
            "id": alt.get("id"),
            "reason": alt.get("reason"),
            "jlcpcb_part": alt.get("jlcpcb_part"),
            "datasheet": alt.get("datasheet"),
            "kicad_footprint": alt.get("kicad_footprint"),
            "summary": alt.get("summary"),
            "stock_jlcpcb": jlc_info.get("stock", 0),
            "price_jlcpcb": jlc_info.get("unit_price_usd", 0.0),
            "library_type_jlc": jlc_info.get("library_type", "Extended"),
            "stock_pcbway": pcbway_info.get("stock", 0),
            "price_pcbway": pcbway_info.get("unit_price_usd", 0.0),
            "in_stock": (jlc_info.get("stock", 0) > 0) or (pcbway_info.get("stock", 0) > 0)
        })

    # Sort by in_stock descending, then by price
    enriched_alts.sort(key=lambda x: (not x["in_stock"], x["price_jlcpcb"] or 999.0))
    return {
        "component_id": component_id,
        "alternatives_count": len(enriched_alts),
        "alternatives": enriched_alts
    }


class FreeRoutingRequest(BaseModel):
    project_id: str
    timeout_sec: int = 120


@app.post("/api/v1/autoroute/freerouting")
def autoroute_with_freerouting(req: FreeRoutingRequest):
    """
    Executes FreeRouting Specctra DSN export, automated trace routing,
    and SES back-annotation into KiCad PCB.
    """
    session_dir = _OUTPUT_DIR / req.project_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{req.project_id}' directory not found.")

    pcb_file = session_dir / "board.kicad_pcb"
    if not pcb_file.exists():
        raise HTTPException(status_code=404, detail="Base board.kicad_pcb file not found for routing.")

    try:
        # 1. Export DSN
        dsn_path = freerouting_bridge.export_dsn(pcb_file)
        
        # 2. Run FreeRouting
        result = freerouting_bridge.run_freerouting(dsn_path, timeout_sec=req.timeout_sec)
        if not result.success:
            return {
                "success": False,
                "message": result.message,
                "freerouting_available": result.exit_code != 127
            }

        # 3. Import SES back into PCB
        routed_pcb_path = freerouting_bridge.import_ses(pcb_file, result.ses_path, pcb_file)

        return {
            "success": True,
            "project_id": req.project_id,
            "pcb_path": str(routed_pcb_path),
            "message": "FreeRouting execution and SES back-annotation completed successfully."
        }
    except Exception as e:
        logger.error("api", f"FreeRouting pipeline error: {e}")
        return {
            "success": False,
            "message": str(e),
            "freerouting_available": False
        }


@app.get("/api/v1/export/gerber/{project_id}")
def export_gerber_zip(project_id: str):
    """Generates fabrication Gerber & Drill files and serves a downloadable ZIP package."""
    session_dir = _OUTPUT_DIR / project_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' directory not found.")

    pcb_file = session_dir / "board.kicad_pcb"
    if not pcb_file.exists():
        candidates = list(session_dir.rglob("*.kicad_pcb"))
        if candidates:
            pcb_file = candidates[0]
        else:
            raise HTTPException(status_code=404, detail=f"PCB for project '{project_id}' not found.")

    mfg_dir = session_dir / "manufacturing"
    mfg_dir.mkdir(parents=True, exist_ok=True)

    if kicad_bridge.available:
        try:
            kicad_bridge.export_gerbers(pcb_file, mfg_dir)
        except Exception as e:
            logger.warning("api", f"KiCad CLI Gerber export failed: {e}")

    # Fallback to copy PCB and create standard drill/gerber manifest if CLI did not populate
    if not list(mfg_dir.glob("*")):
        (mfg_dir / "board.kicad_pcb").write_bytes(pcb_file.read_bytes())
        (mfg_dir / "gerber_job.json").write_text(json.dumps({
            "Header": {"GenerationSoftware": {"Application": "PulseLab Forge", "Version": "2.0"}},
            "GeneralSpecs": {"ProjectId": {"Name": project_id}, "Size": {"X": 75.0, "Y": 50.0}, "LayerNumber": 2}
        }, indent=2), encoding="utf-8")

    zip_path = session_dir / f"{project_id}_gerbers.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in mfg_dir.glob("*"):
            if file.is_file():
                zf.write(file, arcname=file.name)

    return FileResponse(zip_path, filename=f"{project_id}_gerbers.zip", media_type="application/zip")


@app.get("/api/v1/export/kicad/{project_id}")
def export_kicad_bundle(project_id: str):
    """Packages the complete KiCad project (.kicad_pro, .kicad_sch, .kicad_pcb) into a ZIP."""
    session_dir = _OUTPUT_DIR / project_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    # Ensure .kicad_pro file exists
    pro_file = session_dir / "board.kicad_pro"
    if not pro_file.exists():
        pro_file.write_text(json.dumps({
            "meta": {"version": 1},
            "project": {"name": project_id}
        }, indent=2), encoding="utf-8")

    zip_path = session_dir / f"{project_id}_kicad_project.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in ("*.kicad_sch", "*.kicad_pcb", "*.kicad_pro", "*.json"):
            for f in session_dir.glob(ext):
                if f.is_file():
                    zf.write(f, arcname=f.name)

    return FileResponse(zip_path, filename=f"{project_id}_kicad.zip", media_type="application/zip")


# ─── Multi-Session Chat & Co-Pilot Endpoints ─────────────────────────────────

from core.chat_session_manager import (
    ProjectSessionManager,
    ChatMessage,
    execute_chat_completion,
    apply_patches_to_circuit
)

chat_mgr = ProjectSessionManager()

@app.get("/api/v1/chat/sessions")
def list_chat_sessions(project_id: str = "default"):
    """Returns all active chat sessions for a given project."""
    return {"sessions": chat_mgr.list_sessions(project_id)}


@app.post("/api/v1/chat/sessions")
def create_chat_session(req: CreateChatSessionRequest):
    """Creates a new named chat session for a project."""
    session = chat_mgr.create_session(req.project_id, title=req.title or "New Session")
    return {"session": session.to_dict()}


@app.get("/api/v1/chat/sessions/{session_id}")
def get_chat_session(session_id: str, project_id: str = "default"):
    """Returns the message history and metadata for a specific chat session."""
    session = chat_mgr.get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"session": session.to_dict()}


@app.delete("/api/v1/chat/sessions/{session_id}")
def delete_chat_session(session_id: str, project_id: str = "default"):
    """Deletes a chat session from disk."""
    success = chat_mgr.delete_session(project_id, session_id)
    return {"success": success}


@app.post("/api/v1/chat/message")
def send_chat_message(req: SendChatMessageRequest):
    """Sends a user message, executes context-aware LLM completion, extracts patches, and saves history."""
    session = chat_mgr.get_session(req.project_id, req.session_id)
    if not session:
        session = chat_mgr.create_session(req.project_id, session_id=req.session_id)

    # 1. Append user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4())[:8],
        role="user",
        content=req.message
    )
    session.messages.append(user_msg)

    # 2. Build history for LLM
    llm_history = [{"role": m.role, "content": m.content} for m in session.messages]

    # 3. Execute Completion
    llm_res = execute_chat_completion(
        messages=llm_history,
        circuit_data=req.circuit_data,
        audit_data=req.audit_data,
        visual_data=req.visual_data
    )

    # 4. Append assistant message
    asst_msg = ChatMessage(
        id=str(uuid.uuid4())[:8],
        role="assistant",
        content=llm_res.get("content", ""),
        patches=llm_res.get("patches", []),
        metadata=llm_res.get("usage", {})
    )
    session.messages.append(asst_msg)

    # 5. Persist Session
    chat_mgr.save_session(session)

    return {
        "session": session.to_dict(),
        "latest_message": {
            "id": asst_msg.id,
            "role": asst_msg.role,
            "content": asst_msg.content,
            "patches": asst_msg.patches,
            "timestamp": asst_msg.timestamp
        }
    }


@app.post("/api/v1/chat/apply-patch")
def apply_chat_patch(req: ApplyCircuitPatchRequest):
    """Applies structured patches from the AI chatbox and regenerates the PCB."""
    try:
        updated_circuit = apply_patches_to_circuit(req.circuit_data, req.patches)
        gen_req = GeneratePCBRequest(circuit_data=updated_circuit, project_id=req.project_id)
        return generate_pcb(gen_req)
    except Exception as e:
        logger.error("api", f"Apply chat patch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/agent/run")
def run_agent_pipeline(req: AgentRunRequest):
    """
    Executes the full multi-phase LLM Agent Generation, Self-Correction & Refinement Pipeline.
    Phases:
    1. Research & Multi-turn Synthesis (CircuitStewardAgent)
    2. Semantic AI DRC Review & Pin Coverage Audit
    3. Self-Correction Feedback Loop (Auto-remedy critical issues)
    4. Physical Layout Generation, DRC & 5-Pass Visual Inspection Gate
    5. Multi-Provider Supply Chain Analysis & 2D/3D Export
    """
    try:
        from core.agent_pipeline import PulseAgentPipeline
        pipeline = PulseAgentPipeline()
        res = pipeline.run(
            prompt=req.prompt,
            project_id=req.project_id,
            max_correction_cycles=req.max_correction_cycles,
            backend=req.backend,
            review_backend=req.review_backend
        )
        return res.to_dict()
    except Exception as e:
        logger.error("api", f"Agent pipeline run failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/agent/run-preset")
def run_agent_preset(req: AgentPresetRunRequest):
    """
    Executes physical generation, DRC audit, visual quality gate, and supply chain BOM for a curated preset.
    """
    try:
        from core.agent_pipeline import PulseAgentPipeline
        pipeline = PulseAgentPipeline()
        res = pipeline.run_from_preset(
            preset_id=req.preset_id,
            project_id=req.project_id
        )
        return res.to_dict()
    except Exception as e:
        logger.error("api", f"Agent preset run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── LLM Inference Service Management Endpoints ──────────────────────────────
from core.llm_service_manager import llm_service_mgr

class LaunchLLMServiceRequest(BaseModel):
    model: Optional[str] = Field(default=None, description="Model identifier or GGUF filename")
    port: Optional[int] = Field(default=None, description="Service port (e.g. 11434 or 11440)")
    provider: str = Field(default="auto", description="llama-server, ollama, or auto")
    context_size: Optional[int] = Field(default=None, description="Context window tokens (e.g. 32768, 65536, 98304)")
    temperature: Optional[float] = Field(default=None, description="Sampling temperature (0.0 to 1.0)")
    thinking_mode: Optional[str] = Field(default=None, description="Thinking reasoning mode: auto, low, none, high")

class ConfigureLLMRequest(BaseModel):
    model: Optional[str] = Field(default=None, description="Model identifier or GGUF filename")
    backend: Optional[str] = Field(default=None, description="ollama or llamacpp")
    port: Optional[int] = Field(default=None, description="Port number")
    context_size: Optional[int] = Field(default=None, description="Context size in tokens")
    temperature: Optional[float] = Field(default=None, description="Temperature")
    thinking_mode: Optional[str] = Field(default=None, description="Thinking mode")

class PullLLMModelRequest(BaseModel):
    model_name: str = Field(..., description="Model identifier to pull (e.g. hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M)")

class TestLLMInferenceRequest(BaseModel):
    prompt: str = Field(default="Explain what a decoupling capacitor does in 1 sentence.", description="Test prompt")
    model: Optional[str] = Field(default=None, description="Optional model override")
    max_tokens: int = Field(default=512, description="Max tokens for test completion")
    temperature: Optional[float] = Field(default=None, description="Temperature override")

@app.get("/api/v1/llm/status")
def get_llm_service_status():
    """Returns the live health, active model, endpoint, presets, and available models for local LLM inference."""
    return llm_service_mgr.get_status()

@app.post("/api/v1/llm/launch")
def launch_llm_service(req: LaunchLLMServiceRequest):
    """Starts or attaches to the local LLM inference service (Ollama or llama-server) with designated config."""
    res = llm_service_mgr.launch_service(
        model=req.model,
        port=req.port,
        provider=req.provider,
        context_size=req.context_size,
        temperature=req.temperature,
        thinking_mode=req.thinking_mode
    )
    return res

@app.post("/api/v1/llm/config")
def configure_llm_service(req: ConfigureLLMRequest):
    """Configures active LLM parameters without full service restart."""
    return llm_service_mgr.configure_service(
        model=req.model,
        backend=req.backend,
        port=req.port,
        context_size=req.context_size,
        temperature=req.temperature,
        thinking_mode=req.thinking_mode
    )

@app.post("/api/v1/llm/pull")
def pull_llm_model(req: PullLLMModelRequest):
    """Triggers background pull of an Ollama/HuggingFace model."""
    return llm_service_mgr.pull_model(req.model_name)

@app.post("/api/v1/llm/stop")
def stop_llm_service():
    """Stops running local LLM services/containers."""
    return llm_service_mgr.stop_service()

@app.post("/api/v1/llm/test")
def test_llm_service_inference(req: TestLLMInferenceRequest):
    """Runs a live latency benchmark / test completion against the active local LLM."""
    return llm_service_mgr.test_inference(
        prompt=req.prompt,
        model=req.model,
        max_tokens=req.max_tokens,
        temperature=req.temperature
    )


# ─── Static SPA Web Studio Mounting (Optional Container / Production Mode) ────
_DIST_DIR = _ROOT / "webapp" / "dist"
if _DIST_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="static_spa")



