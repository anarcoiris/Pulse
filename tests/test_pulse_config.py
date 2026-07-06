"""Tests for Pulse_cfg.json loader."""

from knowledge.pulse_config import PulseConfig, cfg, _MIN_NUM_CTX


def test_cfg_loads_llm_model():
    assert cfg("llm.model")


def test_num_ctx_minimum_96k():
    c = PulseConfig.get()
    assert int(c.lookup("llm.num_ctx", 0)) >= _MIN_NUM_CTX


def test_num_predict_at_least_max_tokens():
    c = PulseConfig.get()
    assert int(c.lookup("llm.num_predict", 0)) >= int(c.lookup("llm.max_tokens", 0))
