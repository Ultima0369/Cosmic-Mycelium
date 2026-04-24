"""
BitNet Adapter Unit Tests

Tests energy gating, prompt building, result parsing, and integration
with HIC energy accounting.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cosmic_mycelium.infant.engines.engine_bitnet import (
    BitNetAdapter,
    BitNetReasoningResult,
)
from cosmic_mycelium.infant.hic import HIC, HICConfig


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def hic():
    return HIC(config=HICConfig(energy_max=100.0))


@pytest.fixture
def adapter(hic):
    """BitNetAdapter with mocked llama_cpp backend."""
    adapter = BitNetAdapter(hic=hic)
    # Force available=True and set up llama mock
    adapter.available = True
    adapter._embedding_dim = 2560
    return adapter


# ── Initialization ───────────────────────────────────────────────────────

class TestBitNetAdapterInitialization:
    """Tests for BitNetAdapter construction and configuration."""

    def test_adapter_requires_hic(self):
        """BitNetAdapter raises ValueError if HIC is None."""
        with pytest.raises(ValueError, match="HIC instance required"):
            BitNetAdapter(hic=None)

    def test_default_model_path(self, hic):
        """Default model path points to BitNet GGUF file."""
        adapter = BitNetAdapter(hic=hic)
        assert "Bitnet/models/bitnet-2b-q4_0.gguf" in adapter.model_path

    def test_custom_model_path(self, hic):
        """Custom model path can be provided."""
        adapter = BitNetAdapter(hic=hic, model_path="/custom/model.gguf")
        assert adapter.model_path == "/custom/model.gguf"

    def test_energy_threshold_default(self, hic):
        """Default energy threshold is 70.0."""
        adapter = BitNetAdapter(hic=hic)
        assert adapter.energy_threshold == 70.0

    def test_confidence_threshold_default(self, hic):
        """Default confidence threshold is 0.7."""
        adapter = BitNetAdapter(hic=hic)
        assert adapter.confidence_threshold == 0.7

    def test_custom_thresholds(self, hic):
        """Custom thresholds are respected."""
        adapter = BitNetAdapter(
            hic=hic,
            energy_threshold=80.0,
            confidence_threshold=0.5,
        )
        assert adapter.energy_threshold == 80.0
        assert adapter.confidence_threshold == 0.5


# ── Energy Gate Logic ─────────────────────────────────────────────────────

class TestShouldInvoke:
    """Tests for the energy-confidence gate logic."""

    def test_should_not_invoke_when_not_available(self, hic):
        """If BitNet unavailable, should_invoke returns False."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = False
        assert adapter.should_invoke(energy=80.0, confidence=0.3) is False

    def test_should_not_invoke_when_energy_low(self, hic):
        """Energy below threshold blocks invocation."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True
        hic._energy = 50.0  # Below 70 threshold
        assert adapter.should_invoke(energy=50.0, confidence=0.3) is False

    def test_should_not_invoke_when_confidence_high(self, hic):
        """High confidence skips BitNet (already certain)."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True
        assert adapter.should_invoke(energy=80.0, confidence=0.9) is False

    def test_should_invoke_when_energy_ok_and_confidence_low(self, hic):
        """Energy sufficient AND confidence low → invoke."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True
        assert adapter.should_invoke(energy=80.0, confidence=0.3) is True

    def test_should_invoke_explicit_query_override(self, hic):
        """Explicit query overrides confidence check."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True
        # Even with high confidence, explicit query triggers invocation
        assert adapter.should_invoke(energy=80.0, confidence=0.95, explicit_query=True) is True

    def test_should_invoke_energy_edge_case(self, hic):
        """Exactly at threshold should invoke."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True
        assert adapter.should_invoke(energy=70.0, confidence=0.5) is True

    def test_should_not_invoke_below_threshold(self, hic):
        """Just below threshold should not invoke."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True
        assert adapter.should_invoke(energy=69.9, confidence=0.5) is False


# ── Prompt Construction ────────────────────────────────────────────────────

