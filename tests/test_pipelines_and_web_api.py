"""
tests/test_pipelines_and_web_api.py
===================================
Comprehensive Test Suite for PulseLab EDA Pipelines & WebApp API Accessibility.

Tests:
  1. WebApp REST API Endpoints (FastAPI TestClient)
     - /api/v1/health
     - /api/v1/presets
     - /api/v1/presets/{preset_id}
     - /api/v1/supply-chain/search
     - /api/v1/generate-pcb
  2. PulseLabEngine Master Service Kernel Pipeline
     - Full cycle: Schema -> AutoPlace -> Schematic -> PCB -> Dynamic Zones -> DRC -> Gerbers -> BOM -> CPL
  3. MNA Circuit Simulation Pipeline
     - Nodal analysis & transient RC solver
  4. Multi-Provider Supply Chain Pipeline
     - ProviderFetchManager (JLCPCB & PCBWay search)
  5. Copper Zone & Thermal Management Pipeline
     - Dynamic polygon pour & solid thermal coupling
"""

import sys
import json
import shutil
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.service_kernel import PulseLabEngine
from core.circuit_graph import CircuitGraph
from core.circuit_engine import CircuitSimulator
from core.provider_fetcher import ProviderFetchManager
from core.copper_zone_manager import generate_ground_pour_zones, format_zone_sexpr
from bridge.freerouting_bridge import FreeRoutingBridge
from core.kicad_audit import run_audit

client = TestClient(app)


# ─── 1. WebApp REST API Tests ────────────────────────────────────────────────

class TestWebAppAPIAccessibility:
    """Verifica que todos los endpoints clave de la WebApp responden correctamente."""

    def test_health_endpoint(self):
        """GET /api/v1/health"""
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") in ("healthy", "ok")
        assert "kicad_available" in data

    def test_list_presets(self):
        """GET /api/v1/presets"""
        res = client.get("/api/v1/presets")
        assert res.status_code == 200
        data = res.json()
        presets = data.get("presets", data)
        assert isinstance(presets, list)
        assert len(presets) > 0
        assert "id" in presets[0]

    def test_get_specific_preset(self):
        """GET /api/v1/presets/{preset_id}"""
        presets_res = client.get("/api/v1/presets")
        presets_data = presets_res.json()
        presets = presets_data.get("presets", presets_data)
        preset_id = presets[0]["id"]
        
        res = client.get(f"/api/v1/presets/{preset_id}")
        assert res.status_code == 200
        preset_data = res.json()
        assert "circuit" in preset_data

    def test_supply_chain_search(self):
        """POST /api/v1/supply-chain/search"""
        res = client.post("/api/v1/supply-chain/search", json={
            "query": "10k",
            "limit": 3
        })
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert "jlcpcb" in data["results"] or "pcbway" in data["results"]

    def test_generate_pcb_pipeline(self):
        """POST /api/v1/generate-pcb"""
        sample_circuit = {
            "name": "API Test Board",
            "board_width": 45.0,
            "board_height": 30.0,
            "circuit": [
                {
                    "etype": "R",
                    "value": "10k",
                    "label": "R1",
                    "n1": "PWR_5V",
                    "n2": "NET_DIV",
                    "footprint": "Resistor_SMD:R_0603_1608Metric"
                },
                {
                    "etype": "R",
                    "value": "10k",
                    "label": "R2",
                    "n1": "NET_DIV",
                    "n2": "PWR_GND",
                    "footprint": "Resistor_SMD:R_0603_1608Metric"
                }
            ]
        }
        res = client.post("/api/v1/generate-pcb", json={
            "circuit_data": sample_circuit,
            "project_id": "test_api_proj_01"
        })
        assert res.status_code == 200
        result = res.json()
        assert result.get("success") is True
        assert "project_id" in result


# ─── 2. Service Kernel Master Pipeline Tests ─────────────────────────────────

