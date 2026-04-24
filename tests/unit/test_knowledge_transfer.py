"""
Unit tests for KnowledgeTransfer — cross-infant knowledge sharing.

TDD coverage:
- KnowledgeEntry serialization (to_dict / from_dict)
- Eligibility checks (trust_threshold via mutual_benefit)
- export_knowledge (similarity-based top-k selection)
- import_knowledge (deduplication, validation)
- Cosine similarity computation
- InfantSkill protocol compliance (initialize, can_activate, execute)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from cosmic_mycelium.infant.skills.base import SkillContext
from cosmic_mycelium.infant.skills.collective.knowledge_transfer import (
    KnowledgeEntry,
    KnowledgeTransfer,
)


class TestKnowledgeEntry:
    """Tests for KnowledgeEntry dataclass (serialization)."""

    def test_create_entry(self):
        """KnowledgeEntry constructs with all fields."""
        entry = KnowledgeEntry(
            entry_id="e1",
            feature_code="fc-abc123",
            embedding=[1.0, 2.0, 3.0],
            value_vector={"curiosity": 1.2},
            path_signature="abc",
            frequency=5,
            source_node_id="node-xyz",
            tags=["sensorimotor"],
        )
        assert entry.entry_id == "e1"
        assert entry.feature_code == "fc-abc123"
        assert entry.embedding == [1.0, 2.0, 3.0]
        assert entry.value_vector == {"curiosity": 1.2}
        assert entry.path_signature == "abc"
        assert entry.frequency == 5
        assert entry.source_node_id == "node-xyz"
        assert entry.tags == ["sensorimotor"]

    def test_to_dict_roundtrip(self):
        """to_dict() and from_dict() are inverse operations."""
        original = KnowledgeEntry(
            entry_id="e2",
            feature_code="fc-def456",
            embedding=[0.5, 1.5],
            value_vector={"caution": 0.8},
            path_signature="xyz",
            frequency=3,
            source_node_id="node-123",
            timestamp=1234567890.0,
            tags=["vibration"],
        )
        d = original.to_dict()
        recovered = KnowledgeEntry.from_dict(d)
        assert recovered.entry_id == original.entry_id
        assert recovered.feature_code == original.feature_code
        assert recovered.embedding == original.embedding
        assert recovered.value_vector == original.value_vector
        assert recovered.path_signature == original.path_signature
        assert recovered.frequency == original.frequency
        assert recovered.source_node_id == original.source_node_id
        assert recovered.tags == original.tags


class TestKnowledgeTransferInitialization:
    """Tests for KnowledgeTransfer construction and configuration."""

    def test_default_initialization(self):
        """Default trust_threshold=0.6, max_entries=50."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm)

        assert kt.trust_threshold == 0.6
        assert kt.max_entries == 50
        assert kt.enabled is True
        assert kt._pending_requests == {}

    def test_custom_threshold_and_limit(self):
        """Custom trust_threshold and max_entries_per_transfer respected."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        kt = KnowledgeTransfer(
            feature_manager=mock_fm,
            node_manager=mock_nm,
            trust_threshold=0.8,
            max_entries_per_transfer=20,
        )
        assert kt.trust_threshold == 0.8
        assert kt.max_entries == 20

    def test_hic_optional(self):
        """HIC is optional — None allowed."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm, hic=None)
        assert kt.hic is None


class TestEligibility:
    """Tests for is_eligible_donor() trust logic."""

    def test_trusted_node_passes(self):
        """mutual_benefit >= threshold → eligible."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        mock_hic = MagicMock()
        mock_hic.value_vector = {"mutual_benefit": 0.75}

        kt = KnowledgeTransfer(
            feature_manager=mock_fm, node_manager=mock_nm, hic=mock_hic, trust_threshold=0.6
        )
        assert kt.is_eligible_donor("any_node") is True

    def test_untrusted_node_fails(self):
        """mutual_benefit < threshold → not eligible."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        mock_hic = MagicMock()
        mock_hic.value_vector = {"mutual_benefit": 0.4}

        kt = KnowledgeTransfer(
            feature_manager=mock_fm, node_manager=mock_nm, hic=mock_hic, trust_threshold=0.6
        )
        assert kt.is_eligible_donor("any_node") is False

    def test_no_hic_returns_false(self):
        """Without HIC, cannot assess trust → not eligible."""
        kt = KnowledgeTransfer(feature_manager=MagicMock(), node_manager=MagicMock(), hic=None)
        assert kt.is_eligible_donor("any_node") is False


