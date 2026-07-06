"""Tests for atomic lane profile helpers."""

import json

from knowledge.atomic_lane import canonical_profile, read_state, slot_context_tokens


def test_canonical_profile_aliases():
    assert canonical_profile("default") == "concurrent2"
    assert canonical_profile("burst") == "concurrent3"
    assert canonical_profile("solo") == "longctx"


def test_read_state_and_slot_ctx(tmp_path, monkeypatch):
    state_file = tmp_path / "qwythos.state.json"
    state_file.write_text(
        json.dumps(
            {
                "atomic": {
                    "profile": "concurrent2",
                    "parallel": 2,
                    "slotCtx": 49152,
                    "port": 11439,
                }
            }
        ),
        encoding="utf-8",
    )
    import knowledge.atomic_lane as al
    monkeypatch.setattr(al, "_state_path", lambda: state_file)
    data = read_state()
    assert data["atomic"]["profile"] == "concurrent2"
    assert slot_context_tokens() == 49152
