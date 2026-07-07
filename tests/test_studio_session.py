"""Tests for Forge Studio command parsing and session (no live LLM)."""

from studio.commands import ParsedCommand, parse_input
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
