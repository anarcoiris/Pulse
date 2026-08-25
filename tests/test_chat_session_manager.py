"""
tests/test_chat_session_manager.py
==================================
Unit tests for ProjectSessionManager, context injection, patch extraction,
and multi-session API endpoints.
"""

import pytest
from core.chat_session_manager import (
    ProjectSessionManager,
    build_system_prompt_with_context,
    extract_circuit_patches,
    apply_patches_to_circuit,
)
from fastapi.testclient import TestClient
from app.main import app


def test_create_list_get_delete_sessions(tmp_path):
    mgr = ProjectSessionManager(base_dir=str(tmp_path))
    project_id = "test_project_alpha"

    # Initial list creates default
    sessions = mgr.list_sessions(project_id)
    assert len(sessions) >= 1

    # Create new named session
    sess2 = mgr.create_session(project_id, title="Power Supply Tuning")
    assert sess2.title == "Power Supply Tuning"
    assert sess2.project_id == project_id

    # Retrieve session
    fetched = mgr.get_session(project_id, sess2.session_id)
    assert fetched is not None
    assert fetched.title == "Power Supply Tuning"

    # List again
    sessions_after = mgr.list_sessions(project_id)
    assert len(sessions_after) >= 2

    # Delete session
    deleted = mgr.delete_session(project_id, sess2.session_id)
    assert deleted is True
    assert mgr.get_session(project_id, sess2.session_id) is None


def test_build_system_prompt_with_context():
    circuit = {
        "board_width": 60.0,
        "board_height": 40.0,
        "circuit": [
            {"label": "U1", "etype": "MCU", "value": "ESP32-S3", "position": [0, 0], "pins": {"1": "3V3", "2": "GND"}},
            {"label": "C1", "etype": "C", "value": "10uF", "position": [-5, 0], "n1": "3V3", "n2": "GND"}
        ]
    }
    audit = {
        "errors_count": 0,
        "warnings_count": 0,
        "findings": []
    }
    visual = {
        "visual_score": 98.5,
        "violations": []
    }

    prompt = build_system_prompt_with_context(circuit, audit, visual)
    assert "U1 (MCU, ESP32-S3)" in prompt
    assert "60.0 mm x 40.0 mm" in prompt
    assert "DRC Status: PASSED" in prompt
    assert "Visual Inspection Score: 98.5%" in prompt
    assert "```circuit_patch" in prompt


def test_extract_circuit_patches():
    text = """
I recommend adding an indicator LED on GPIO5 and increasing C1.
```circuit_patch
[
  {
    "action_type": "ADD_COMPONENT",
    "label": "D1",
    "etype": "LED",
    "value": "Red",
    "pins": {"1": "GPIO5", "2": "GND"}
  },
  {
    "action_type": "UPDATE_COMPONENT",
    "label": "C1",
    "value": "22uF"
  }
]
```
Let me know if you would like any further adjustments!
"""
    clean_text, patches = extract_circuit_patches(text)
    assert len(patches) == 2
    assert patches[0]["action_type"] == "ADD_COMPONENT"
    assert patches[0]["label"] == "D1"
    assert patches[1]["action_type"] == "UPDATE_COMPONENT"
    assert patches[1]["value"] == "22uF"


def test_apply_patches_to_circuit():
    initial_circuit = {
        "board_width": 75.0,
        "board_height": 50.0,
        "circuit": [
            {"label": "U1", "etype": "MCU", "value": "ESP32-S3", "position": [0, 0]},
            {"label": "C1", "etype": "C", "value": "10uF", "position": [-10, 0]}
        ]
    }

    patches = [
        {
            "action_type": "ADD_COMPONENT",
            "label": "D_STAT",
            "etype": "LED",
            "value": "Green",
            "pins": {"1": "GPIO12", "2": "GND"}
        },
        {
            "action_type": "UPDATE_COMPONENT",
            "label": "C1",
            "value": "47uF"
        },
        {
            "action_type": "REMOVE_COMPONENT",
            "label": "OLD_PART"
        }
    ]

    updated = apply_patches_to_circuit(initial_circuit, patches)
    labels = [c["label"] for c in updated["circuit"]]
    assert "D_STAT" in labels
    assert "U1" in labels
    assert "C1" in labels

    # Check updated C1 value
    c1 = next(c for c in updated["circuit"] if c["label"] == "C1")
    assert c1["value"] == "47uF"


def test_api_chat_endpoints():
    client = TestClient(app)
    project_id = "test_api_proj"

    # 1. List sessions
    res = client.get(f"/api/v1/chat/sessions?project_id={project_id}")
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 1

    # 2. Create session
    res2 = client.post("/api/v1/chat/sessions", json={"project_id": project_id, "title": "DRC Analysis Session"})
    assert res2.status_code == 200
    sess_id = res2.json()["session"]["session_id"]
    assert res2.json()["session"]["title"] == "DRC Analysis Session"

    # 3. Send message
    res3 = client.post("/api/v1/chat/message", json={
        "project_id": project_id,
        "session_id": sess_id,
        "message": "Hello AI, what components are currently on the board?",
        "circuit_data": {"circuit": [{"label": "U1", "etype": "MCU", "value": "ESP32-S3"}]}
    })
    assert res3.status_code == 200
    msg_data = res3.json()
    assert "latest_message" in msg_data
    assert msg_data["latest_message"]["role"] == "assistant"

    # 4. Delete session
    res4 = client.delete(f"/api/v1/chat/sessions/{sess_id}?project_id={project_id}")
    assert res4.status_code == 200
    assert res4.json()["success"] is True
