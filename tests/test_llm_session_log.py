"""Tests for LLM session I/O logging."""

import json
from pathlib import Path

import pytest

from knowledge import llm_session_log as log


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(log, "PULSE_LLM_LOG_IO", True)
    monkeypatch.setattr(log, "PULSE_LLM_LOG_DIR", str(tmp_path))
    return tmp_path


def test_record_llm_exchange_writes_jsonl_and_call_file(log_dir):
    path = log.record_llm_exchange(
        call_id="abc123",
        session_id="sess1",
        caller="test",
        api="native",
        model="qwythos-9b-96k",
        think="low",
        system="sys",
        user="user prompt",
        response={"content": '{"circuit":[]}', "thinking": "reasoning", "tokens": 10},
        duration_ms=1234.5,
        meta={"test": "x"},
    )
    assert path is not None
    assert path.exists()

    jsonl_files = list(log_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    line = json.loads(jsonl_files[0].read_text(encoding="utf-8").strip())
    assert line["call_id"] == "abc123"
    assert line["caller"] == "test"
    assert line["input"]["user"] == "user prompt"
    assert line["output"]["content"] == '{"circuit":[]}'


def test_record_skipped_when_disabled(log_dir, monkeypatch):
    monkeypatch.setattr(log, "PULSE_LLM_LOG_IO", False)
    path = log.record_llm_exchange(
        call_id="x",
        session_id="s",
        caller="t",
        api="openai",
        model="m",
        think=False,
        system="",
        user="",
        response={"content": ""},
        duration_ms=1,
    )
    assert path is None


def test_session_dir_unique_calls(log_dir, monkeypatch):
    monkeypatch.setattr(log, "PULSE_LLM_LOG_IO", True)
    sid = "test_sess_001"
    p1 = log.record_llm_exchange(
        call_id="abc123",
        session_id=sid,
        caller="test",
        api="native",
        model="m",
        think="low",
        system="sys",
        user="user",
        response={"content": "{}", "thinking": "t"},
        duration_ms=1,
    )
    p2 = log.record_llm_exchange(
        call_id="abc123",
        session_id=sid,
        caller="test",
        api="native",
        model="m",
        think="low",
        system="sys2",
        user="user2",
        response={"content": "{}"},
        duration_ms=2,
    )
    assert p1 != p2
    assert (log_dir / "sessions" / sid / "manifest.jsonl").exists()
