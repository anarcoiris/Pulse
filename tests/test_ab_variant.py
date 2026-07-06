"""Session 4b A/B variant toggle — prompt construction only (no LLM)."""

from knowledge.circuit_synthesizer import CircuitSynthesizer, _OBLIGATORIAS_UART_USB


def test_variant_a_includes_obligatorias_rules():
    synth = CircuitSynthesizer(ab_variant="a")
    assert "REGLAS UART / USB (OBLIGATORIAS)" in synth.base_system_prompt
    assert "Pines EN del ESP32 requieren pull-up 10k" in synth.base_system_prompt


def test_variant_b_omits_obligatorias_rules():
    synth = CircuitSynthesizer(ab_variant="b")
    assert "REGLAS UART / USB (OBLIGATORIAS)" not in synth.base_system_prompt
    assert _OBLIGATORIAS_UART_USB.strip() not in synth.base_system_prompt


def test_variant_defaults_to_a():
    synth = CircuitSynthesizer()
    assert synth.ab_variant == "a"
    assert "REGLAS UART / USB (OBLIGATORIAS)" in synth.base_system_prompt


def test_invalid_variant_falls_back_to_a():
    synth = CircuitSynthesizer(ab_variant="x")
    assert synth.ab_variant == "a"


def test_circuit_example_rag_top_k_by_variant():
    synth_a = CircuitSynthesizer(ab_variant="a")
    synth_b = CircuitSynthesizer(ab_variant="b")
    assert synth_a._circuit_example_rag_top_k() == 1
    assert synth_b._circuit_example_rag_top_k() == 4
