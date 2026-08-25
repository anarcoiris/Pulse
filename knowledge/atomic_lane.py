"""
knowledge/atomic_lane.py
========================
Qwythos / Qwen3 atomic llama-server lane (:11439) — state, health, profile switching.
OpenAI /v1 only (no native /api/chat). Profiles: concurrent2, concurrent3, longctx.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from knowledge.pulse_config import cfg


PROFILE_ALIASES = {
    "default": "concurrent2",
    "burst": "concurrent3",
    "solo": "longctx",
    "heavy": "longctx",
}


import os

def _scripts_dir() -> Path:
    raw = str(cfg("llm.backends.atomic.scripts_dir", ""))
    if raw:
        expanded = os.path.expandvars(os.path.expanduser(raw))
        p = Path(expanded)
        if p.is_absolute() and p.exists():
            return p
    # Repo-relative fallback
    fallback = Path(__file__).resolve().parent.parent / "scripts" / "atomic_lane"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _state_path() -> Path:
    raw = str(cfg("llm.backends.atomic.state_file", ""))
    if raw:
        expanded = os.path.expandvars(os.path.expanduser(raw))
        p = Path(expanded)
        if p.is_absolute() and p.exists():
            return p
    return _scripts_dir() / "qwythos.state.json"


def canonical_profile(name: str) -> str:
    n = name.strip().lower()
    return PROFILE_ALIASES.get(n, n)


def read_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_port() -> int:
    state = read_state()
    atomic = state.get("atomic") or {}
    return int(atomic.get("port") or cfg("llm.backends.atomic.port", 11439))


def atomic_base_url() -> str:
    configured = str(cfg("llm.backends.atomic.base_url", ""))
    if configured:
        return configured.rstrip("/")
    return f"http://127.0.0.1:{atomic_port()}/v1"


def health_ok(port: int | None = None) -> bool:
    port = port or atomic_port()
    url = f"http://127.0.0.1:{port}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=float(cfg("llm.health_check_timeout_s", 3))) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_models(base_url: str | None = None) -> list[str]:
    root = (base_url or atomic_base_url()).rstrip("/")
    url = f"{root}/models"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = []
        for item in data.get("data") or data.get("models") or []:
            mid = item.get("id") or item.get("name") or item.get("model")
            if mid:
                models.append(str(mid))
        return models
    except Exception:
        return []


def resolve_model_id() -> str:
    configured = str(cfg("llm.backends.atomic.model", "auto"))
    if configured and configured.lower() != "auto":
        return configured
    state = read_state()
    alias = (state.get("atomic") or {}).get("serverAlias")
    if alias:
        return str(alias)
    models = list_models()
    return models[0] if models else "qwen3-4b-instruct-48k"


def slot_context_tokens() -> int:
    state = read_state()
    atomic = state.get("atomic") or {}
    if atomic.get("slotCtx"):
        return int(atomic["slotCtx"])
    profile = canonical_profile(str(atomic.get("profile") or cfg("llm.backends.atomic.default_profile", "concurrent2")))
    profiles = cfg("llm.backends.atomic.profiles", {}) or {}
    preset = profiles.get(profile, {})
    return int(preset.get("slot_ctx", cfg("llm.backends.atomic.num_ctx", 49152)))


def status() -> dict[str, Any]:
    state = read_state()
    atomic = state.get("atomic") or {}
    port = atomic_port()
    profile = canonical_profile(str(atomic.get("profile") or "unknown"))
    profiles_cfg = cfg("llm.backends.atomic.profiles", {}) or {}
    preset = profiles_cfg.get(profile, {})
    up = health_ok(port)
    return {
        "available": up,
        "port": port,
        "base_url": atomic_base_url(),
        "profile": profile,
        "parallel": int(atomic.get("parallel") or preset.get("parallel", 0)),
        "slot_ctx": slot_context_tokens(),
        "total_ctx": int(atomic.get("ctx") or 98304),
        "model": resolve_model_id() if up else cfg("llm.backends.atomic.model", "auto"),
        "server_alias": atomic.get("serverAlias"),
        "pid": atomic.get("pid"),
        "state_file": str(_state_path()),
        "api": "openai",
        "think": "none",
        "roles": cfg("llm.backends.atomic.roles", []),
        "last_switch": (atomic.get("lastSwitch") or {}),
    }


def switch_profile(
    target_profile: str,
    reason: str = "pulselab",
    idle_timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Run set-atomic-lane-profile.ps1 and return parsed JSON result."""
    canonical = canonical_profile(target_profile)
    script = _scripts_dir() / "set-atomic-lane-profile.ps1"
    if not script.exists():
        return {
            "error": f"Profile switch script not found: {script}",
            "hint": "Set llm.backends.atomic.scripts_dir in Pulse_cfg.json",
        }

    timeout = idle_timeout_sec
    if timeout is None:
        timeout = int(cfg("llm.backends.atomic.switch_idle_timeout_s", 90))

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-TargetProfile",
        canonical,
        "-Reason",
        reason,
        "-IdleTimeoutSec",
        str(timeout),
        "-Json",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(cfg("llm.backends.atomic.switch_timeout_s", 600)),
            cwd=str(_scripts_dir()),
        )
        stdout = (proc.stdout or "").strip()
        if proc.returncode != 0:
            return {
                "error": proc.stderr.strip() or f"switch failed exit {proc.returncode}",
                "stdout": stdout[:500],
            }
        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass
        return status()
    except subprocess.TimeoutExpired:
        return {"error": "Profile switch timed out"}
    except Exception as e:
        return {"error": str(e)}


def recommended_profile_for_parallel(n: int) -> str:
    if n <= 1:
        return "longctx"
    if n == 2:
        return "concurrent2"
    return "concurrent3"
