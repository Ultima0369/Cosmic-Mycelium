"""Integration tests for SiliconInfant save/load serialization."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cosmic_mycelium.infant.main import SiliconInfant


class TestSerialization:
    """Tests for save()/load()/to_dict()/from_dict() round-trip."""

    @pytest.fixture
    def infant(self) -> SiliconInfant:
        """Create a minimal infant for testing."""
        return SiliconInfant("test-serialize-001")

    @pytest.fixture
    def tmp_path(self) -> Path:
        """Temporary file path for save tests."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)

    def test_to_dict_includes_required_keys(self, infant: SiliconInfant) -> None:
        """to_dict() returns all expected top-level keys."""
        data = infant.to_dict()
        required = {"infant_id", "hic", "sympnet", "memory", "brain", "interface"}
        missing = required - set(data.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_to_dict_his_infant_id(self, infant: SiliconInfant) -> None:
        """to_dict() contains the correct infant_id."""
        data = infant.to_dict()
        assert data["infant_id"] == "test-serialize-001"

    def test_to_dict_his_hic_energy(self, infant: SiliconInfant) -> None:
        """to_dict() includes HIC energy."""
        data = infant.to_dict()
        assert "energy" in data["hic"]
        assert data["hic"]["energy"] > 0

    def test_save_creates_file(self, infant: SiliconInfant, tmp_path: Path) -> None:
        """save() creates a JSON file on disk."""
        infant.save(tmp_path)
        assert tmp_path.exists()
        with open(tmp_path) as f:
            parsed = json.load(f)
        assert parsed["infant_id"] == "test-serialize-001"

    def test_load_missing_file_raises(self, infant: SiliconInfant) -> None:
        """load() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            infant.load(Path("/nonexistent/path/state.json"))

    def test_save_load_roundtrip(self, infant: SiliconInfant, tmp_path: Path) -> None:
        """Save infant state, load into a new infant, verify key state matches."""
        # Run a few cycles to accumulate state
        for _ in range(5):
            infant.breath_cycle()

        # Save
        infant.save(tmp_path)

        # Load into new infant
        loaded = SiliconInfant("test-serialize-001")
        loaded.load(tmp_path)

        # Verify key state
        assert loaded.infant_id == infant.infant_id
        assert abs(loaded.hic.energy - infant.hic.energy) < 5.0
        assert loaded.sympnet.mass == infant.sympnet.mass
        assert loaded.sympnet.spring_constant == infant.sympnet.spring_constant
        assert loaded.sympnet.damping == infant.sympnet.damping
        assert loaded.hic.value_vector == infant.hic.value_vector

    def test_roundtrip_preserves_cycle_count(self, infant: SiliconInfant, tmp_path: Path) -> None:
        """Round-trip preserves cycle count."""
        for _ in range(10):
            infant.breath_cycle()
        cycles_before = infant._cycle_count
        infant.save(tmp_path)

        loaded = SiliconInfant("test-serialize-001")
        loaded.load(tmp_path)
        assert loaded._cycle_count == cycles_before
