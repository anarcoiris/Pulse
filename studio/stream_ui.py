"""
studio/stream_ui.py
===================
Rich streaming renderer for Forge Studio (Windows-safe, ASCII tags).
"""

from __future__ import annotations

from typing import Callable

from knowledge.llm_types import StreamChunk

try:
    from rich.console import Console
    from rich.style import Style
except ImportError:  # pragma: no cover
    Console = None  # type: ignore


_THINKING_STYLE = Style(dim=True, color="bright_black")
_CONTENT_STYLE = Style(color="cyan")
_DONE_OK = Style(color="green")
_DONE_WARN = Style(color="yellow", bold=True)
_ERROR_STYLE = Style(color="red", bold=True)


class StreamRenderer:
    """Incremental token display for thinking/content channels."""

    def __init__(self, console: "Console | None" = None):
        if Console is None:
            raise ImportError("rich is required for Forge Studio. Run: pip install 'rich>=13,<14'")
        self.console = console or Console(legacy_windows=False, force_terminal=True)
        self._thinking_open = False
        self._content_open = False

    def _ensure_thinking_header(self) -> None:
        if not self._thinking_open:
            self.console.print("[thinking]", style=_THINKING_STYLE, end=" ")
            self._thinking_open = True

    def _ensure_content_header(self) -> None:
        if not self._content_open:
            if self._thinking_open:
                self.console.print()
            self.console.print("[content]", style=_CONTENT_STYLE, end=" ")
            self._content_open = True

    def render_chunk(self, chunk: StreamChunk) -> None:
        if chunk.kind == "thinking" and chunk.text:
            self._ensure_thinking_header()
            self.console.print(chunk.text, style=_THINKING_STYLE, end="")
        elif chunk.kind == "content" and chunk.text:
            self._ensure_content_header()
            self.console.print(chunk.text, style=_CONTENT_STYLE, end="")
        elif chunk.kind == "done":
            if self._thinking_open or self._content_open:
                self.console.print()
            reason = chunk.done_reason or "stop"
            style = _DONE_WARN if reason == "length" else _DONE_OK
            self.console.print(
                f"[done] reason={reason} tokens={chunk.tokens}",
                style=style,
            )
            self._reset()
        elif chunk.kind == "error":
            self.console.print(f"[error] {chunk.error or chunk.text}", style=_ERROR_STYLE)
            self._reset()

    def _reset(self) -> None:
        self._thinking_open = False
        self._content_open = False

    def on_chunk_callback(self) -> Callable[[StreamChunk], None]:
        return self.render_chunk

    def print_info(self, msg: str) -> None:
        self.console.print(msg)

    def print_error(self, msg: str) -> None:
        self.console.print(f"[error] {msg}", style=_ERROR_STYLE)

    def print_ok(self, msg: str) -> None:
        self.console.print(f"[ok] {msg}", style=_DONE_OK)