class TestBuildPrompt:
    """Tests for prompt construction from perception dict."""

    def test_build_prompt_basic_structure(self, hic):
        """Prompt includes basic silicon node identity and sensor readings."""
        adapter = BitNetAdapter(hic=hic)
        perception = {
            "physical": {"q": 0.5, "p": -0.2},
            "sensors": {
                "vibration": 0.15,
                "temperature": 25.5,
                "spectrum_power": 0.8,
            },
        }
        prompt = adapter._build_prompt(perception)

        assert "silicon-based lifeform" in prompt
        assert "q=0.500" in prompt
        assert "p=-0.200" in prompt
        assert "vibration=0.15" in prompt
        assert "25.5°C" in prompt
        assert "spectrum_power=0.8" in prompt

    def test_build_prompt_with_semantic_embedding(self, hic):
        """Prompt includes semantic embedding metadata."""
        adapter = BitNetAdapter(hic=hic)
        perception = {
            "physical": {"q": 0.0, "p": 0.0},
            "sensors": {"vibration": 0.0, "temperature": 22.0, "spectrum_power": 1.0},
            "semantic_embedding": np.random.randn(16),
        }
        prompt = adapter._build_prompt(perception)
        assert "Semantic embedding shape" in prompt

    def test_build_prompt_with_context_question(self, hic):
        """Prompt includes peer question when present in context."""
        adapter = BitNetAdapter(hic=hic)
        perception = {"physical": {"q": 0, "p": 0}, "sensors": {}}
        context = {"question": "Is that vibration from machinery?"}
        prompt = adapter._build_prompt(perception, context)
        assert "Question from peer:" in prompt
        assert "vibration from machinery" in prompt

    def test_build_prompt_without_semantic(self, hic):
        """Prompt works when semantic_embedding is absent."""
        adapter = BitNetAdapter(hic=hic)
        perception = {
            "physical": {"q": 0.1, "p": 0.2},
            "sensors": {"vibration": 0.05},
        }
        # Should not raise
        prompt = adapter._build_prompt(perception)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ── Confidence Estimation ─────────────────────────────────────────────────

class TestEstimateConfidence:
    """Tests for confidence estimation from generated text."""

    def test_high_confidence_certainty_markers(self, hic):
        """Text with certainty words yields high confidence."""
        adapter = BitNetAdapter(hic=hic)
        text = "The situation is clearly stable and definitely normal."
        confidence = adapter._estimate_confidence(text)
        assert confidence > 0.7

    def test_low_confidence_uncertainty_markers(self, hic):
        """Text with uncertainty words yields low confidence."""
        adapter = BitNetAdapter(hic=hic)
        text = "Maybe the vibration is uncertain. Perhaps we should wait."
        confidence = adapter._estimate_confidence(text)
        assert confidence < 0.5

    def test_neutral_text_default_confidence(self, hic):
        """Text without markers gives default ~0.7."""
        adapter = BitNetAdapter(hic=hic)
        text = "The temperature is within normal range."
        confidence = adapter._estimate_confidence(text)
        assert 0.6 < confidence < 0.8

    def test_suspend_marker_lowers_confidence(self, hic):
        """SUSPEND-related words lower confidence (cautious alignment)."""
        adapter = BitNetAdapter(hic=hic)
        text = "We should suspend judgment and wait for more data."
        confidence = adapter._estimate_confidence(text)
        # uncertainty markers penalize -0.15 each
        assert confidence < 0.7


# ── Energy Accounting ──────────────────────────────────────────────────────

