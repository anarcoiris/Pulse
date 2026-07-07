"""
studio/commands.py
==================
Slash-command parsing for the Forge Studio REPL.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedCommand:
    name: str
    args: str
    is_slash: bool = True


def parse_input(line: str) -> ParsedCommand | str:
    """Return ParsedCommand for slash input, or raw prompt string."""
    text = line.strip()
    if not text:
        return ""
    if not text.startswith("/"):
        return text
    parts = text[1:].split(maxsplit=1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return ParsedCommand(name=name, args=args)