class TestExportKnowledge:
    """Tests for export_knowledge() similarity-based retrieval."""

    def test_export_returns_top_k_by_similarity(self):
        """Exported entries ranked by cosine similarity to query."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()

        # Create mock traces with known embeddings
        trace_a = MagicMock()
        trace_a.embedding = np.array([1.0, 0.0, 0.0])
        trace_a.feature_code = "fc-a"
        trace_a.value_vector = {}
        trace_a.path_signature = "path-a"
        trace_a.frequency = 5
        trace_a.tags = []

        trace_b = MagicMock()
        trace_b.embedding = np.array([0.0, 1.0, 0.0])
        trace_b.feature_code = "fc-b"
        trace_b.value_vector = {}
        trace_b.path_signature = "path-b"
        trace_b.frequency = 3
        trace_b.tags = []

        trace_c = MagicMock()
        trace_c.embedding = np.array([0.1, 0.0, 0.0])  # close to A
        trace_c.feature_code = "fc-c"
        trace_c.value_vector = {}
        trace_c.path_signature = "path-c"
        trace_c.frequency = 1
        trace_c.tags = []

        mock_fm.traces = [trace_a, trace_b, trace_c]
        mock_fm.traces_by_code = {"fc-a": trace_a, "fc-b": trace_b, "fc-c": trace_c}

        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm)
        query = np.array([1.0, 0.0, 0.0])

        entries = kt.export_knowledge(query, k=2)

        assert len(entries) == 2
        # fc-a and fc-c should be top-2 (both aligned with x-axis)
        returned_codes = {e.feature_code for e in entries}
        assert "fc-a" in returned_codes
        assert "fc-c" in returned_codes
        # fc-a should be first (exact match higher than 0.1 offset)
        assert entries[0].feature_code == "fc-a"

    def test_export_skips_traces_without_embedding(self):
        """Traces with None embedding are ignored during export."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        trace_valid = MagicMock()
        trace_valid.embedding = np.array([1.0, 0.0])
        trace_valid.feature_code = "valid"
        trace_valid.value_vector = {}
        trace_valid.path_signature = "p1"
        trace_valid.frequency = 1
        trace_valid.tags = []

        trace_null = MagicMock()
        trace_null.embedding = None
        trace_null.feature_code = "null"
        trace_null.value_vector = {}
        trace_null.path_signature = "p2"
        trace_null.frequency = 1
        trace_null.tags = []

        mock_fm.traces = [trace_valid, trace_null]
        mock_fm.traces_by_code = {"valid": trace_valid}

        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm)
        entries = kt.export_knowledge(np.array([1.0, 0.0]), k=10)
        assert len(entries) == 1
        assert entries[0].feature_code == "valid"

    def test_empty_traces_returns_empty_list(self):
        """No traces → no entries exported."""
        mock_fm = MagicMock()
        mock_fm.traces = []
        mock_fm.traces_by_code = {}
        mock_nm = MagicMock()

        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm)
        entries = kt.export_knowledge(np.array([1.0, 2.0]), k=5)
        assert entries == []

    def test_export_respects_max_entries_cap(self):
        """export respects max_entries even when k is larger."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        # 10 traces
        traces = []
        for i in range(10):
            t = MagicMock()
            t.embedding = np.array([float(i) * 0.1, 0.0, 0.0])
            t.feature_code = f"fc-{i}"
            t.value_vector = {}
            t.path_signature = f"p{i}"
            t.frequency = 1
            t.tags = []
            traces.append(t)
        mock_fm.traces = traces
        mock_fm.traces_by_code = {f"fc-{i}": traces[i] for i in range(10)}

        kt = KnowledgeTransfer(
            feature_manager=mock_fm, node_manager=mock_nm, max_entries_per_transfer=3
        )
        entries = kt.export_knowledge(np.array([0.0, 0.0, 0.0]), k=100)
        assert len(entries) == 3


class TestImportKnowledge:
    """Tests for import_knowledge() deduplication and validation."""

    def setup_method(self):
        """Common fixtures."""
        self.mock_fm = MagicMock()
        self.mock_fm.traces = []
        self.mock_fm.traces_by_code = {}
        self.mock_nm = MagicMock()
        self.kt = KnowledgeTransfer(feature_manager=self.mock_fm, node_manager=self.mock_nm)

    def test_import_adds_new_traces(self):
        """New entries are appended to FeatureManager."""
        entry = KnowledgeEntry(
            entry_id="e1",
            feature_code="fc-new",
            embedding=[0.5, 0.5],
            value_vector={"curiosity": 1.0},
            path_signature="sig123",
            frequency=1,
            source_node_id="remote-1",
        )
        imported, rejected = self.kt.import_knowledge([entry])

        assert imported == 1
        assert rejected == []
        self.mock_fm.append.assert_called_once()
        call_kwargs = self.mock_fm.append.call_args[1]
        assert call_kwargs["feature_code"] == "fc-new"
        assert np.allclose(call_kwargs["embedding"], [0.5, 0.5])

    def test_import_skips_duplicate_feature_codes(self):
        """Entries with already-known feature_codes are rejected as duplicates."""
        # Pre-seed local traces
        self.mock_fm.traces_by_code = {"fc-known": MagicMock()}

        entry = KnowledgeEntry(
            entry_id="e1",
            feature_code="fc-known",
            embedding=[1.0, 2.0],
            value_vector={},
            path_signature="sig",
            frequency=1,
            source_node_id="remote",
        )
        imported, rejected = self.kt.import_knowledge([entry])

        assert imported == 0
        assert len(rejected) == 1
        assert "duplicate" in rejected[0]
        self.mock_fm.append.assert_not_called()

    def test_import_rejects_invalid_value_vectors(self):
        """Entries with out-of-range or malformed value_vector rejected."""
        bad_entry = KnowledgeEntry(
            entry_id="e2",
            feature_code="fc-bad",
            embedding=[1.0, 1.0],
            value_vector={"curiosity": -999.0},  # absurd value
            path_signature="sig",
            frequency=1,
            source_node_id="remote",
        )
        imported, rejected = self.kt.import_knowledge([bad_entry])
        assert imported == 0
        assert any("invalid_value_vector" in r for r in rejected)

    def test_import_handles_append_exceptions(self):
        """Exceptions during FeatureManager.append are caught and reported."""
        self.mock_fm.append.side_effect = RuntimeError("disk full")

        entry = KnowledgeEntry(
            entry_id="e3",
            feature_code="fc-error",
            embedding=[1.0],
            value_vector={},
            path_signature="sig",
            frequency=1,
            source_node_id="remote",
        )
        imported, rejected = self.kt.import_knowledge([entry])
        assert imported == 0
        assert any("import_error" in r for r in rejected)

    def test_import_mixed_success_and_failure(self):
        """Mixed batch: some succeed, some fail, counts separated."""
        self.mock_fm.traces_by_code = {"fc-dup": MagicMock()}  # pre-existing

        entries = [
            KnowledgeEntry(
                entry_id="e1",
                feature_code="fc-new1",
                embedding=[1.0],
                value_vector={"x": 1.0},
                path_signature="s1",
                frequency=1,
                source_node_id="r1",
            ),
            KnowledgeEntry(
                entry_id="e2",
                feature_code="fc-dup",
                embedding=[2.0],
                value_vector={"x": 2.0},
                path_signature="s2",
                frequency=1,
                source_node_id="r2",
            ),
            KnowledgeEntry(
                entry_id="e3",
                feature_code="fc-new2",
                embedding=[3.0],
                value_vector={"x": -999.0},  # invalid
                path_signature="s3",
                frequency=1,
                source_node_id="r3",
            ),
        ]
        imported, rejected = self.kt.import_knowledge(entries)
        assert imported == 1
        assert len(rejected) == 2
        assert any("duplicate" in r for r in rejected)
        assert any("invalid_value_vector" in r for r in rejected)


class TestCosineSimilarity:
    """Tests for _cosine_similarity() helper."""

    def setup_method(self):
        self.kt = KnowledgeTransfer(
            feature_manager=MagicMock(), node_manager=MagicMock()
        )

    def test_identical_vectors_similarity_one(self):
        """Identical vectors have cosine similarity = 1.0."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        sim = self.kt._cosine_similarity(a, b)
        assert np.isclose(sim, 1.0)

    def test_orthogonal_vectors_similarity_zero(self):
        """Orthogonal vectors have cosine similarity = 0."""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        sim = self.kt._cosine_similarity(a, b)
        assert np.isclose(sim, 0.0)

    def test_opposite_vectors_similarity_negative_one(self):
        """Opposite vectors have cosine similarity = -1."""
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        sim = self.kt._cosine_similarity(a, b)
        assert np.isclose(sim, -1.0)

    def test_different_lengths_are_truncated(self):
        """Vectors of different lengths are truncated to shorter."""
        a = np.array([1.0, 2.0, 3.0, 4.0])
        b = np.array([1.0, 2.0])
        sim = self.kt._cosine_similarity(a, b)
        # Effectively comparing [1,2] vs [1,2]
        assert np.isclose(sim, 1.0)

    def test_zero_vectors_return_zero(self):
        """Zero vectors produce similarity 0 (avoid division by zero)."""
        a = np.array([0.0, 0.0])
        b = np.array([0.0, 0.0])
        sim = self.kt._cosine_similarity(a, b)
        assert sim == 0.0


