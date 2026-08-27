"""
tests/test_llm_service_manager.py
=================================
Unit tests for LLMServiceManager and LLM API endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app
from core.llm_service_manager import (
    LLMServiceManager,
    is_port_open,
    list_local_gguf_models,
    llm_service_mgr
)

client = TestClient(app)

def test_llm_service_manager_singleton():
    mgr1 = LLMServiceManager()
    mgr2 = LLMServiceManager()
    assert mgr1 is mgr2
    assert mgr1 is llm_service_mgr

def test_list_local_gguf_models():
    models = list_local_gguf_models()
    assert isinstance(models, list)
    # Ensure items have expected schema
    for m in models:
        assert "name" in m
        assert "path" in m
        assert "size_gb" in m
        assert m["name"].endswith(".gguf")

def test_llm_service_manager_status():
    status = llm_service_mgr.get_status()
    assert "online" in status
    assert "service_type" in status
    assert "active_endpoint" in status
    assert "available_models" in status
    assert "port" in status
    assert isinstance(status["available_models"], list)

def test_api_llm_status():
    response = client.get("/api/v1/llm/status")
    assert response.status_code == 200
    data = response.json()
    assert "online" in data
    assert "active_endpoint" in data
    assert "available_models" in data

def test_api_llm_test_inference():
    # Calling test endpoint
    response = client.post("/api/v1/llm/test", json={
        "prompt": "Say hello in 1 word.",
        "model": "qwen3:4b-thinking-2507-q4_K_M"
    })
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
