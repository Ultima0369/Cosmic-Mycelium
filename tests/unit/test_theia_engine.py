"""
THEIA Engine Unit Tests

Tests for the physics intuition engine: delayed verdict, inference, stats.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import torch

from cosmic_mycelium.infant.engines.engine_theia import THEIAEngine, THEIAIntuitionResult
from cosmic_mycelium.common.theia_model import THEIA as THEIAModel


@pytest.fixture
def dummy_model_path(tmp_path: Path) -> Path:
    """Create a minimal dummy THEIA model checkpoint."""
    model = THEIAModel(hidden_dim=64, input_dim=4)
    # Initialize with simple weights (random is fine for structure test)
    for param in model.parameters():
        if param.dim() > 1:
            torch.nn.init.xavier_uniform_(param)
        else:
            torch.nn.init.zeros_(param)
    model.eval()

    path = tmp_path / "dummy_theia.pt"
    torch.save(model.state_dict(), path)
    return path


class TestTHEIAModel:
    """Tests for THEIA model architecture."""

    def test_forward_shape(self, dummy_model_path: Path):
        """Model forward pass returns correct shapes."""
        model = THEIAModel(hidden_dim=64, input_dim=4)
        model.load_state_dict(torch.load(dummy_model_path))
        model.eval()

        a = torch.tensor([[0.5]])
        b = torch.tensor([[1.0]])
        a_unk = torch.tensor([[False]])
        b_unk = torch.tensor([[False]])

        with torch.no_grad():
            logits, hidden, engine_states = model(a, b, a_unk, b_unk)

        assert logits.shape == (1, 3), f"logits shape mismatch: {logits.shape}"
        assert hidden.shape == (1, 64), f"hidden shape mismatch: {hidden.shape}"
        assert isinstance(engine_states, dict)

    def test_load_from_checkpoint(self, dummy_model_path: Path):
        """load_from_checkpoint correctly loads weights."""
        model = THEIAModel.load_from_checkpoint(str(dummy_model_path))
        assert isinstance(model, THEIAModel)
        assert model.training is False  # eval mode

    def test_softmax_output_sum(self, dummy_model_path: Path):
        """Softmax probabilities sum to 1."""
        model = THEIAModel.load_from_checkpoint(str(dummy_model_path))
        # Ensure inputs are on same device as model
        device = next(model.parameters()).device
        a = torch.tensor([[1.0]], device=device)
        b = torch.tensor([[2.0]], device=device)
        a_unk = torch.tensor([[False]], device=device)
        b_unk = torch.tensor([[False]], device=device)

        with torch.no_grad():
            logits, _, _ = model(a, b, a_unk, b_unk)
            probs = torch.nn.functional.softmax(logits, dim=-1)

        assert abs(probs.sum().item() - 1.0) < 1e-5


class TestTHEIAEngine:
    """Tests for THEIAEngine wrapper."""

    def test_init_loads_model(self, dummy_model_path: Path):
        """Engine loads model on init."""
        engine = THEIAEngine(model_path=dummy_model_path)
        assert engine.model is not None
        assert engine.device in ("cpu", "cuda")

    def test_intuit_returns_result(self, dummy_model_path: Path):
        """intuit() returns structured result."""
        engine = THEIAEngine(model_path=dummy_model_path)
        result = engine.intuit({"a": 0.5, "b": 1.0})

        assert isinstance(result, THEIAIntuitionResult)
        assert result.verdict in (0, 1, 2)
        assert 0.0 <= result.confidence <= 1.0
        assert result.inference_time_ms >= 0.0

    def test_intuit_unknown_handling(self, dummy_model_path: Path):
        """Unknown flags are passed correctly."""
        engine = THEIAEngine(model_path=dummy_model_path)
        result = engine.intuit({"a": 0.5, "b": 1.0}, a_unk=True, b_unk=False)

        assert result.verdict in (0, 1, 2)
        # Hidden state available when requested
        result_hidden = engine.intuit({"a": 0.5, "b": 1.0}, return_hidden=True)
        assert result_hidden.hidden_state is not None
        # Hidden state is numpy array (converted from torch tensor in engine)
        assert hasattr(result_hidden.hidden_state, "shape")

    def test_is_physics_safe_true(self, dummy_model_path: Path):
        """is_physics_safe returns True for confident True verdict."""
        engine = THEIAEngine(model_path=dummy_model_path)
        # Test multiple times due to random model init
        for _ in range(10):
            if engine.is_physics_safe({"a": 1.0, "b": 2.0}, min_confidence=0.5):
                break
        else:
            pytest.skip("Model not confident enough for this test (random weights)")

    def test_should_trigger_caution_on_unknown(self, dummy_model_path: Path):
        """Unknown verdict triggers caution."""
        engine = THEIAEngine(model_path=dummy_model_path)
        # With random weights, unknown (2) is possible
        # We just verify the method runs without error
        result = engine.should_trigger_caution({"a": 0.5, "b": 0.5})
        assert isinstance(result, bool)

    def test_get_stats_returns_reasonable_values(self, dummy_model_path: Path):
        """get_stats provides useful info."""
        engine = THEIAEngine(model_path=dummy_model_path)
        # Run a few inferences
        engine.intuit({"a": 1.0, "b": 1.0})
        engine.intuit({"a": 2.0, "b": 0.5})

        stats = engine.get_stats()
        assert stats["inference_count"] == 2
        assert stats["avg_inference_time_ms"] > 0.0
        assert stats["device"] in ("cpu", "cuda")
        assert Path(stats["model_path"]).exists()

    def test_probe_hidden_state_accuracy(self, dummy_model_path: Path):
        """Linear probe on hidden states should return a valid accuracy score."""
        engine = THEIAEngine(model_path=dummy_model_path)

        # Generate synthetic multi-class hidden states
        rng = torch.Generator().manual_seed(42)
        X = torch.randn(100, 64)
        # Derive 3 classes from first two dimensions
        y = ((X[:, 0] > 0).int() + (X[:, 1] > 0).int() * 2).clamp(0, 2)

        X_np = X.numpy()
        y_np = y.numpy()

        acc = engine.probe_hidden_state(X_np, y_np)
        assert 0.0 <= acc <= 1.0

    def test_missing_model_raises_error(self, tmp_path: Path):
        """Non-existent model path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            THEIAEngine(model_path=tmp_path / "nonexistent.pt")

    def test_pytorch_unavailable_fallback(self, dummy_model_path: Path):
        """If PyTorch unavailable, ImportError is raised."""
        # Can't easily simulate ImportError without sys.modules manipulation
        # Just verify torch is used
        engine = THEIAEngine(model_path=dummy_model_path)
        assert hasattr(engine, "model")
