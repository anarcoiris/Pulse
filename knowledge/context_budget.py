"""
knowledge/context_budget.py
============================
Shared token estimation and context budget management for Pulse LLM agents.

Mirrors the approach used by Tiny Steward (core/llm.py:estimate_messages_tokens)
to prevent context overflow on constrained hardware (see CONSTRAINS.md).

Usage:
    from knowledge.context_budget import estimate_tokens, estimate_history_tokens, ContextBudget

    budget = ContextBudget.from_backend("primary")  # derives from Pulse_cfg.json
    if budget.history_exceeds(messages):
        messages = budget.compact(messages)
"""

from __future__ import annotations

from typing import Any


# ── Token estimation ─────────────────────────────────────────────────────────
# ~3.5 chars/token for mixed ES/EN + JSON is the same heuristic Tiny Steward
# uses.  Per-message overhead accounts for chat-template role tags, BOS/EOS
# tokens, and separator whitespace.

_CHARS_PER_TOKEN = 3.5
_MSG_OVERHEAD_TOKENS = 4  # role header + formatting


def estimate_tokens(text: str) -> int:
    """Estimate token count for a single string."""
    if not text:
        return 0
    return int(len(text) / _CHARS_PER_TOKEN) + 1


def estimate_content_tokens(content: Any) -> int:
    """Estimate tokens for message content (handles str and list)."""
    if isinstance(content, str):
        return estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict):
                total += estimate_tokens(str(part.get("text", "")))
            elif isinstance(part, str):
                total += estimate_tokens(part)
        return total
    return estimate_tokens(str(content or ""))


def estimate_history_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens across all messages in a conversation history."""
    total = 0
    for msg in messages:
        total += estimate_content_tokens(msg.get("content", "") or "")
        # Some backends return reasoning_content separately
        rc = msg.get("reasoning_content")
        if isinstance(rc, str):
            total += estimate_tokens(rc)
        total += _MSG_OVERHEAD_TOKENS
    return total


# ── Context budget ───────────────────────────────────────────────────────────

# What fraction of the total context window the *history* (excluding the
# current turn's output) should occupy.  The remainder is reserved for
# system prompt overhead and the model's output (num_predict).
_HISTORY_RATIO = 0.55

# Messages at the tail that are never dropped during compaction.  Keeps
# the model's most recent exchange intact.
_PROTECTED_TAIL = 4


class ContextBudget:
    """Manages context-window budget for a multi-turn agent loop.

    Instantiate once per agent run; call ``should_compact`` before each LLM
    call and ``compact`` when it returns True.
    """

    def __init__(self, num_ctx: int, num_predict: int = 16384):
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        # History budget = total ctx minus output reservation, capped at ratio
        self.history_budget_tokens = min(
            int(num_ctx * _HISTORY_RATIO),
            num_ctx - num_predict - 512,  # 512 = safety margin for template
        )

    @classmethod
    def from_backend(cls, backend_name: str = "primary") -> "ContextBudget":
        """Create from Pulse_cfg.json backend limits."""
        from knowledge.llm_backends import backend_limits
        limits = backend_limits(backend_name)
        return cls(
            num_ctx=int(limits.get("num_ctx", 131072)),
            num_predict=int(limits.get("max_tokens", 16384)),
        )

    def should_compact(self, messages: list[dict]) -> bool:
        """True if current history exceeds the token budget."""
        return estimate_history_tokens(messages) > self.history_budget_tokens

    def compact(
        self,
        messages: list[dict],
        *,
        protect_head: int = 2,
    ) -> list[dict]:
        """Compact history in-place-style (returns new list).

        Strategy (mirrors Tiny Steward's ``_compact_messages``):
        1. Always preserve: system prompt (idx 0), first user message (idx 1).
        2. Always preserve: last ``_PROTECTED_TAIL`` messages.
        3. Middle messages: summarise skill responses to one line each; if still
           over budget, drop oldest non-protected messages entirely.
        """
        if len(messages) <= protect_head + _PROTECTED_TAIL:
            return messages  # nothing to compact

        head = messages[:protect_head]
        tail = messages[-_PROTECTED_TAIL:]
        middle = messages[protect_head: len(messages) - _PROTECTED_TAIL]

        # Pass 1: trim verbose skill responses to summaries
        compacted_middle: list[dict] = []
        for msg in middle:
            content = msg.get("content", "")
            if (
                msg.get("role") == "user"
                and isinstance(content, str)
                and content.startswith("SYSTEM_SKILL_RESPONSE:")
                and len(content) > 300
            ):
                # Extract first meaningful line as summary
                lines = content.splitlines()
                first_useful = lines[1] if len(lines) > 1 else lines[0]
                msg = {
                    **msg,
                    "content": (
                        f"SYSTEM_SKILL_RESPONSE (compacted — full result used in earlier turn): "
                        f"{first_useful[:200]}"
                    ),
                }
            compacted_middle.append(msg)

        result = head + compacted_middle + tail
        if estimate_history_tokens(result) <= self.history_budget_tokens:
            return result

        # Pass 2: if still over, drop oldest middle messages one by one
        while compacted_middle and estimate_history_tokens(head + compacted_middle + tail) > self.history_budget_tokens:
            compacted_middle.pop(0)

        # If completely empty middle, add a compaction marker
        if not compacted_middle and middle:
            marker = {
                "role": "system",
                "content": (
                    f"[Context compacted: {len(middle)} earlier messages dropped to "
                    f"fit within {self.history_budget_tokens} token budget. "
                    f"Skill lookups from earlier turns are no longer in context.]"
                ),
            }
            return head + [marker] + tail

        return head + compacted_middle + tail

    def utilization(self, messages: list[dict]) -> float:
        """Return 0.0–1.0+ indicating how full the history budget is."""
        if self.history_budget_tokens <= 0:
            return 1.0
        return estimate_history_tokens(messages) / self.history_budget_tokens
