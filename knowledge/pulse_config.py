"""
knowledge/pulse_config.py
=========================
Central configuration: Pulse_cfg.json + optional .env overrides.

Env vars still override JSON (backward compatible). LLM num_ctx is never below 98304.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CFG_PATH = _ROOT / "Pulse_cfg.json"
_ENV_FILE = _ROOT / ".env"
_MIN_NUM_CTX = 32768

# Load .env before reading env overrides
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE)
    except ImportError:
        pass

# Env key -> dot path in Pulse_cfg.json
_ENV_TO_CFG: dict[str, str] = {
    "PULSE_OLLAMA_BASE_URL": "llm.ollama_base_url",
    "PULSE_LLM_MODEL": "llm.model",
    "PULSE_EMBED_MODEL": "llm.embed.model",
    "PULSE_RAG_BACKEND": "rag.backend",
    "PULSE_LLM_TIMEOUT": "llm.timeout_s",
    "PULSE_LLM_MAX_TOKENS": "llm.max_tokens",
    "PULSE_LLM_NUM_PREDICT": "llm.num_predict",
    "PULSE_LLM_NUM_CTX": "llm.num_ctx",
    "PULSE_LLM_THINK": "llm.think",
    "PULSE_LLM_API": "llm.api",
    "PULSE_LLM_LOG_IO": "llm.log_io",
    "PULSE_LLM_LOG_DIR": "llm.log_dir",
    "PULSE_MCP_HOST": "mcp.server.host",
    "PULSE_MCP_PORT": "mcp.server.port",
    "PULSE_PCB_OUTPUT_DIR": "pcb.output_dir",
    "PULSE_ATOMIC_BASE_URL": "llm.backends.atomic.base_url",
}


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _deep_get(data: dict, path: str, default: Any = None) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _deep_set(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _coerce_env(path: str, raw: str) -> Any:
    if path.endswith("_io") or raw.lower() in ("true", "false", "1", "0", "yes", "no", "on", "off"):
        return raw.lower() in ("1", "true", "yes", "on")
    if path.endswith(("_s", "_ms")) or ".timeout" in path or path.endswith("_port"):
        try:
            return int(raw) if path.endswith("_port") else float(raw)
        except ValueError:
            return raw
    if path.endswith(("_tokens", "_ctx", "_retries", "_steps", "_top_k", "_version")) or "num_" in path:
        try:
            return int(raw)
        except ValueError:
            return raw
    return raw


def _load_json() -> dict:
    if not _CFG_PATH.exists():
        return {}
    with _CFG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _apply_env(data: dict) -> dict:
    out = deepcopy(data)
    for env_key, cfg_path in _ENV_TO_CFG.items():
        val = get_env(env_key)
        if val:
            _deep_set(out, cfg_path, _coerce_env(cfg_path, val))
    return out


def _enforce_llm_limits(data: dict) -> dict:
    llm = data.setdefault("llm", {})
    num_ctx = int(llm.get("num_ctx", _MIN_NUM_CTX))
    llm["num_ctx"] = max(num_ctx, _MIN_NUM_CTX)
    max_tok = int(llm.get("max_tokens", 16384))
    num_pred = int(llm.get("num_predict", max_tok))
    llm["max_tokens"] = max(max_tok, 1)
    llm["num_predict"] = max(num_pred, llm["max_tokens"])
    return data


class PulseConfig:
    """Singleton accessor for Pulse_cfg.json."""

    _instance: PulseConfig | None = None

    def __init__(self, data: dict | None = None):
        self._data = _enforce_llm_limits(_apply_env(data if data is not None else _load_json()))

    @classmethod
    def get(cls) -> PulseConfig:
        if cls._instance is None:
            cls._instance = PulseConfig()
        return cls._instance

    @classmethod
    def reload(cls) -> PulseConfig:
        cls._instance = PulseConfig()
        return cls._instance

    @property
    def data(self) -> dict:
        return self._data

    @property
    def path(self) -> Path:
        return _CFG_PATH

    def lookup(self, path: str, default: Any = None) -> Any:
        val = _deep_get(self._data, path, default)
        return default if val is None else val

    def section(self, name: str) -> dict:
        sec = self._data.get(name, {})
        return sec if isinstance(sec, dict) else {}


def cfg(path: str, default: Any = None) -> Any:
    return PulseConfig.get().lookup(path, default)


def reload_config() -> PulseConfig:
    return PulseConfig.reload()


# ── Backward-compatible module constants (prefer Pulse_cfg.json) ─────────────

_c = PulseConfig.get()

PULSE_OLLAMA_BASE_URL = str(cfg("llm.ollama_base_url", "http://localhost:11434/v1"))
PULSE_LLM_MODEL = str(cfg("llm.model", "qwen2.5:3b"))
PULSE_EMBED_MODEL = str(cfg("llm.embed.model", "nomic-embed-text"))
PULSE_RAG_BACKEND = str(cfg("rag.backend", "hybrid")).lower()
PULSE_LLM_TIMEOUT = float(cfg("llm.timeout_s", 120))
PULSE_LLM_MAX_TOKENS = int(cfg("llm.max_tokens", 16384))
PULSE_LLM_NUM_PREDICT = int(cfg("llm.num_predict", PULSE_LLM_MAX_TOKENS))
PULSE_LLM_NUM_CTX = int(cfg("llm.num_ctx", _MIN_NUM_CTX))
PULSE_LLM_LOG_IO = bool(cfg("llm.log_io", True))
PULSE_LLM_LOG_DIR = str(cfg("llm.log_dir", "knowledge/data/llm_sessions"))
PULSE_LLM_THINK = str(cfg("llm.think", "low"))
PULSE_LLM_API = str(cfg("llm.api", "auto")).lower()
PULSE_LLM_MAX_CONTEXT = PULSE_LLM_NUM_CTX
PULSE_LLM_MAX_RETRIES = int(cfg("llm.max_retries", 2))
