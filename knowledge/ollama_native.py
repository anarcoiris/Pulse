"""
knowledge/ollama_native.py
==========================
Ollama native /api/chat client with thinking support (think: low|medium|high|false).

Use stream=false for programmatic JSON extraction; stream=true only for interactive UI.
OpenAI-compat /v1/chat/completions does not expose the native `think` field — use this module.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterator

from knowledge.llm_types import StreamChunk


def ollama_native_url(base_url_v1: str) -> str:
    """http://host:11431/v1 -> http://host:11431/api/chat"""
    root = base_url_v1.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    return f"{root}/api/chat"


def normalize_think(value: str | bool | None) -> str | bool:
    """Map env/config strings to Ollama think parameter."""
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in ("none", "false", "off", "0", "no"):
        return False
    if v in ("true", "on", "1", "yes"):
        return True
    if v in ("low", "medium", "high", "max"):
        return v
    return False


def chat_native(
    *,
    api_url: str,
    model: str,
    messages: list[dict[str, str]],
    think: str | bool = False,
    stream: bool = False,
    temperature: float = 0.3,
    num_predict: int | None = None,
    num_ctx: int | None = None,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """
    POST /api/chat (non-streaming).

    Returns dict with keys: content, thinking, model, tokens (eval_count), raw.
    """
    from knowledge.pulse_config import PULSE_LLM_NUM_CTX, PULSE_LLM_NUM_PREDICT

    if num_predict is None:
        num_predict = PULSE_LLM_NUM_PREDICT
    if num_ctx is None:
        num_ctx = PULSE_LLM_NUM_CTX

    options: dict[str, Any] = {
        "temperature": temperature,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "think": think,
        "options": options,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        return {"error": f"Ollama native HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"error": f"Ollama native error: {e}"}

    msg = body.get("message") or {}
    done_reason = body.get("done_reason") or ""
    return {
        "content": msg.get("content") or "",
        "thinking": msg.get("thinking") or "",
        "model": body.get("model") or model,
        "tokens": body.get("eval_count") or 0,
        "done_reason": done_reason,
        "raw": body,
    }


def _build_native_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    think: str | bool,
    stream: bool,
    temperature: float,
    num_predict: int,
    num_ctx: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "stream": stream,
        "think": think,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
        },
    }


def chat_native_stream(
    *,
    api_url: str,
    model: str,
    messages: list[dict[str, str]],
    think: str | bool = False,
    temperature: float = 0.3,
    num_predict: int | None = None,
    num_ctx: int | None = None,
    timeout: float = 300.0,
) -> Iterator[StreamChunk]:
    """
    POST /api/chat with stream=true; yield StreamChunk per NDJSON line.

    On HTTP or connection errors yields a single error chunk then stops.
    """
    from knowledge.pulse_config import PULSE_LLM_NUM_CTX, PULSE_LLM_NUM_PREDICT

    if num_predict is None:
        num_predict = PULSE_LLM_NUM_PREDICT
    if num_ctx is None:
        num_ctx = PULSE_LLM_NUM_CTX

    payload = _build_native_payload(
        model=model,
        messages=messages,
        think=think,
        stream=True,
        temperature=temperature,
        num_predict=num_predict,
        num_ctx=num_ctx,
    )

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            buffer = ""
            while True:
                raw_line = resp.readline()
                if not raw_line:
                    break
                buffer += raw_line.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        body = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = body.get("message") or {}
                    thinking = msg.get("thinking") or ""
                    content = msg.get("content") or ""
                    if thinking:
                        yield StreamChunk(kind="thinking", text=thinking, model=body.get("model") or model)
                    if content:
                        yield StreamChunk(kind="content", text=content, model=body.get("model") or model)
                    if body.get("done"):
                        yield StreamChunk(
                            kind="done",
                            done_reason=body.get("done_reason") or "",
                            tokens=int(body.get("eval_count") or 0),
                            model=body.get("model") or model,
                        )
                        return
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        yield StreamChunk(kind="error", error=f"Ollama native HTTP {e.code}: {detail}")
    except Exception as e:
        yield StreamChunk(kind="error", error=f"Ollama native stream error: {e}")
