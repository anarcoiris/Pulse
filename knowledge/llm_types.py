"""
knowledge/llm_types.py
========================
Shared types for LLM transport (streaming and chat history).
No UI dependencies — safe for knowledge/, studio/, and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


ChunkKind = Literal["thinking", "content", "done", "error"]


@dataclass
class StreamChunk:
    kind: ChunkKind
    text: str = ""
    done_reason: str = ""
    tokens: int = 0
    model: str = ""
    error: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.kind in ("done", "error")


@dataclass
class StreamAccumulator:
    """Collects stream chunks into a final LLM result dict."""

    content: str = ""
    thinking: str = ""
    done_reason: str = ""
    tokens: int = 0
    model: str = ""
    error: str = ""

    def consume(self, chunk: StreamChunk) -> None:
        if chunk.kind == "thinking" and chunk.text:
            self.thinking += chunk.text
        elif chunk.kind == "content" and chunk.text:
            self.content += chunk.text
        elif chunk.kind == "done":
            if chunk.done_reason:
                self.done_reason = chunk.done_reason
            if chunk.tokens:
                self.tokens = chunk.tokens
            if chunk.model:
                self.model = chunk.model
        elif chunk.kind == "error":
            self.error = chunk.error or chunk.text

    def to_result(self) -> dict:
        if self.error:
            return {"error": self.error}
        raw: dict = {"done_reason": self.done_reason}
        if self.done_reason:
            raw["finish_reason"] = self.done_reason
        return {
            "content": self.content,
            "thinking": self.thinking,
            "model": self.model,
            "tokens": self.tokens,
            "done_reason": self.done_reason,
            "raw": raw,
        }
