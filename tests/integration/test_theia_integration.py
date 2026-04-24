"""
THEIA Integration Tests

验证 THEIA 引擎正确集成到 SiliconInfant 的决策流程中:
- THEIA 启用时，act() 会调用物理直觉验证
- THEIA 的 verdict 影响最终 action_payload 中的 confidence
- THEIA 统计正确记录到 get_status()
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.infant.engines.engine_theia import THEIAEngine, THEIAIntuitionResult


@pytest.fixture
def infant_with_theia(tmp_path: Path) -> SiliconInfant:
    """Create an infant with THEIA enabled."""
    config = {
        "theia_enabled": True,
        "theia_model_path": str(tmp_path / "theia_model.pt"),
        "theia_probe_lambda": 0.5,
    }
    # Create dummy model file
    from cosmic_mycelium.common.theia_model import THEIA as THEIAModel
    import torch

    model = THEIAModel(hidden_dim=64)
    for param in model.parameters():
        if param.dim() > 1:
            torch.nn.init.xavier_uniform_(param)
        else:
            torch.nn.init.zeros_(param)
    model.eval()
    torch.save(model.state_dict(), config["theia_model_path"])

    infant = SiliconInfant(infant_id="test-theia-infant", config=config)
    return infant


class TestTHEIAIntegration:
    """Integration tests for THEIA in SiliconInfant."""

    def test_theia_initialized_when_enabled(self, infant_with_theia: SiliconInfant):
        """THEIA engine is attached to infant when enabled."""
        assert infant_with_theia.theia is not None
        assert isinstance(infant_with_theia.theia, THEIAEngine)

    def test_theia_not_initialized_when_disabled(self, tmp_path: Path):
        """THEIA engine is None when disabled."""
        config = {"theia_enabled": False}
        infant = SiliconInfant(infant_id="no-theia", config=config)
        assert infant.theia is None

    def test_act_calls_theia_when_enabled(self, infant_with_theia: SiliconInfant):
        """act() invokes THEIA intuition during decision."""
        # Mock THEIA to return known verdict
        call_log = []

        def mock_intuit(physical_data, **kwargs):
            call_log.append(physical_data)
            return THEIAIntuitionResult(
                verdict=1,
                confidence=0.9,
                inference_time_ms=1.0,
            )

        infant_with_theia.theia.intuit = mock_intuit

        # Mock explorer.plan to return a valid plan (bypass slime explorer randomness)
        infant_with_theia.explorer.plan = lambda *a, **kw: ({"path": ["adjust"], "quality": 0.9}, 0.9)

        # Build a perception that passes initial checks
        perception = {
            "timestamp": 1234567890.0,
            "physical": {"q": 0.5, "p": 0.3},
            "sensors": {"vibration": 0.1, "temperature": 22.0, "spectrum_power": 1.0},
            "external": {},
        }
        predicted = {"q": 0.6, "p": 0.4}
        confidence = 0.8  # Above suspend threshold

        packet = infant_with_theia.act(perception, predicted, confidence)

        # THEIA should have been called
        assert len(call_log) == 1
        assert "a" in call_log[0] and "b" in call_log[0]

        # Packet should reflect THEIA-adjusted confidence
        assert packet is not None
        returned_conf = packet.value_payload["confidence"]
        # verdict=1 should increase confidence: 0.9 + 0.1*0.9 = 0.99 (capped at 1.0)
        expected = min(1.0, 0.9 + 0.1 * 0.9)
        assert abs(returned_conf - expected) < 1e-6

    def test_theia_negative_verdict_lowers_confidence(self, infant_with_theia: SiliconInfant):
        """THEIA verdict=0 (False) reduces plan confidence."""
        # This test would require patching THEIA before act()
        # For brevity, we verify the logic in _apply_theia_intuition directly
        infant = infant_with_theia

        # Create perception
        perception = {
            "physical": {"q": 0.5, "p": 0.3},
        }
        plan = {"path": ["adjust"], "quality": 0.8}
        plan_conf = 0.8

        # Mock THEIA to return verdict=0
        def mock_intuit(physical_data):
            return THEIAIntuitionResult(verdict=0, confidence=0.85, inference_time_ms=1.0)
        infant.theia.intuit = mock_intuit

        adjusted = infant._apply_theia_intuition(perception, plan, plan_conf)

        # Should be reduced: 0.8 - 0.3 * 0.85 = 0.8 - 0.255 = 0.545
        expected = max(0.0, 0.8 - 0.3 * 0.85)
        assert abs(adjusted - expected) < 1e-6

    def test_theia_unknown_verdict_slightly_lowers_confidence(self, infant_with_theia: SiliconInfant):
        """THEIA verdict=2 (Unknown) slightly reduces confidence."""
        infant = infant_with_theia

        def mock_intuit(physical_data):
            return THEIAIntuitionResult(verdict=2, confidence=0.6, inference_time_ms=1.0)

        infant.theia.intuit = mock_intuit

        adjusted = infant._apply_theia_intuition(
            {"physical": {"q": 0, "p": 0}},
            {"path": []},
            0.7,
        )
        expected = max(0.0, 0.7 - 0.1)
        assert abs(adjusted - expected) < 1e-6

    def test_theia_exception_does_not_crash_act(self, infant_with_theia: SiliconInfant):
        """THEIA errors are caught and act() continues with original confidence."""
        infant = infant_with_theia

        def failing_intuit(physical_data):
            raise RuntimeError("Model error")

        infant.theia.intuit = failing_intuit

        perception = {
            "physical": {"q": 0.5, "p": 0.3},
            "sensors": {"vibration": 0.1, "temperature": 22.0},
        }
        # Mock explorer.plan to return a valid plan
        infant.explorer.plan = lambda *a, **kw: ({"path": ["x"], "quality": 0.9}, 0.8)

        # act() should not raise
        packet = infant.act(perception, {"q": 0.6, "p": 0.4}, confidence=0.5)
        assert packet is not None
        # Confidence should equal plan_conf (THEIA error fallback, no adjustment)
        assert packet.value_payload["confidence"] == 0.8

    def test_theia_stats_in_status(self, infant_with_theia: SiliconInfant):
        """THEIA stats appear in get_status()."""
        infant = infant_with_theia
        # Run a few intuitions
        infant.theia.intuit({"a": 1.0, "b": 1.0})
        infant.theia.intuit({"a": 2.0, "b": 0.5})

        status = infant.get_status()
        assert "theia" in status
        assert status["theia"]["inference_count"] == 2
        assert status["theia"]["avg_inference_time_ms"] > 0.0

    def test_theia_disabled_does_not_affect_act(self, tmp_path: Path):
        """When THEIA disabled, act proceeds normally without THEIA adjustment."""
        config = {"theia_enabled": False}
        infant = SiliconInfant(infant_id="no-theia", config=config)

        assert infant.theia is None

        # Mock explorer.plan to return a valid plan with known confidence
        infant.explorer.plan = lambda *a, **kw: ({"path": ["x"], "quality": 0.9}, 0.8)

        perception = {
            "physical": {"q": 0.5, "p": 0.3},
            "sensors": {"vibration": 0.1, "temperature": 22.0},
        }
        packet = infant.act(perception, {"q": 0.6, "p": 0.4}, confidence=0.5)

        assert packet is not None
        # Confidence should equal plan_conf (0.8), unchanged by THEIA
        assert packet.value_payload["confidence"] == 0.8