class TestEnergyCostCalculation:
    """Tests for energy accounting."""

    def test_base_cost_constant(self, hic):
        """Base cost is the ENERGY_COST_BASE class constant."""
        assert BitNetAdapter.ENERGY_COST_BASE == 2.0

    def test_token_cost_factor_constant(self, hic):
        """Token cost factor is the TOKEN_COST_FACTOR class constant."""
        assert BitNetAdapter.TOKEN_COST_FACTOR == 0.01

    def test_calculate_energy_cost_formula(self, hic):
        """_calculate_energy_cost uses base + tokens * factor."""
        adapter = BitNetAdapter(hic=hic)
        cost = adapter._calculate_energy_cost(tokens_used=50)
        expected = BitNetAdapter.ENERGY_COST_BASE + 50 * BitNetAdapter.TOKEN_COST_FACTOR
        assert cost == expected

    def test_energy_deducted_from_hic(self, hic):
        """Energy is deducted from HIC after successful reasoning."""
        adapter = BitNetAdapter(hic=hic, energy_threshold=50.0)  # Lower threshold
        hic._energy = 80.0  # Ensure above threshold
        initial_energy = hic.energy
        # Force adapter state to "ready"
        adapter.available = True
        adapter._embedding_dim = 2560
        mock_llama = MagicMock()
        mock_llama.tokenize.return_value = [1, 2, 3]
        mock_llama.generate.return_value = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        mock_llama.detokenize.return_value = b"Analysis complete."
        mock_llama.token_eos.return_value = 0
        adapter._llama = mock_llama

        perception = {
            "physical": {"q": 0, "p": 0},
            "sensors": {"vibration": 0, "temperature": 22, "spectrum_power": 1},
        }
        result = adapter.reason(perception)

        assert result is not None
        # Energy should have decreased by at least base cost
        assert hic.energy < initial_energy
        assert hic.energy >= 0  # Never negative

    def test_energy_floor_at_zero(self, hic):
        """Energy never goes below zero even with high cost."""
        hic._energy = 5.0  # Just above zero
        # Use low energy threshold so gate passes, high base cost to exhaust energy
        adapter = BitNetAdapter(
            hic=hic,
            energy_threshold=1.0,  # Low threshold to allow invocation
            energy_cost_base=10.0,  # High base cost
            token_cost_factor=0.0,
        )
        adapter.available = True
        adapter._embedding_dim = 2560
        mock_llama = MagicMock()
        mock_llama.tokenize.return_value = [1]
        mock_llama.generate.return_value = [1, 2, 3]
        mock_llama.detokenize.return_value = b"test"
        mock_llama.token_eos.return_value = 0
        adapter._llama = mock_llama

        perception = {
            "physical": {"q": 0, "p": 0},
            "sensors": {"vibration": 0, "temperature": 22, "spectrum_power": 1},
        }
        adapter.reason(perception)

        assert hic.energy == 0.0


# ── Main reason() Method ────────────────────────────────────────────────────

