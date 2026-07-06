"""Tests for LLM backend routing."""

from knowledge.llm_backends import backend_limits, resolve_backend_name


def test_backend_limits_primary():
    lim = backend_limits("primary")
    assert lim["num_ctx"] >= 98304
    assert lim["max_tokens"] >= 16384


def test_backend_limits_atomic():
    lim = backend_limits("atomic")
    assert lim["json_mode"] is True
    assert lim["think"] is False


def test_resolve_explicit():
    assert resolve_backend_name(prefer="primary") == "primary"
    assert resolve_backend_name(prefer="atomic") == "atomic"
