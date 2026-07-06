"""Retrieval quality tests for hybrid RAG (TF-IDF + optional dense)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _top_results(kb, query: str, chunk_type=None, top_k=5):
    return kb.query(query, top_k=top_k, chunk_type=chunk_type)


def test_rag_usb_retrieval():
    from knowledge.rag_engine import ElectronicsKnowledgeBase

    kb = ElectronicsKnowledgeBase()
    results = _top_results(kb, "USB differential impedance devboard", chunk_type="circuit_example")
    sources = [r["source"] for r in results]
    print(f"USB query sources: {sources[:3]}")
    usb_hits = [
        r for r in results
        if any(k in (r["source"] + r.get("excerpt", "")).lower()
               for k in ("usb", "usb_dp", "recovery_usb", "differential"))
    ]
    assert usb_hits, f"No USB training hit: {sources[:5]}"


def test_rag_esp32_component():
    from knowledge.rag_engine import ElectronicsKnowledgeBase

    kb = ElectronicsKnowledgeBase()
    sources = [r["source"] for r in _top_results(kb, "ESP32 decoupling capacitor WiFi", top_k=5)]
    print(f"ESP32 query sources: {sources[:3]}")
    assert any("ESP32" in s or "esp32" in s.lower() for s in sources), sources


def test_rag_ipc_clearance():
    from knowledge.rag_engine import ElectronicsKnowledgeBase

    kb = ElectronicsKnowledgeBase()
    sources = [r["source"] for r in _top_results(kb, "clearance 48V external uncoated PCB", top_k=3)]
    print(f"IPC query sources: {sources[:3]}")
    assert any("IPC" in s for s in sources), sources


def test_rag_design_intent_retrieval():
    from knowledge.rag_engine import ElectronicsKnowledgeBase

    kb = ElectronicsKnowledgeBase()
    results = _top_results(
        kb,
        "RLC RF pulse receiver induction LED induccion",
        chunk_type="circuit_example",
    )
    top = results[0]
    print(f"Design-intent query top source: {top['source']}")
    print(f"Design-intent excerpt: {top.get('excerpt', '')[:160]}")
    assert "sample_20260501_064720_181247" in top["source"], results[:3]
    excerpt = top.get("excerpt", "").lower()
    assert "design_intent:" in excerpt
    assert any(k in excerpt for k in ("rf", "induccion", "receptor", "pulso"))


def test_rf_usb_diff_pair():
    from core.rf_tools import usb_diff_pair_dimensions, differential_microstrip_impedance

    dims = usb_diff_pair_dimensions(Zdiff_target=90.0, h_mm=1.6, er=4.4)
    print(f"USB diff pair: W={dims.get('W_mm')} S={dims.get('S_mm')} Z={dims.get('Zdiff')}")
    assert dims.get("W_mm", 0) > 0
    assert dims.get("S_mm", 0) > 0
    assert abs(dims.get("Zdiff", 0) - 90) < 25

    r = differential_microstrip_impedance(dims["W_mm"], dims["S_mm"], 1.6, 4.4)
    assert 70 < r["Zdiff"] < 110


if __name__ == "__main__":
    tests = [
        test_rag_usb_retrieval,
        test_rag_esp32_component,
        test_rag_ipc_clearance,
        test_rag_design_intent_retrieval,
        test_rf_usb_diff_pair,
    ]
    passed = failed = 0
    for t in tests:
        print(f"--- {t.__name__} ---")
        try:
            t()
            passed += 1
            print("PASS\n")
        except Exception as e:
            failed += 1
            print(f"FAIL: {e}\n")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
