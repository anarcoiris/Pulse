"""
tests/test_corpus_rules.py
==========================
Unit tests for PulseLab CorpusEvaluator, neutral model conversion,
and domain rules (I2C pull-ups, boot strapping, power-on reset, decoupling).
"""

import pytest
from core.corpus_evaluator import CorpusEvaluator, parse_numeric_value


def test_parse_numeric_value():
    assert parse_numeric_value("4.7k") == 4700.0
    assert parse_numeric_value("10kΩ") == 10000.0
    assert parse_numeric_value("100nF") == pytest.approx(1e-7)
    assert parse_numeric_value("10uF") == pytest.approx(1e-5)
    assert parse_numeric_value("330") == 330.0


def test_power_on_reset_rule():
    evaluator = CorpusEvaluator()

    # Good circuit: U1 has EN with pull-up R1 to 3.3V
    good_circuit = {
        "circuit": [
            {"label": "U1", "etype": "MCU", "value": "ESP32-S3", "pins": {"3": "EN_NET", "2": "3.3V", "1": "GND"}},
            {"label": "R1", "etype": "R", "value": "10k", "n1": "EN_NET", "n2": "3.3V"}
        ]
    }
    findings = evaluator.evaluate(good_circuit)
    en_findings = [f for f in findings if f["rule_id"] == "schematic.power_on_reset.en_pullup"]
    assert len(en_findings) == 0

    # Bad circuit: EN missing pull-up
    bad_circuit = {
        "circuit": [
            {"label": "U1", "etype": "MCU", "value": "ESP32-S3", "pins": {"3": "EN_NET", "2": "3.3V", "1": "GND"}}
        ]
    }
    findings_bad = evaluator.evaluate(bad_circuit)
    en_bad = [f for f in findings_bad if f["rule_id"] == "schematic.power_on_reset.en_pullup"]
    assert len(en_bad) == 1
    assert en_bad[0]["severity"] == "critical"

    # Inverted circuit: EN tied directly to GND
    grounded_circuit = {
        "circuit": [
            {"label": "U1", "etype": "MCU", "value": "ESP32-S3", "pins": {"3": "GND", "2": "3.3V", "1": "GND"}}
        ]
    }
    findings_gnd = evaluator.evaluate(grounded_circuit)
    en_gnd = [f for f in findings_gnd if f["rule_id"] == "schematic.power_on_reset.en_pullup"]
    assert len(en_gnd) == 1
    assert "reset permanente" in en_gnd[0]["message"]


def test_i2c_bus_pullups_rule():
    evaluator = CorpusEvaluator()

    # Good I2C circuit: OLED with SCL/SDA pulled up to 3.3V via 4.7k
    good_i2c = {
        "circuit": [
            {"label": "DISP1", "etype": "IC", "value": "SSD1306", "pins": {"1": "GND", "2": "3.3V", "3": "I2C_SCL", "4": "I2C_SDA"}},
            {"label": "R_SCL", "etype": "R", "value": "4.7k", "n1": "I2C_SCL", "n2": "3.3V"},
            {"label": "R_SDA", "etype": "R", "value": "4.7k", "n1": "I2C_SDA", "n2": "3.3V"},
            {"label": "C_DISP", "etype": "C", "value": "100nF", "n1": "3.3V", "n2": "GND"}
        ]
    }
    findings = evaluator.evaluate(good_i2c)
    i2c_findings = [f for f in findings if f["rule_id"] == "schematic.i2c_bus.pullup_to_power_rail"]
    assert len(i2c_findings) == 0

    # Bad I2C circuit: SCL pulled down to GND (observed bug)
    bad_i2c = {
        "circuit": [
            {"label": "DISP1", "etype": "IC", "value": "SSD1306", "pins": {"1": "GND", "2": "3.3V", "3": "I2C_SCL", "4": "I2C_SDA"}},
            {"label": "R_SCL", "etype": "R", "value": "4.7k", "n1": "I2C_SCL", "n2": "GND"},
            {"label": "R_SDA", "etype": "R", "value": "4.7k", "n1": "I2C_SDA", "n2": "3.3V"},
            {"label": "C_DISP", "etype": "C", "value": "100nF", "n1": "3.3V", "n2": "GND"}
        ]
    }
    findings_bad = evaluator.evaluate(bad_i2c)
    i2c_bad = [f for f in findings_bad if f["rule_id"] == "schematic.i2c_bus.pullup_to_power_rail"]
    assert len(i2c_bad) >= 1
    assert any("bloqueo del bus" in f["message"] for f in i2c_bad)


def test_boot_strap_pins_rule():
    evaluator = CorpusEvaluator()

    # Strapping pin shorted to ground without switch
    shorted_strap = {
        "circuit": [
            {"label": "U1", "etype": "MCU", "value": "ESP32-S3", "pins": {"27": "GND", "3": "EN_NET", "2": "3.3V", "1": "GND"}},
            {"label": "R_EN", "etype": "R", "value": "10k", "n1": "EN_NET", "n2": "3.3V"}
        ]
    }
    findings = evaluator.evaluate(shorted_strap)
    strap_findings = [f for f in findings if f["rule_id"] == "schematic.mcu.boot_strap_pins"]
    assert len(strap_findings) == 1
    assert strap_findings[0]["severity"] == "critical"


def test_decoupling_rule():
    evaluator = CorpusEvaluator()

    # Missing decoupling cap on IC
    missing_cap = {
        "circuit": [
            {"label": "U_RF", "etype": "IC", "value": "CC1101", "pins": {"1": "3.3V", "2": "GND"}}
        ]
    }
    findings = evaluator.evaluate(missing_cap)
    decoupling_findings = [f for f in findings if f["rule_id"] == "ee_fundamentals.decoupling.per_ic_100nf"]
    assert len(decoupling_findings) == 1
    assert decoupling_findings[0]["severity"] == "warning"
