"""
test_api_gateway.py
===================
Unit and integration tests for FastAPI EDA gateway.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "supported_providers" in data

def test_api_presets():
    response = client.get("/api/v1/presets")
    assert response.status_code == 200
    data = response.json()
    assert len(data["presets"]) >= 4

def test_api_get_preset_detail():
    response = client.get("/api/v1/presets/esp32_tft_console")
    assert response.status_code == 200
    data = response.json()
    assert "circuit" in data
    assert len(data["circuit"]) >= 10

def test_api_prompt_to_circuit():
    req = {
        "prompt": "ESP32-S3 TFT Console with 5 buttons and USB-C",
        "provider": "auto"
    }
    response = client.post("/api/v1/prompt-to-circuit", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "circuit_data" in data

def test_api_generate_pcb():
    circuit_data = {
        "name": "Test LED Flasher",
        "version": "1.0.0",
        "board_width": 40.0,
        "board_height": 30.0,
        "circuit": [
            {
                "etype": "Connector", "value": "USB-C",
                "symbol": "Connector:USB_C_Receptacle_USB20",
                "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
                "pins": {"1": "PWR_5V", "4": "PWR_GND"},
                "label": "J1", "jlcpcb_part": "C165948"
            },
            {
                "etype": "R", "value": "1k",
                "footprint": "Resistor_SMD:R_0805_2012Metric",
                "n1": "PWR_5V", "n2": "LED_SIG", "label": "R1", "jlcpcb_part": "C17513"
            },
            {
                "etype": "LED", "value": "Red",
                "footprint": "LED_SMD:LED_0805_2012Metric",
                "n1": "LED_SIG", "n2": "PWR_GND", "label": "D1", "jlcpcb_part": "C2286"
            }
        ]
    }
    response = client.post("/api/v1/generate-pcb", json={"circuit_data": circuit_data})
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert "vectors_2d" in res
    assert "mesh_3d" in res
    assert "supply_chain" in res
    assert len(res["vectors_2d"]["components"]) >= 3

def test_api_supply_chain_search():
    response = client.post("/api/v1/supply-chain/search", json={"query": "ESP32", "limit": 3})
    assert response.status_code == 200
    res = response.json()
    assert "results" in res
    assert "jlcpcb" in res["results"]

def test_api_update_component_position_preserves_user_drag():
    circuit_data = {
        "name": "Drag Test Circuit",
        "version": "1.0.0",
        "board_width": 50.0,
        "board_height": 40.0,
        "circuit": [
            {
                "etype": "Connector", "value": "USB-C", "label": "J1",
                "pins": {"1": "PWR_5V", "2": "GND"}
            },
            {
                "etype": "R", "value": "10k", "label": "R1",
                "n1": "PWR_5V", "n2": "GND"
            }
        ]
    }
    # Drag component R1 to custom position [12.5, -8.0]
    update_req = {
        "project_id": "test_drag",
        "circuit_data": circuit_data,
        "label": "R1",
        "position": [12.5, -8.0],
        "rotation": 90.0
    }
    response = client.post("/api/v1/update-component-position", json=update_req)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    
    # Verify R1 stayed at user dragged position [12.5, -8.0]
    r1_comp = next((c for c in res["vectors_2d"]["components"] if c["ref"] == "R1"), None)
    assert r1_comp is not None
    assert abs(r1_comp["x"] - 12.5) < 0.01
    assert abs(r1_comp["y"] - (-8.0)) < 0.01

