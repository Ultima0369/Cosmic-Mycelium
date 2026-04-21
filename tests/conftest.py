"""
Cosmic Mycelium — Pytest Configuration and Shared Fixtures
Factory-grade test infrastructure with complete type safety.
"""

from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from _pytest.config import Config
from _pytest.nodes import Item

# Set default asyncio scope
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config: Config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (multi-component)"
    )
    config.addinivalue_line(
        "markers", "physics: Physics validation tests (energy conservation)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests that take >1s"
    )
    config.addinivalue_line(
        "markers", "performance: Performance benchmarks"
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]):
    """Auto-tag tests based on file path."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "physics" in str(item.fspath):
            item.add_marker(pytest.mark.physics)


# ============================================================================
# Fixtures: Shared Test Utilities
# ============================================================================

@pytest.fixture
def infant_id() -> str:
    """Generate a unique infant ID for each test."""
    return f"test-infant-{random.randint(1000, 9999)}"


@pytest.fixture
def hic_config() -> dict:
    """Default HIC configuration for tests."""
    return {
        "energy_max": 100.0,
        "contract_duration": 0.055,
        "diffuse_duration": 0.005,
        "suspend_duration": 0.1,  # Fast for tests
        "recovery_energy": 60.0,
        "recovery_rate": 0.5,
    }


@pytest.fixture
def hic(hic_config: dict):
    """Create a fresh HIC instance for each test."""
    from cosmic_mycelium.infant.hic import HIC, HICConfig, BreathState
    import time

    config = HICConfig(**hic_config)
    h = HIC(config=config, name="test-hic")

    # Initialize to known state
    h._energy = 100.0
    h._state = BreathState.CONTRACT
    h._last_switch = time.monotonic()
    h.total_cycles = 0
    h.suspend_count = 0
    h.adaptation_count = 0
    h.value_vector = {
        "self_preservation": 1.0,
        "mutual_benefit": 1.0,
        "curiosity": 0.7,
        "caution": 0.5,
    }

    return h


@pytest.fixture
def sympnet_config() -> dict:
    """Default SympNet configuration for tests."""
    return {
        "mass": 1.0,
        "spring_constant": 1.0,
        "damping": 0.0,
    }


@pytest.fixture
def sympnet(sympnet_config: dict):
    """Create a fresh SympNet instance for each test."""
    from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
    s = SympNetEngine(**sympnet_config)
    # Clear history to ensure test isolation
    s._history = []
    s._integration_error = 0.0
    return s


@pytest.fixture(autouse=True)
def reset_sympnet_history(sympnet):
    """Automatically clear SympNet history before and after every physics test."""
    # Before test
    sympnet._history = []
    sympnet._integration_error = 0.0
    yield
    # After test
    sympnet._history = []
    sympnet._integration_error = 0.0


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test data."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an asyncio event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def physics_tolerance() -> float:
    """
    Physics anchor tolerance.
    The sacred threshold: energy drift must not exceed 0.1% (0.001).
    """
    return 0.001


@pytest.fixture
def mock_time(monkeypatch):
    """Mock time.monotonic() for deterministic HIC testing."""
    import time as real_time
    start = real_time.monotonic()
    current = [start]

    def fake_monotonic():
        return current[0]

    def advance(seconds: float):
        current[0] += seconds

    monkeypatch.setattr(real_time, "monotonic", fake_monotonic)
    return type("MockTime", (), {"now": fake_monotonic, "advance": advance})


# ============================================================================
# Test Helpers
# ============================================================================

def assert_energy_conserved(
    initial_energy: float,
    final_energy: float,
    tolerance: float = 0.001,
) -> None:
    """Assert that energy is conserved within tolerance."""
    drift = abs(final_energy - initial_energy) / max(initial_energy, 1e-9)
    assert drift < tolerance, (
        f"Energy drift {drift:.6f} exceeds tolerance {tolerance:.6f}. "
        f"Initial: {initial_energy:.6f}, Final: {final_energy:.6f}"
    )


def assert_breath_state_valid(state: str) -> None:
    """Assert that breath state is one of the valid states."""
    assert state in ("contract", "diffuse", "suspend"), (
        f"Invalid breath state: {state}"
    )


def assert_hypothesis_compatible(function):
    """
    Decorator to mark tests that are compatible with hypothesis property testing.
    These tests should be deterministic given the same random seed.
    """
    return function