class TestValueVectorValidation:
    """Tests for _validate_value_vector()."""

    def setup_method(self):
        self.kt = KnowledgeTransfer(
            feature_manager=MagicMock(), node_manager=MagicMock()
        )

    def test_valid_vector_passes(self):
        """Standard value vector with floats passes."""
        vv = {"curiosity": 1.2, "caution": 0.8, "mutual_benefit": 1.5}
        assert self.kt._validate_value_vector(vv) is True

    def test_invalid_type_fails(self):
        """Non-dict fails."""
        assert self.kt._validate_value_vector([]) is False
        assert self.kt._validate_value_vector("not a dict") is False

    def test_non_string_keys_fail(self):
        """Non-string keys fail validation."""
        vv = {1: 1.0, "a": 2.0}
        assert self.kt._validate_value_vector(vv) is False

    def test_non_numeric_values_fail(self):
        """Non-numeric values fail."""
        vv = {"a": "not a number"}
        assert self.kt._validate_value_vector(vv) is False

    def test_extreme_values_fail(self):
        """Values outside [-10, 10] range fail (sanity bound)."""
        vv_high = {"x": 10.001}
        vv_low = {"y": -10.001}
        assert self.kt._validate_value_vector(vv_high) is False
        assert self.kt._validate_value_vector(vv_low) is False

    def test_boundary_values_pass(self):
        """Values at exactly ±10 pass."""
        vv = {"a": 10.0, "b": -10.0}
        assert self.kt._validate_value_vector(vv) is True


