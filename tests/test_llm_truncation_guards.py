"""
tests/test_llm_truncation_guards.py
====================================
Session 4c P3 — fixture-based regression tests for the four LLM output failure
modes documented in docs/calibration_forge/llm_truncation_review_06072026.md:

1. Stub semantico   — valid JSON but an MCU/IC with an injected full pinout has
                       no "pins"/"unconnected_pins" at all.
2. Truncacion dura   — done_reason == "length" with empty content.
3. Reviewer truncado — the entire output budget went to "thinking", content is
                       empty (recovered via llm_json.parse_llm_result).
4. Enumeracion runaway — the model declares far more pins than the component's
                       real pinout (e.g. 1..1000) when no reference table was
                       actually available/matched.

These use CircuitSynthesizer() directly (real RAG + pinouts_db, no network
calls) and a fake `llm` duck-type object for the continuation-turn test, so
none of this suite requires a live Ollama/llama-server backend.
"""

import json

import pytest

from knowledge.circuit_synthesizer import CircuitSynthesizer
from knowledge.llm_json import llm_output_truncated, parse_llm_result


@pytest.fixture(scope="module")
def synth() -> CircuitSynthesizer:
    return CircuitSynthesizer(ab_variant="a")


# --- Failure mode 1: stub MCU without pins -------------------------------


def test_stub_mcu_without_pins_is_rejected(synth: CircuitSynthesizer):
    description = "Circuito con un ESP32-WROOM-32 y una pantalla OLED SSD1306"
    components = [
        {"etype": "MCU", "value": "ESP32-WROOM-32", "label": "U1"},
    ]
    err = synth._validate_injected_pinouts(components, description)
    assert err is not None
    assert "sin pines" in err


def test_mcu_with_partial_pins_is_rejected(synth: CircuitSynthesizer):
    """Regression test for a live finding (06-jul-2026 verification run,
    validate_20260706_213340_b12415d7): the model returned valid JSON with a
    non-empty but tiny pins dict (4/39) for a component with a full pinout
    injected — JSON-valid, non-empty, but still a "stub" per FIDELIDAD DE
    PINES. The plain "not declared" check misses this; the >=90% coverage
    guard should catch it."""
    description = "Circuito con un ESP32-WROOM-32 y una pantalla OLED SSD1306"
    components = [
        {
            "etype": "MCU",
            "value": "ESP32-WROOM-32",
            "label": "U1",
            "pins": {"1": "GND", "2": "VCC33", "33": "I2C_SDA", "36": "I2C_SCL"},
        }
    ]
    err = synth._validate_injected_pinouts(components, description)
    assert err is not None
    assert "cobertura de pines incompleta" in err


def test_mcu_with_declared_pins_passes(synth: CircuitSynthesizer):
    description = "Circuito con un ESP32-WROOM-32 y una pantalla OLED SSD1306"
    matched = synth._match_pinouts(description)
    assert matched, "expected the RAG pinout index to resolve ESP32-WROOM-32"
    _, entry = matched[0]
    full_pins = entry.get("pins") or {}
    assert full_pins, "fixture assumption: ESP32-WROOM-32 has a non-empty pin table"

    components = [{"etype": "MCU", "value": "ESP32-WROOM-32", "label": "U1", "pins": dict(full_pins)}]
    err = synth._validate_injected_pinouts(components, description)
    assert err is None


# --- Failure mode 2: hard truncation, empty content -----------------------


def test_length_truncation_with_empty_content_is_truncated():
    result = {"done_reason": "length", "content": "", "thinking": ""}
    assert llm_output_truncated(result) is True


def test_components_from_llm_result_flags_truncation(synth: CircuitSynthesizer):
    result = {"done_reason": "length", "content": "", "thinking": ""}
    components, err = synth._components_from_llm_result(result, "cualquier descripcion")
    assert components is None
    assert err is not None and "truncado" in err.lower()


# --- Failure mode 3: reviewer truncated, only thinking has content --------


def test_reviewer_response_recovered_from_thinking_when_content_empty():
    thinking_json = json.dumps({"issues": [{"msg": "GND flotante", "severity": "critical"}]})
    data = parse_llm_result("", thinking_json)
    assert data["issues"][0]["severity"] == "critical"


def test_reviewer_stop_with_empty_content_and_thinking_is_truncated():
    # done_reason == "stop" but both content and thinking are empty: still a
    # failure, not a valid "zero issues" result (see llm_output_truncated).
    result = {"done_reason": "stop", "content": "", "thinking": ""}
    assert llm_output_truncated(result) is True


# --- Failure mode 4: runaway pin enumeration -------------------------------


def test_runaway_pin_enumeration_is_rejected(synth: CircuitSynthesizer):
    description = "Circuito con un ESP32-WROOM-32 y una pantalla OLED SSD1306"
    matched = synth._match_pinouts(description)
    assert matched
    _, entry = matched[0]
    expected_count = len(entry.get("pins") or {})
    assert expected_count > 0

    runaway_pins = {str(n): f"GPIO{n}" for n in range(1, expected_count * 3 + 50)}
    components = [{"etype": "MCU", "value": "ESP32-WROOM-32", "label": "U1", "pins": runaway_pins}]
    err = synth._validate_injected_pinouts(components, description)
    assert err is not None
    assert "sospechosa" in err


# --- Continuation-turn recovery (no live LLM; fake client) ----------------


class _FakeTruncatedThenCompleteLLM:
    """Duck-types LLMClient.chat(): first call truncates mid-array, a single
    continuation turn completes the JSON."""

    def __init__(self):
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "content": '{"circuit": [{"etype": "GND", "value": 0, "label": "G1"',
                "thinking": "",
                "done_reason": "length",
            }
        return {
            "content": '}]}',
            "thinking": "",
            "done_reason": "stop",
        }


def test_continuation_turn_recovers_truncated_json(synth: CircuitSynthesizer):
    fake_llm = _FakeTruncatedThenCompleteLLM()
    first_result = fake_llm.chat()
    components, err = synth._continue_truncated_json(
        system_prompt="system",
        user_msg="user",
        description="",
        backend_name="primary",
        llm=fake_llm,
        session_id="test-session",
        meta={},
        first_result=first_result,
    )
    assert err is None
    assert components == [{"etype": "GND", "value": 0, "label": "G1"}]
    assert fake_llm.calls == 2  # 1 initial (above) + 1 continuation turn
