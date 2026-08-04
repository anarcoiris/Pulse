"""
knowledge/llm_json.py
=====================
Parse JSON from LLM responses (reasoning models, markdown fences, think blocks).
"""

from __future__ import annotations
import json
import re


def is_reasoning_model(model: str) -> bool:
    m = model.lower()
    return any(k in m for k in ("qwythos", "deepseek-r", "r1", "reason", "think", "qwq"))


def extract_json_text(raw: str) -> str:
    """Strip thinking traces and pull the first JSON object from model output."""
    if not raw:
        return ""
    text = raw.strip()

    # Qwythos / Qwen-style thinking blocks
    open_tag = "<" + "think" + ">"
    close_tag = "</" + "think" + ">"
    while open_tag in text:
        start = text.find(open_tag)
        end = text.find(close_tag, start)
        if end == -1:
            text = text[:start]
            break
        text = text[:start] + text[end + len(close_tag) :]
    text = re.sub(r"Thinking\.\.\..*?done thinking\.?\s*", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Fenced JSON (object or array)
    fence = re.search(r"```(?:json)?\s*([\{\[\s\S]*?[\}\]])\s*```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()

    # Bare object or array
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        return m.group(1).strip()

    return text.strip()


def parse_json_object(raw: str) -> dict | list:
    """Parse JSON object or array from raw LLM text; raises JSONDecodeError on failure."""
    cleaned = extract_json_text(raw)
    if not cleaned:
        raise json.JSONDecodeError("empty LLM response", raw or "", 0)
    return json.loads(cleaned)


def parse_llm_result(content: str, thinking: str = "") -> dict:
    """Parse JSON from content, falling back to thinking when content is empty."""
    last_err: json.JSONDecodeError | None = None
    for raw in (content, thinking):
        if not (raw or "").strip():
            continue
        try:
            return parse_json_object(raw)
        except json.JSONDecodeError as exc:
            last_err = exc
    if last_err is not None:
        raise last_err
    raise json.JSONDecodeError("empty LLM response", content or "", 0)


def llm_output_truncated(result: dict) -> bool:
    """True when the model hit output budget or returned no usable text."""
    reason = str(result.get("done_reason") or "").lower()
    if reason == "length":
        return True
    content = (result.get("content") or "").strip()
    thinking = (result.get("thinking") or "").strip()
    if reason == "stop" and not content and not thinking:
        return True
    return not content and not thinking