class TestReasonMethod:
    """Tests for the main reason() method behavior."""

    def test_reason_returns_none_when_unavailable(self, hic):
        """reason() returns None if model not loaded."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = False
        perception = {"physical": {"q": 0, "p": 0}, "sensors": {}}
        result = adapter.reason(perception)
        assert result is None

    def test_reason_skipped_when_energy_low(self, hic):
        """reason() returns None when energy below threshold."""
        adapter = BitNetAdapter(hic=hic)
        adapter.available = True  # Even if available, energy gate fires first
        hic._energy = 50.0  # Below 70
        perception = {"physical": {"q": 0, "p": 0}, "sensors": {}}
        result = adapter.reason(perception)
        assert result is None
        assert adapter.last_error == "Energy 50.0 < 70.0 threshold"

    def test_reason_successful_returns_result(self, hic):
        """reason() returns BitNetReasoningResult on success."""
        adapter = BitNetAdapter(hic=hic)
        hic._energy = 80.0  # Sufficient energy
        adapter.available = True
        adapter._embedding_dim = 2560
        mock_llama = MagicMock()
        mock_llama.tokenize.return_value = [1, 2, 3]
        mock_llama.generate.return_value = [1, 2, 3, 4, 5]
        mock_llama.detokenize.return_value = b"Situation normal. Proceed."
        mock_llama.token_eos.return_value = 0
        adapter._llama = mock_llama

        perception = {
            "physical": {"q": 0.5, "p": -0.3},
            "sensors": {"vibration": 0.1, "temperature": 23.5, "spectrum_power": 1.2},
        }
        result = adapter.reason(perception)

        assert result is not None
        assert isinstance(result, BitNetReasoningResult)
        assert "Situation normal" in result.answer
        assert 0.0 <= result.confidence <= 1.0
        assert result.tokens_used > 0
        assert result.energy_cost > BitNetAdapter.ENERGY_COST_BASE

    def test_reason_tracks_statistics(self, hic):
        """Statistics updated after each successful invocation."""
        adapter = BitNetAdapter(hic=hic)
        hic._energy = 80.0
        adapter.available = True
        adapter._embedding_dim = 2560
        mock_llama = MagicMock()
        mock_llama.tokenize.return_value = [1]
        mock_llama.generate.return_value = [1, 2, 3]
        mock_llama.detokenize.return_value = b"Test."
        mock_llama.token_eos.return_value = 0
        adapter._llama = mock_llama

        perception = {
            "physical": {"q": 0, "p": 0},
            "sensors": {"vibration": 0, "temperature": 22, "spectrum_power": 1},
        }
        adapter.reason(perception)

        assert adapter.total_invocations == 1
        assert adapter.total_energy_spent > 0
        assert adapter.last_inference_time > 0

    def test_reason_handles_exception_gracefully(self, hic):
        """Exceptions during inference return None and set last_error."""
        adapter = BitNetAdapter(hic=hic)
        hic._energy = 80.0
        adapter.available = True
        adapter._embedding_dim = 2560
        mock_llama = MagicMock()
        mock_llama.tokenize.side_effect = RuntimeError("tokenizer failed")
        adapter._llama = mock_llama

        perception = {
            "physical": {"q": 0, "p": 0},
            "sensors": {"vibration": 0, "temperature": 22, "spectrum_power": 1},
        }
        result = adapter.reason(perception)

        assert result is None
        assert "tokenizer failed" in adapter.last_error
        assert adapter.total_invocations == 0  # Not counted on failure


# ── Monitoring Stats ────────────────────────────────────────────────────────

class TestGetStats:
    """Tests for get_stats() monitoring output."""

    def test_get_stats_returns_expected_keys(self, hic):
        """Stats dict contains all expected monitoring keys."""
        adapter = BitNetAdapter(hic=hic)
        stats = adapter.get_stats()

        expected_keys = {
            "available", "init_error", "total_invocations", "total_energy_spent",
            "last_inference_time", "last_error", "energy_threshold",
            "confidence_threshold", "model_path", "embedding_dim",
        }
        assert expected_keys.issubset(stats.keys())

    def test_get_stats_available_flag_correct(self, hic):
        """available flag reflects actual model load state."""
        adapter = BitNetAdapter(hic=hic)
        stats = adapter.get_stats()
        assert isinstance(stats["available"], bool)

    def test_get_stats_includes_thresholds(self, hic):
        """Thresholds are reported in stats."""
        adapter = BitNetAdapter(hic=hic, energy_threshold=85.0, confidence_threshold=0.5)
        stats = adapter.get_stats()
        assert stats["energy_threshold"] == 85.0
        assert stats["confidence_threshold"] == 0.5


# ── BitNetReasoningResult ──────────────────────────────────────────────────

class TestBitNetReasoningResult:
    """Tests for the BitNetReasoningResult dataclass."""

    def test_default_construction(self):
        """Result can be constructed with required fields."""
        result = BitNetReasoningResult(
            answer="Test answer",
            confidence=0.85,
            tokens_used=42,
            energy_cost=2.5,
        )
        assert result.answer == "Test answer"
        assert result.confidence == 0.85
        assert result.tokens_used == 42
        assert result.energy_cost == 2.5
        assert result.raw_output is None
        assert result.metadata == {}

    def test_full_construction(self):
        """Result supports optional raw_output and metadata."""
        result = BitNetReasoningResult(
            answer="Test",
            confidence=0.6,
            tokens_used=10,
            energy_cost=2.1,
            raw_output="Full raw text here",
            metadata={"prompt_tokens": 5, "some_key": "value"},
        )
        assert result.raw_output == "Full raw text here"
        assert result.metadata["some_key"] == "value"
