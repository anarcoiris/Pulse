"""Tests for Ollama native streaming (no live Ollama required)."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

from knowledge.llm_types import StreamAccumulator, StreamChunk
from knowledge.ollama_native import chat_native_stream


def _ndjson_response(*lines: dict) -> bytes:
  body = "".join(json.dumps(line) + "\n" for line in lines)
  return body.encode("utf-8")


def test_stream_accumulator_merges_chunks():
    acc = StreamAccumulator()
    acc.consume(StreamChunk(kind="thinking", text="plan "))
    acc.consume(StreamChunk(kind="thinking", text="more"))
    acc.consume(StreamChunk(kind="content", text='{"circuit":'))
    acc.consume(StreamChunk(kind="done", done_reason="stop", tokens=42, model="test-model"))
    result = acc.to_result()
    assert result["thinking"] == "plan more"
    assert result["content"] == '{"circuit":'
    assert result["done_reason"] == "stop"
    assert result["tokens"] == 42
    assert result["model"] == "test-model"


def test_stream_accumulator_error():
    acc = StreamAccumulator()
    acc.consume(StreamChunk(kind="error", error="connection refused"))
    assert acc.to_result() == {"error": "connection refused"}


@patch("urllib.request.urlopen")
def test_chat_native_stream_yields_thinking_content_done(mock_urlopen):
    ndjson_lines = [
        json.dumps({"message": {"thinking": "hmm"}, "done": False}).encode("utf-8") + b"\n",
        json.dumps({"message": {"content": "{"}, "done": False}).encode("utf-8") + b"\n",
        json.dumps({
            "message": {"content": "}"},
            "done": True,
            "done_reason": "stop",
            "eval_count": 10,
            "model": "qwythos",
        }).encode("utf-8") + b"\n",
        b"",
    ]
    mock_resp = MagicMock()
    mock_resp.readline = MagicMock(side_effect=ndjson_lines)
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    chunks = list(
        chat_native_stream(
            api_url="http://localhost:11431/api/chat",
            model="qwythos",
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    kinds = [c.kind for c in chunks]
    assert kinds == ["thinking", "content", "content", "done"]
    assert chunks[-1].done_reason == "stop"
    assert chunks[-1].tokens == 10


@patch("urllib.request.urlopen")
def test_chat_native_stream_http_error(mock_urlopen):
    import urllib.error

    err = urllib.error.HTTPError("http://x", 500, "fail", {}, io.BytesIO(b"boom"))
    mock_urlopen.side_effect = err
    chunks = list(
        chat_native_stream(
            api_url="http://localhost:11431/api/chat",
            model="qwythos",
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    assert len(chunks) == 1
    assert chunks[0].kind == "error"
    assert "500" in chunks[0].error