class TestKnowledgeTransferExecute:
    """Tests for execute() skill entry point."""

    def test_execute_returns_dict_with_imported_count(self):
        """execute() returns status dict with imported count (currently 0)."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm)
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

        result = kt.execute({})

        assert isinstance(result, dict)
        assert result["imported"] == 0
        assert result["energy_cost"] == 3.0

    def test_execute_returns_zero_when_disabled(self):
        """Disabled skill returns 0 imported."""
        mock_fm = MagicMock()
        mock_nm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=mock_nm)
        kt.enabled = False
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

        result = kt.execute({})
        assert result["imported"] == 0

    def test_execute_requires_initialization(self):
        """execute() raises if not initialized."""
        kt = KnowledgeTransfer(feature_manager=MagicMock(), node_manager=MagicMock())
        # Not initialized
        with pytest.raises(RuntimeError, match="not initialized"):
            kt.execute({})

    def test_can_activate_checks_feature_manager(self):
        """can_activate returns False if FeatureManager missing."""
        kt = KnowledgeTransfer(feature_manager=None, node_manager=MagicMock())
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        assert kt.can_activate(SkillContext(infant_id="test", cycle_count=0, energy_available=10)) is False

    def test_can_activate_checks_energy(self):
        """can_activate returns False if energy budget insufficient."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=MagicMock())
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=2.0))
        assert kt.can_activate(SkillContext(infant_id="test", cycle_count=0, energy_available=2.0)) is False

    def test_can_activate_happy_path(self):
        """can_activate True when all conditions satisfied."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, node_manager=MagicMock())
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        assert kt.can_activate(SkillContext(infant_id="test", cycle_count=0, energy_available=10)) is True


class TestLRUCache:
    """Sprint 3: LRU similarity cache tests."""

    def setup_method(self):
        self.mock_fm = MagicMock()
        trace = MagicMock()
        trace.embedding = np.array([1.0, 0.0])
        trace.feature_code = "fc1"
        trace.value_vector = {}
        trace.path_signature = "p1"
        trace.frequency = 1
        trace.tags = []
        self.mock_fm.traces = [trace]
        self.kt = KnowledgeTransfer(feature_manager=self.mock_fm, hic=MagicMock())
        self.kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

    def test_cache_hit_returns_same_object(self):
        """Identical query should hit cache and return same list object."""
        query = np.array([1.0, 0.0])
        first = self.kt.export_knowledge(query, k=1)
        second = self.kt.export_knowledge(query, k=1)
        assert first is second
        assert len(first) == 1

    def test_cache_miss_returns_different_objects(self):
        """Different queries should compute separately."""
        q1 = np.array([1.0, 0.0])
        q2 = np.array([0.0, 1.0])
        r1 = self.kt.export_knowledge(q1, k=1)
        r2 = self.kt.export_knowledge(q2, k=1)
        assert r1 is not r2
        assert len(r1) == 1 and len(r2) == 1

    def test_cache_evicts_oldest_when_full(self):
        """LRU eviction removes least recently used entry."""
        kt = KnowledgeTransfer(feature_manager=self.mock_fm, hic=MagicMock())
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        kt._cache_max_size = 2
        q1 = np.array([1.0, 0.0])
        q2 = np.array([0.0, 1.0])
        q3 = np.array([0.5, 0.5])
        kt.export_knowledge(q1, k=1)
        kt.export_knowledge(q2, k=1)
        kt.export_knowledge(q3, k=1)  # triggers eviction of q1
        assert len(kt._similarity_cache) == 2
        key1 = ((1.0, 0.0), 1)
        assert key1 not in kt._similarity_cache

    def test_import_knowledge_clears_cache(self):
        """import_knowledge invalidates entire similarity cache."""
        query = np.array([1.0, 0.0])
        self.kt.export_knowledge(query, k=1)
        assert len(self.kt._similarity_cache) == 1
        entry = KnowledgeEntry(
            entry_id="e1",
            feature_code="fc2",
            embedding=[0.5, 0.5],
            value_vector={},
            path_signature="p2",
            frequency=1,
            source_node_id="remote",
        )
        self.kt.import_knowledge([entry])
        assert len(self.kt._similarity_cache) == 0
