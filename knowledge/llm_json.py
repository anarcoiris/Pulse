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

    # Fenced JSON
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()

    # Bare object
    obj = re.search(r"\{[\s\S]*\}", text)
    if obj:
        return obj.group(0).strip()

    return text.strip()


def parse_json_object(raw: str) -> dict:
    """Parse JSON object from raw LLM text; raises JSONDecodeError on failure."""
    cleaned = extract_json_text(raw)
    if not cleaned:
        raise json.JSONDecodeError("empty LLM response", raw or "", 0)
    return json.loads(cleaned)
