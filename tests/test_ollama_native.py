"""Tests for Ollama native API helpers."""

from knowledge.ollama_native import normalize_think, ollama_native_url


def test_ollama_native_url():
    assert ollama_native_url("http://localhost:11431/v1") == "http://localhost:11431/api/chat"
    assert ollama_native_url("http://localhost:11431/v1/") == "http://localhost:11431/api/chat"


def test_normalize_think():
    assert normalize_think("none") is False
    assert normalize_think("false") is False
    assert normalize_think("low") == "low"
    assert normalize_think("medium") == "medium"
    assert normalize_think(True) is True
