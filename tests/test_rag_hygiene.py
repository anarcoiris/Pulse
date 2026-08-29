"""
tests/test_rag_hygiene.py
==========================
Automated test suite verifying RAG memory hygiene, gatekeeper enforcement,
remediation text filtering, QA fixture exclusions, and SHA-256 fingerprinting.
"""

import os
import json
import pytest
from pathlib import Path

from knowledge.rag_engine import ElectronicsKnowledgeBase
from knowledge.design_experience import DesignExperience, record_design_outcome


def test_gatekeeper_rejects_failed_experience(tmp_path):
    """Verifies that DesignExperience with passed=False or drc_violations > 0 is rejected by RAG."""
    exp = DesignExperience(
        board_id="test_failed_board_123",
        timestamp="2026-08-30T00:00:00Z",
        mcu="ESP32-TEST",
        passed=False,
        drc_violations=3,
        lessons_learned=[
            "Remediated issue: Floating pin on EN",
            "Always add 10k pull-up to EN"
        ]
    )
    
    # Attempting to ingest unverified experience must return 0 chunks ingested
    n_ingested = exp.ingest_to_rag()
    assert n_ingested == 0, "Gatekeeper failed: Ingested chunks from a passed=False experience!"


def test_remediation_text_filtering(tmp_path):
    """Verifies that raw debug/remediation text strings are stripped from lessons."""
    kb = ElectronicsKnowledgeBase()
    initial_count = len(kb._chunks)

    # Ingest text directly with remediation string
    kb.ingest_text(
        "Remediated issue: Missing pin connections on component C1",
        source="Experience:test_debug",
        chunk_type="design_experience"
    )
    # The raw ingest_text accepts whatever text is passed, but DesignExperience filters it:
    exp = DesignExperience(
        board_id="test_passed_board_456",
        timestamp="2026-08-30T00:00:00Z",
        mcu="ESP32-TEST",
        passed=True,
        drc_violations=0,
        lessons_learned=[
            "Remediated issue: Missing pin connections on component C1",
            "Use 10uF ceramic decoupling capacitor adjacent to VCC"
        ]
    )
    
    n_ingested = exp.ingest_to_rag()
    assert n_ingested == 1, "Only the clean lesson should have been ingested!"


def test_qa_fixture_exclusion():
    """Verifies that KiCad parser unit test fixtures (e.g. error/bugtest files) are excluded from RAG."""
    kb = ElectronicsKnowledgeBase()
    
    excluded_keywords = ["_error", "bugtest", "erc_", "noconnect", "topology_mismatch"]
    
    for chunk in kb._chunks:
        if chunk.get("type") == "circuit_example":
            source = chunk.get("source", "").lower()
            for kw in excluded_keywords:
                assert kw not in source, f"QA Test Fixture '{source}' containing '{kw}' leaked into RAG chunks!"


def test_sha256_content_fingerprint():
    """Verifies that modifying a chunk text invalidates the SHA-256 manifest fingerprint."""
    kb = ElectronicsKnowledgeBase()
    h1 = kb._compute_chunks_hash()
    assert isinstance(h1, str) and len(h1) == 64
    
    # Modify a chunk in memory
    kb._chunks[0]["text"] += " __TAMPERED__"
    h2 = kb._compute_chunks_hash()
    
    assert h1 != h2, "SHA-256 content fingerprint did not change after chunk tampering!"
