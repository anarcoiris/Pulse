"""
test_provider_fetcher.py
========================
Unit tests for multi-provider component fetchers (JLCPCB & PCBWay) and ProviderFetchManager.
"""
import pytest
from core.providers.jlcpcb_fetcher import JLCPCBProviderFetcher
from core.providers.pcbway_fetcher import PCBWayProviderFetcher
from core.provider_fetcher import ProviderFetchManager
from core.component_db import ComponentDB

def test_jlcpcb_fetcher():
    fetcher = JLCPCBProviderFetcher()
    results = fetcher.search("CH340G", limit=3)
    assert len(results) > 0
    top = results[0]
    assert top.provider == "jlcpcb"
    assert top.part_number != ""
    assert top.mpn != ""

def test_jlcpcb_get_by_part_number():
    fetcher = JLCPCBProviderFetcher()
    res = fetcher.get_by_part_number("C14267")
    assert res is not None
    assert res.provider == "jlcpcb"
    assert "C14267" in res.part_number or res.mpn == "CH340G"

def test_pcbway_fetcher():
    fetcher = PCBWayProviderFetcher()
    results = fetcher.search("CH340G", limit=3)
    assert len(results) > 0
    top = results[0]
    assert top.provider == "pcbway"
    assert top.part_number != ""
    assert top.mpn != ""

def test_provider_fetch_manager():
    manager = ProviderFetchManager()
    all_res = manager.search_all_providers("ESP32-S3", limit=3)
    assert "jlcpcb" in all_res
    assert "pcbway" in all_res
    assert len(all_res["jlcpcb"]) > 0
    assert len(all_res["pcbway"]) > 0

def test_component_comparison():
    manager = ProviderFetchManager()
    comp = manager.get_component_comparison("CH340G")
    assert "jlcpcb" in comp
    assert "pcbway" in comp
    assert "recommendation" in comp
    assert comp["jlcpcb"]["part_number"] != "N/A"

def test_component_db_search_with_providers():
    db = ComponentDB()
    res = db.search_with_providers("AMS1117-3.3", top_k=3)
    assert "local_candidates" in res
    assert "provider_comparison" in res
    assert len(res["local_candidates"]) > 0
