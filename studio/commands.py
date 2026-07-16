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


def resolve_file_references(text: str) -> str:
    """Find references starting with @ and replace them with file contents."""
    import re
    from pathlib import Path

    # Matches @ followed by:
    # 1) double-quoted path: "..."
    # 2) single-quoted path: '...'
    # 3) unquoted path: starts with drive (e.g. C:\... or C:/...) or a normal path segment
    pattern = r'@(?:"([^"]+)"|\'([^\']+)\'|([a-zA-Z]:\\[^\s]+|[a-zA-Z]:/[^\s]+|[\w\.\-\\/]+))'

    def replace_match(match: re.Match) -> str:
        path_str = match.group(1) or match.group(2) or match.group(3)
        path_str = path_str.strip('"\'')
        p = Path(path_str)
        if p.exists() and p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                return f"[Error leyendo archivo en {path_str}: {e}]"
        return match.group(0)

    return re.sub(pattern, replace_match, text)

