"""
knowledge/llm_session_log.py
==============================
Persistent JSONL + per-session call records for all LLM exchanges.
Never overwrites prior sessions; each call gets a unique file.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from knowledge.pulse_config import PULSE_LLM_LOG_DIR, PULSE_LLM_LOG_IO

_lock = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_log_dir() -> Path:
    p = Path(PULSE_LLM_LOG_DIR)
    if not p.is_absolute():
        p = _repo_root() / p
    return p


def new_call_id() -> str:
    return uuid.uuid4().hex[:12]


def new_session_id(prefix: str = "sess") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:8]}"


def _unique_path(base: Path) -> Path:
    """If base exists, append _2, _3, ... — never overwrite."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    n = 2
    while True:
        candidate = base.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def record_llm_exchange(
    *,
    call_id: str,
    session_id: str,
    caller: str,
    api: str,
    model: str,
    think: str | bool,
    system: str,
    user: str,
    response: dict,
    duration_ms: float,
    attempt: int = 0,
    meta: Optional[dict[str, Any]] = None,
    backend_id: str = "",
    max_tokens: int | None = None,
    num_ctx: int | None = None,
) -> Optional[Path]:
    """Append JSONL + write unique per-call JSON under sessions/{session_id}/."""
    if not PULSE_LLM_LOG_IO:
        return None

    log_dir = default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()
    content = response.get("content", "") or ""
    thinking = response.get("thinking", "") or ""
    raw = response.get("raw") or {}
    output_block: dict[str, Any] = {
        "content": content,
        "thinking": thinking,
        "tokens": response.get("tokens", 0),
        "error": response.get("error"),
        "done_reason": response.get("done_reason") or raw.get("done_reason") or raw.get("finish_reason") or "",
        "content_len": len(content),
        "thinking_len": len(thinking),
        "eval_count": raw.get("eval_count"),
    }
    if response.get("raw") is not None:
        output_block["raw"] = response.get("raw")

    record: dict[str, Any] = {
        "call_id": call_id,
        "session_id": session_id,
        "caller": caller,
        "backend_id": backend_id,
        "api": api,
        "model": model,
        "think": think,
        "max_tokens": max_tokens,
        "num_ctx": num_ctx,
        "timestamp": ts,
        "duration_ms": round(duration_ms, 1),
        "attempt": attempt,
        "done_reason": output_block["done_reason"],
        "content_len": output_block["content_len"],
        "thinking_len": output_block["thinking_len"],
        "input": {
            "system": system,
            "user": user,
            "system_chars": len(system),
            "user_chars": len(user),
        },
        "output": output_block,
        "meta": meta or {},
    }

    day = ts[:10]
    jsonl_path = log_dir / f"{day}.jsonl"

    session_dir = log_dir / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    call_path = _unique_path(session_dir / f"{call_id}.json")

    line = json.dumps(record, ensure_ascii=False) + "\n"
    manifest_path = session_dir / "manifest.jsonl"

    with _lock:
        with jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        with manifest_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        call_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

        session_meta_path = session_dir / "session_meta.json"
        if not session_meta_path.exists():
            session_meta_path.write_text(
                json.dumps(
                    {
                        "session_id": session_id,
                        "created_at": ts,
                        "caller": caller,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    return call_path
