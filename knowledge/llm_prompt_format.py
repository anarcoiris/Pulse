"""
knowledge/llm_prompt_format.py
================================
Backend-specific JSON prompt shaping for MCP / circuit synthesis.
Atomic lane: OpenAI json_object, no thinking, compact system prompt.
"""

from __future__ import annotations

from knowledge.llm_backends import backend_limits


ATOMIC_JSON_SUFFIX = (
    "\n\nOUTPUT RULES (atomic executor):\n"
    "- Respond with ONE raw JSON object only.\n"
    "- Root key MUST be \"circuit\" containing an array of components.\n"
    "- No markdown fences, no prose, no keys outside the schema.\n"
    "- Each component: etype, value, label; use pins for IC/MCU else n1/n2.\n"
    "- If context gives a component's full pin table, account for every pin: for any\n"
    "  physical pin intentionally left floating, map it to \"NC\" inside \"pins\" or list\n"
    "  its number in an \"unconnected_pins\" array. Never omit a known pin silently.\n"
)


def format_system_prompt(base_system: str, backend: str) -> str:
    limits = backend_limits(backend)
    budget = limits["prompt_max_chars"]
    prompt = base_system
    if backend == "atomic":
        prompt += ATOMIC_JSON_SUFFIX
    if len(prompt) > budget:
        prompt = prompt[:budget]
    return prompt


def format_user_prompt(user: str, backend: str) -> str:
    if backend != "atomic":
        return user
    return user + "\n\nJSON object only. Root key: circuit."


def chat_options_for_backend(backend: str) -> dict:
    limits = backend_limits(backend)
    opts = {
        "max_tokens": limits["max_tokens"],
        "json_mode": limits["json_mode"],
        "disable_thinking": backend == "atomic" or limits.get("think") in (False, "none", "false"),
    }
    return opts
