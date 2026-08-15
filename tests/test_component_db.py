"""
test_component_db.py
====================
Unit tests for ComponentDB and decision assistant candidate matching in core/component_db.py.
"""
import pytest
from core.component_db import ComponentDB, Component

def test_component_db_load():
    db = ComponentDB()
    all_comps = db.all()
    assert len(all_comps) >= 30, f"Expected at least 30 components, got {len(all_comps)}"

def test_inspect_component():
    db = ComponentDB()
    esp32 = db.inspect_component("ESP32-S3-WROOM-1")
    assert esp32["id"] == "ESP32-S3-WROOM-1"
    assert esp32["jlcpcb_part"] == "C2913202"
    assert "espressif.com" in esp32["datasheet"]
    assert esp32["footprint_info"]["package"] == "SMD-44"

def test_find_candidates_text():
    db = ComponentDB()
    candidates = db.find_candidates("LDO regulator", top_k=3)
    assert len(candidates) > 0
    top = candidates[0]
    assert "jlcpcb_part" in top
    assert "datasheet" in top

def test_find_candidates_parametric():
    db = ComponentDB()
    candidates = db.find_candidates({"category": "PMIC", "vout_v": 3.3}, top_k=5)
    assert len(candidates) > 0
    ids = [c["id"] for c in candidates]
    assert "AMS1117-3.3" in ids or "AP2112K-3.3" in ids or "ME6211C33M5G" in ids

def test_get_alternatives():
    db = ComponentDB()
    alts = db.get_alternatives("AMS1117-3.3")
    assert len(alts) > 0
    alt_ids = [a["id"] for a in alts]
    assert "AP2112K-3.3" in alt_ids or "ME6211C33M5G" in alt_ids