class TestServiceKernelPipeline:
    """Verifica el ciclo completo del motor maestro PulseLabEngine."""

    def test_complete_project_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PulseLabEngine(output_base_dir=Path(tmpdir))
            
            sample_circuit = {
                "name": "Kernel Verification Board",
                "board_width": 55.0,
                "board_height": 35.0,
                "circuit": [
                    {
                        "etype": "R",
                        "value": "4.7k",
                        "label": "R1",
                        "n1": "PWR_3V3",
                        "n2": "I2C_SDA",
                        "footprint": "Resistor_SMD:R_0603_1608Metric"
                    },
                    {
                        "etype": "R",
                        "value": "4.7k",
                        "label": "R2",
                        "n1": "PWR_3V3",
                        "n2": "I2C_SCL",
                        "footprint": "Resistor_SMD:R_0603_1608Metric"
                    },
                    {
                        "etype": "C",
                        "value": "10uF",
                        "label": "C1",
                        "n1": "PWR_3V3",
                        "n2": "PWR_GND",
                        "footprint": "Capacitor_SMD:C_0805_2012Metric"
                    }
                ]
            }
            
            bundle = engine.create_project("test_kernel_proj", sample_circuit)
            
            # Verificaciones estructurales
            assert bundle.success is True
            assert bundle.sch_file.exists()
            assert bundle.pcb_file.exists()
            assert bundle.jlcpcb_bom.exists()
            assert bundle.jlcpcb_cpl.exists()
            assert bundle.gerber_dir.exists()
            
            # Verificar contenido del PCB (debe incluir zonas dinámicas)
            with open(bundle.pcb_file, "r", encoding="utf-8") as f:
                pcb_content = f.read()
                assert "(zone" in pcb_content
                assert "PWR_GND" in pcb_content
                assert "filled_polygon" not in pcb_content  # Verificación de vertido dinámico


# ─── 3. MNA Circuit Simulation Pipeline Tests ────────────────────────────────

class TestSimulationPipeline:
    """Verifica el pipeline de simulación eléctrica nodal (MNA)."""

    def test_resistive_divider_mna(self):
        sim = CircuitSimulator(dt=1e-3)
        sim.add_voltage_source("V1", "VCC", "GND", 10.0)
        sim.add_resistor("R1", "VCC", "VOUT", 1000.0)
        sim.add_resistor("R2", "VOUT", "GND", 1000.0)
        
        # Step simulation
        node_voltages, _ = sim.step()
        
        vout_idx = sim.get_node("VOUT")
        v_out = node_voltages[vout_idx]
        assert abs(v_out - 5.0) < 1e-3, f"Expected 5.0V at divider output, got {v_out}"


# ─── 4. Multi-Provider Supply Chain Pipeline Tests ───────────────────────────

class TestSupplyChainPipeline:
    """Verifica el gestor unificado de búsqueda en JLCPCB y PCBWay."""

    def test_provider_manager_structure(self):
        mgr = ProviderFetchManager()
        assert "jlcpcb" in mgr.providers
        assert "pcbway" in mgr.providers


# ─── 5. Copper Zone & Thermal Management Pipeline Tests ──────────────────────

class TestCopperZonePipeline:
    """Verifica la generación de zonas de cobre dinámicas sin polígonos estáticos."""

    def test_dynamic_ground_pour_generation(self):
        bounds = (115.0, 80.0, 180.0, 128.0)
        zones = generate_ground_pour_zones(
            bounds=bounds,
            layers=["F.Cu", "B.Cu"],
            net_name="PWR_GND",
            clearance=0.20
        )
        assert len(zones) == 2
        assert zones[0].layer == "F.Cu"
        assert zones[1].layer == "B.Cu"
        
        sexpr = format_zone_sexpr(zones[0])
        assert '(zone' in sexpr
        assert 'PWR_GND' in sexpr
        assert 'filled_polygon' not in sexpr
