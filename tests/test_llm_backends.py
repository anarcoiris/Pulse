"""Tests for LLM backend routing."""

from knowledge import atomic_lane, llm_backends
from knowledge.llm_backends import backend_limits, resolve_backend_name
from knowledge.pulse_config import cfg


def test_backend_limits_primary():
    lim = backend_limits("primary")
    assert lim["num_ctx"] >= 32768
    assert lim["max_tokens"] >= 16384


def test_backend_limits_atomic():
    lim = backend_limits("atomic")
    assert lim["json_mode"] is True
    assert lim["think"] is False


def test_resolve_explicit():
    assert resolve_backend_name(prefer="primary") == "primary"
    assert resolve_backend_name(prefer="atomic") == "atomic"


# --- Session 4d: review routing --------------------------------------------


def test_review_backend_config_is_atomic():
    """Pulse_cfg.json llm.routing.review_backend must point at atomic (Session 4d
    default policy: synthesis stays on primary/reasoning, review moves to
    atomic/fast-JSON). See docs/calibration_forge/llm_output_pipeline.md
    §Session 4d."""
    assert cfg("llm.routing.review_backend", "") == "atomic"


def test_resolve_review_backend_uses_atomic_when_healthy(monkeypatch):
    monkeypatch.setattr(atomic_lane, "health_ok", lambda *a, **k: True)
    assert resolve_backend_name(task="review") == "atomic"


def test_resolve_review_backend_falls_back_to_primary_when_atomic_down(monkeypatch):
    monkeypatch.setattr(atomic_lane, "health_ok", lambda *a, **k: False)
    assert resolve_backend_name(task="review") == "primary"


def test_semantic_reviewer_resolves_configured_review_backend(monkeypatch):
    """SemanticReviewer must route via llm_backends instead of always grabbing
    the primary client directly (pre-4d smell noted in llm_output_pipeline.md)."""
    monkeypatch.setattr(atomic_lane, "health_ok", lambda *a, **k: True)
    llm_backends.clear_client_cache()
    from knowledge.semantic_reviewer import SemanticReviewer

    reviewer = SemanticReviewer()
    assert reviewer.backend_name == "atomic"
    assert reviewer.llm.backend_id == "atomic"


def test_semantic_reviewer_explicit_backend_override(monkeypatch):
    llm_backends.clear_client_cache()
    from knowledge.semantic_reviewer import SemanticReviewer

    reviewer = SemanticReviewer(backend="primary")
    assert reviewer.backend_name == "primary"
    assert reviewer.llm.backend_id == "primary"
