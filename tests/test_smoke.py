"""
Cosmic Mycelium — Smoke Tests
Factory-floor "does it breathe?" validation.

Run: pytest tests/test_smoke.py -v
This is the FIRST gate before any detailed testing.
"""

from __future__ import annotations

import importlib

import pytest

# List of core modules that MUST import without error
CORE_MODULES = [
    "cosmic_mycelium",
    "cosmic_mycelium.common",
    "cosmic_mycelium.common.data_packet",
    "cosmic_mycelium.common.physical_fingerprint",
    "cosmic_mycelium.common.config_manager",
    "cosmic_mycelium.infant",
    "cosmic_mycelium.infant.main",
    "cosmic_mycelium.infant.hic",
    "cosmic_mycelium.infant.core.layer_1_timescale_segmenter",
    "cosmic_mycelium.infant.core.layer_2_semantic_mapper",
    "cosmic_mycelium.infant.core.layer_3_slime_explorer",
    "cosmic_mycelium.infant.core.layer_4_myelination_memory",
    "cosmic_mycelium.infant.core.layer_5_superbrain",
    "cosmic_mycelium.infant.core.layer_6_symbiosis_interface",
    "cosmic_mycelium.infant.engines.engine_sympnet",
    "cosmic_mycelium.infant.engines.engine_sympnet",
    "cosmic_mycelium.cluster",
    "cosmic_mycelium.cluster.node_manager",
    "cosmic_mycelium.cluster.flow_router",
    "cosmic_mycelium.cluster.consensus",
    "cosmic_mycelium.scripts.run_infant",
    "cosmic_mycelium.scripts.run_cluster",
]


class TestImports:
    """Smoke test: all core modules must import cleanly."""

    @pytest.mark.parametrize("module_name", CORE_MODULES)
    def test_module_imports(self, module_name):
        """Import each core module without error."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")


class TestBasicTypes:
    """Smoke test: fundamental types exist and are usable."""

    def test_cosmic_packet_exists(self):
        """CosmicPacket class is accessible."""
        from cosmic_mycelium.common.data_packet import CosmicPacket

        assert CosmicPacket is not None

    def test_physical_fingerprint_exists(self):
        """PhysicalFingerprint class is accessible."""
        from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint

        assert PhysicalFingerprint is not None

    def test_hic_exists(self):
        """HIC class is accessible."""
        from cosmic_mycelium.infant.hic import HIC

        assert HIC is not None

    def test_sympnet_exists(self):
        """SympNetEngine class is accessible."""
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        assert SympNetEngine is not None


class TestInstantiation:
    """Smoke test: core classes can be instantiated."""

    def test_instantiate_hic(self):
        """HIC can be instantiated with defaults."""
        from cosmic_mycelium.infant.hic import HIC

        hic = HIC()
        assert hic.energy > 0

    def test_instantiate_sympnet(self):
        """SympNetEngine can be instantiated."""
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        engine = SympNetEngine()
        assert engine.mass == 1.0

    def test_instantiate_silicon_infant(self):
        """SiliconInfant can be instantiated."""
        from cosmic_mycelium.infant.main import SiliconInfant

        infant = SiliconInfant(infant_id="smoke-test-001")
        assert infant.infant_id == "smoke-test-001"
        assert infant.hic is not None
        assert infant.sympnet is not None


class TestPhysicalAnchorSmoke:
    """Smoke test: the physical anchor holds at basic level."""

    def test_fingerprint_roundtrip(self):
        """Physical fingerprint: generate → verify must succeed."""
        from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint

        data = {"smoke": "test", "value": 42}
        fp = PhysicalFingerprint.generate(data)
        assert PhysicalFingerprint.verify(data, fp) is True

    def test_sympnet_energy_positive(self):
        """SympNet energy is always positive."""
        from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

        engine = SympNetEngine()
        q, p = 1.0, 0.0
        for _ in range(100):
            q, p = engine.step(q, p, dt=0.01)
            energy = engine.compute_energy(q, p)
            assert energy >= 0, "Energy went negative!"


class TestPackageMetadata:
    """Smoke test: package metadata is accessible."""

    def test_package_version_exists(self):
        """Package has a version string."""
        import cosmic_mycelium

        assert hasattr(cosmic_mycelium, "__version__")
        assert cosmic_mycelium.__version__ is not None

    def test_package_license(self):
        """Package declares AGPL-3.0 license."""
        import cosmic_mycelium

        assert hasattr(cosmic_mycelium, "__license__")
        assert cosmic_mycelium.__license__ == "AGPL-3.0"
