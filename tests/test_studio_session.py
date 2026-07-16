"""Tests for Forge Studio command parsing and session (no live LLM)."""

from studio.commands import ParsedCommand, parse_input, resolve_file_references
from studio.session import ForgeSession


def test_parse_free_text():
    assert parse_input("ESP32 con BME280") == "ESP32 con BME280"


def test_parse_slash_command():
    cmd = parse_input("/generate ESP32 sensors")
    assert isinstance(cmd, ParsedCommand)
    assert cmd.name == "generate"
    assert cmd.args == "ESP32 sensors"


def test_parse_empty():
    assert parse_input("   ") == ""


def test_session_info_has_id():
    sess = ForgeSession(backend="primary")
    info = sess.session_info()
    assert info["session_id"].startswith("studio_")
    assert info["components"] == 0


def test_resolve_file_references(tmp_path):
    # Test file that doesn't exist
    assert resolve_file_references("@not_existing_file.txt") == "@not_existing_file.txt"

    # Test existing file
    temp_file = tmp_path / "test_prompt.txt"
    temp_file.write_text("Hello from file!", encoding="utf-8")

    # Absolute/relative path resolves correctly
    resolved = resolve_file_references(f"@{temp_file}")
    assert resolved == "Hello from file!"

    # Quoted path
    resolved_quoted = resolve_file_references(f'@"{temp_file}"')
    assert resolved_quoted == "Hello from file!"

    # Text mixing
    mixed = resolve_file_references(f"Pre text @{temp_file} post text")
    assert mixed == "Pre text Hello from file! post text"

