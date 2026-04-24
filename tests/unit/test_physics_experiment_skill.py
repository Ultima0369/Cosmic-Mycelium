"""
Unit tests for PhysicsExperimentSkill — THEIA physics engine wrapper.

TDD coverage:
- THEIAEngine lazy loading with fallback
- Safety verdict caching
- Caution trigger on unsafe/unknown physics
- Resource usage reporting
- Graceful degradation when PyTorch unavailable
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cosmic_mycelium.infant.skills.base import SkillContext
from cosmic_mycelium.infant.skills.physics.physics_experiment import PhysicsExperimentSkill


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def physics_skill():
    """Fresh skill instance for each test."""
    return PhysicsExperimentSkill()


# ---------------------------------------------------------------------------
# Test: Initialization & Protocol Compliance
# ---------------------------------------------------------------------------

class TestPhysicsExperimentSkillInit:
    """Tests for skill construction and lifecycle."""

    def test_skill_has_required_attributes(self, physics_skill):
        assert physics_skill.name == "physics_experiment"
        assert physics_skill.version == "1.0.0"
        assert physics_skill.dependencies == []  # no hard deps
        assert "physics" in physics_skill.description.lower()

    def test_initialize_no_external_requirements(self, physics_skill):
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        physics_skill.initialize(context)
        assert physics_skill._initialized is True

    def test_shutdown_clears_engine(self, physics_skill):
        physics_skill._engine = MagicMock()
        physics_skill.shutdown()
        assert physics_skill._engine is None
        assert physics_skill._initialized is False


# ---------------------------------------------------------------------------
# Test: can_activate gating
# ---------------------------------------------------------------------------

class TestPhysicsExperimentSkillActivation:
    """Tests for can_activate() gating."""

    def test_activate_requires_energy(self, physics_skill):
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=1.0)
        assert physics_skill.can_activate(context) is False

    def test_activate_requires_initialized(self, physics_skill):
        physics_skill._initialized = False
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=100)
        assert physics_skill.can_activate(context) is False

    def test_activate_success(self, physics_skill):
        physics_skill._initialized = True
        context = SkillContext(infant_id="test", cycle_count=0, energy_available=50)
        assert physics_skill.can_activate(context) is True


# ---------------------------------------------------------------------------
# Test: execute() with mocked engine
# ---------------------------------------------------------------------------

class TestPhysicsExperimentSkillExecution:
    """Tests for execute() with THEIA engine."""

    def test_execute_returns_safe_verdict(self, physics_skill):
        physics_skill._initialized = True
        mock_engine = MagicMock()
        mock_engine.intuit.return_value = MagicMock(
            verdict=1,
            confidence=0.92,
            inference_time_ms=2.5,
        )
        physics_skill._engine = mock_engine

        result = physics_skill.execute({"physical_data": {"a": 1.0, "b": 2.0}})

        assert result["verdict"] == 1
        assert result["confidence"] == pytest.approx(0.92, abs=0.01)
        assert result["status"] == "safe"
        assert result["energy_cost"] == pytest.approx(4.0, abs=0.5)

    def test_execute_returns_unsafe_when_verdict_false(self, physics_skill):
        physics_skill._initialized = True
        mock_engine = MagicMock()
        mock_engine.intuit.return_value = MagicMock(
            verdict=0,
            confidence=0.88,
            inference_time_ms=2.1,
        )
        physics_skill._engine = mock_engine

        result = physics_skill.execute({"physical_data": {"a": 1.0, "b": 2.0}})

        assert result["verdict"] == 0
        assert result["status"] == "unsafe"
        assert result["caution_triggered"] is True

    def test_execute_returns_unknown_when_confidence_low(self, physics_skill):
        physics_skill._initialized = True
        mock_engine = MagicMock()
        mock_engine.intuit.return_value = MagicMock(
            verdict=1,
            confidence=0.45,  # below threshold
            inference_time_ms=1.8,
        )
        physics_skill._engine = mock_engine

        result = physics_skill.execute({"physical_data": {"a": 1.0, "b": 2.0}})

        assert result["verdict"] == 1
        assert result["status"] == "uncertain"
        assert result["caution_triggered"] is True

    def test_execute_sets_caution_flag_in_hic(self, physics_skill):
        physics_skill._initialized = True
        physics_skill._engine = MagicMock()
        physics_skill._engine.intuit.return_value = MagicMock(
            verdict=0, confidence=0.9, inference_time_ms=2.0
        )
        physics_skill.hic = MagicMock()

        result = physics_skill.execute({"physical_data": {"a": 1.0, "b": 2.0}})

        physics_skill.hic.adjust_caution.assert_called_once_with(True)

    def test_execute_caches_recent_verdicts(self, physics_skill):
        physics_skill._initialized = True
        mock_engine = MagicMock()
        mock_engine.intuit.return_value = MagicMock(
            verdict=1, confidence=0.95, inference_time_ms=2.0
        )
        physics_skill._engine = mock_engine

        data = {"a": 1.0, "b": 2.0}

        # First call - should hit engine
        physics_skill.execute({"physical_data": data})
        assert mock_engine.intuit.call_count == 1

        # Second call with same data - should use cache
        result = physics_skill.execute({"physical_data": data})
        assert result["status"] == "safe"
        # Cache hit means engine not called again
        assert mock_engine.intuit.call_count == 1  # still 1, not 2

    def test_execute_handles_missing_physical_data(self, physics_skill):
        physics_skill._initialized = True
        physics_skill._engine = MagicMock()

        result = physics_skill.execute({})  # no physical_data

        assert result["status"] == "error"
        assert "missing" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Test: Graceful degradation when engine unavailable
# ---------------------------------------------------------------------------

class TestPhysicsExperimentSkillDegradation:
    """Tests for engine unavailability handling."""

    def test_execute_returns_degraded_when_engine_none(self, physics_skill):
        physics_skill._initialized = True
        physics_skill._engine = None

        result = physics_skill.execute({"physical_data": {"a": 1.0, "b": 2.0}})

        assert result["status"] == "degraded"
        assert result["verdict"] is None
        assert result["caution_triggered"] is True  # cautious default

    def test_execute_engine_exception_returns_degraded(self, physics_skill):
        physics_skill._initialized = True
        mock_engine = MagicMock()
        mock_engine.intuit.side_effect = RuntimeError("Torch OOM")
        physics_skill._engine = mock_engine

        result = physics_skill.execute({"physical_data": {"a": 1.0, "b": 2.0}})

        assert result["status"] == "degraded"
        assert "oom" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Test: get_resource_usage & get_status
# ---------------------------------------------------------------------------

class TestPhysicsExperimentSkillMonitoring:
    """Tests for resource reporting and status."""

    def test_get_resource_usage(self, physics_skill):
        usage = physics_skill.get_resource_usage()
        assert usage["energy_cost"] == pytest.approx(4.0, abs=0.5)
        assert usage["duration_s"] == pytest.approx(0.05, abs=0.02)
        assert usage["memory_mb"] == pytest.approx(50.0, abs=5.0)

    def test_get_status_initialized(self, physics_skill):
        physics_skill._initialized = True
        physics_skill._execution_count = 7
        status = physics_skill.get_status()
        assert status["name"] == "physics_experiment"
        assert status["initialized"] is True
        assert status["execution_count"] == 7
        assert "engine_ready" in status

    def test_get_status_degraded_when_no_engine(self, physics_skill):
        physics_skill._initialized = True
        physics_skill._engine = None
        status = physics_skill.get_status()
        assert status["engine_ready"] is False
