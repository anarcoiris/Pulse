"""Unit tests for LLM JSON extraction helpers."""

import json
import pytest

from knowledge.llm_json import extract_json_text, is_reasoning_model, parse_json_object


def test_is_reasoning_model():
    assert is_reasoning_model("qwythos-9b-96k")
    assert is_reasoning_model("deepseek-r1")
    assert not is_reasoning_model("qwen2.5:3b")


def test_parse_fenced_json():
    raw = 'Here is the circuit:\n```json\n{"circuit": [{"etype": "R", "value": 1}]}\n```'
    obj = parse_json_object(raw)
    assert "circuit" in obj


def test_parse_with_thinking_stripped():
    open_tag = "<" + "think" + ">"
    close_tag = "</" + "think" + ">"
    raw = (
        "Some intro\n"
        + f"{open_tag}long reasoning here{close_tag}\n"
        + '{"circuit": [{"etype": "MCU", "value": "ESP32"}]}'
    )
    obj = parse_json_object(raw)
    assert obj["circuit"][0]["value"] == "ESP32"


def test_empty_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_json_object("")
