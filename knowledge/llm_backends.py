"""
knowledge/llm_backends.py
=========================
Dual LLM backend factory: primary (Ollama Qwythos) + atomic (llama-server lane).
"""

from __future__ import annotations

from typing import Any, Optional

from knowledge import atomic_lane
from knowledge.llm_client import LLMClient
from knowledge.pulse_config import cfg


_clients: dict[str, LLMClient] = {}


def _backend_spec(name: str) -> dict[str, Any]:
    spec = cfg(f"llm.backends.{name}", {}) or {}
    if not spec:
        raise KeyError(f"Unknown LLM backend '{name}' — configure llm.backends.{name} in Pulse_cfg.json")
    return spec


def resolve_backend_name(task: str = "default", prefer: str | None = None) -> str:
    """Pick primary or atomic based on config + availability."""
    if prefer and prefer not in ("auto", ""):
        return prefer

    routing = cfg("llm.routing", {}) or {}
    task_map = {
        "mcp": routing.get("mcp_tool_backend", "atomic"),
        "circuit": routing.get("complex_circuit_backend", "primary"),
        "review": routing.get("review_backend", "primary"),
        "default": routing.get("default_backend", "primary"),
    }
    chosen = str(task_map.get(task, task_map["default"]))

    if chosen == "atomic" and not atomic_lane.health_ok():
        if routing.get("auto_fallback", True):
            return "primary"
    if chosen == "primary":
        if not get_backend_client("primary").available and atomic_lane.health_ok():
            if routing.get("auto_fallback", True):
                return "atomic"
    return chosen


def backend_limits(name: str) -> dict[str, Any]:
    spec = _backend_spec(name)
    if name == "atomic":
        slot = atomic_lane.slot_context_tokens()
        return {
            "num_ctx": slot,
            "max_tokens": int(spec.get("num_predict") or spec.get("max_tokens") or cfg("llm.max_tokens", 16384)),
            "prompt_max_chars": int(spec.get("prompt_max_chars", min(48000, slot * 3))),
            "json_mode": bool(spec.get("json_mode", True)),
            "think": False,
            "api": "openai",
        }
    return {
        "num_ctx": int(spec.get("num_ctx") or cfg("llm.num_ctx", 98304)),
        "max_tokens": int(spec.get("num_predict") or spec.get("max_tokens") or cfg("llm.max_tokens", 16384)),
        "prompt_max_chars": int(cfg("llm.agents.circuit_synthesizer.prompt_max_chars", 48000)),
        "json_mode": False,
        "think": spec.get("think", cfg("llm.think", "low")),
        "api": spec.get("api", cfg("llm.api", "auto")),
    }


def get_backend_client(name: str | None = None, task: str = "default") -> LLMClient:
    backend = name or resolve_backend_name(task=task)
    if backend in _clients:
        return _clients[backend]

    spec = _backend_spec(backend)
    model = str(spec.get("model", cfg("llm.model")))
    if backend == "atomic" and model.lower() == "auto":
        model = atomic_lane.resolve_model_id()

    base_url = str(spec.get("base_url") or cfg("llm.ollama_base_url"))
    if backend == "atomic":
        base_url = atomic_lane.atomic_base_url()

    limits = backend_limits(backend)
    client = LLMClient(
        base_url=base_url,
        model=model,
        timeout=float(spec.get("timeout_s") or cfg("llm.timeout_s", 900)),
        think=spec.get("think", "none" if backend == "atomic" else cfg("llm.think")),
        api_mode=str(spec.get("api", "openai" if backend == "atomic" else cfg("llm.api", "auto"))),
        backend_id=backend,
        num_ctx=int(limits["num_ctx"]),
    )
    _clients[backend] = client
    return client


def list_backends() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("primary", "atomic"):
        try:
            spec = _backend_spec(name)
        except KeyError:
            continue
        limits = backend_limits(name)
        client = get_backend_client(name)
        entry = {
            "label": spec.get("label", name),
            "available": client.available,
            "base_url": client.base_url,
            "model": client.model,
            "api": client.api_mode,
            "think": client.think,
            "roles": spec.get("roles", []),
            "limits": limits,
        }
        if name == "atomic":
            entry["atomic"] = atomic_lane.status()
        out[name] = entry
    out["routing"] = cfg("llm.routing", {})
    return out


def clear_client_cache() -> None:
    _clients.clear()
