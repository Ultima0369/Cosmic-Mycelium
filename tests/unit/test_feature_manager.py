"""
Feature Manager Unit Tests

Tests for the Hermes-inspired feature code extraction and management system.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from cosmic_mycelium.infant.feature_manager import FeatureManager
from cosmic_mycelium.common.feature_code import FeatureCode
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper


@pytest.fixture
def fm(tmp_path):
    """FeatureManager with temporary storage."""
    return FeatureManager("test_infant", storage_path=tmp_path / "features")


class TestFeatureCode:
    """Tests for FeatureCode dataclass."""

    def test_create_minimal(self):
        """FeatureCode can be created with required fields."""
        fc = FeatureCode(
            code_id="abc123",
            name="test_feature",
            description="A test feature",
            trigger_patterns=["pattern_a"],
            action_sequence=[{"action": "move", "value": 1}],
        )
        assert fc.code_id == "abc123"
        assert fc.name == "test_feature"
        assert fc.success_count == 0
        assert fc.failure_count == 0
        assert fc.efficacy() == 0.5  # Neutral when no stats

    def test_efficacy_calculation(self):
        """Efficacy = success / (success + failure)."""
        fc = FeatureCode(
            code_id="x",
            name="x",
            description="x",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        fc.success_count = 7
        fc.failure_count = 3
        assert fc.efficacy() == 0.7

    def test_efficacy_neutral_when_unused(self):
        """Unused feature has efficacy 0.5."""
        fc = FeatureCode(
            code_id="y",
            name="y",
            description="y",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        assert fc.efficacy() == 0.5

    def test_reinforce_updates_counts(self):
        """reinforce() updates success/failure counts and last_used."""
        fc = FeatureCode(
            code_id="z",
            name="z",
            description="z",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        initial_time = fc.last_used
        time.sleep(0.01)
        fc.reinforce(success=True)
        assert fc.success_count == 1
        assert fc.failure_count == 0
        assert fc.last_used > initial_time

        fc.reinforce(success=False)
        assert fc.success_count == 1
        assert fc.failure_count == 1
        assert fc.efficacy() == 0.5

    def test_serialization_roundtrip(self):
        """to_dict and from_dict are inverse operations."""
        fc = FeatureCode(
            code_id="serial123",
            name="serializable",
            description="Test serialization",
            trigger_patterns=["a", "b"],
            action_sequence=[{"a": 1}, {"b": 2}],
            success_count=5,
            failure_count=2,
            validation_fingerprint="fp:abc",
        )
        data = fc.to_dict()
        fc2 = FeatureCode.from_dict(data)
        assert fc2.code_id == fc.code_id
        assert fc2.name == fc.name
        assert fc2.success_count == 5
        assert fc2.failure_count == 2

    def test_generate_id_deterministic(self):
        """generate_id produces consistent IDs for same input."""
        id1 = FeatureCode.generate_id("my skill", ["a", "b"])
        id2 = FeatureCode.generate_id("my skill", ["a", "b"])
        assert id1 == id2
        assert len(id1) == 12  # truncated sha256

    def test_generate_id_order_independent(self):
        """Pattern order doesn't affect ID (sorted)."""
        id1 = FeatureCode.generate_id("test", ["c", "a", "b"])
        id2 = FeatureCode.generate_id("test", ["a", "b", "c"])
        assert id1 == id2


class TestFeatureManagerInitialization:
    """Tests for FeatureManager construction and persistence setup."""

    def test_creates_storage_directory(self, tmp_path):
        """Storage directory is created on init."""
        storage = tmp_path / "my_features"
        FeatureManager("test", storage_path=storage)
        assert storage.exists()
        assert storage.is_dir()

    def test_loads_existing_features(self, tmp_path):
        """Existing JSON feature codes are loaded at startup."""
        storage = tmp_path / "features"
        storage.mkdir(parents=True)
        # Write a feature file
        fc_data = {
            "code_id": "loaded123",
            "name": "loaded feature",
            "description": "pre-existing",
            "trigger_patterns": ["vibration"],
            "action_sequence": [{"action": "adjust"}],
            "success_count": 3,
            "failure_count": 1,
            "created_at": time.time() - 3600,
            "last_used": time.time() - 1800,
            "validation_fingerprint": None,
        }
        (storage / "loaded123.json").write_text(json.dumps(fc_data))

        fm = FeatureManager("test", storage_path=storage)
        assert "loaded123" in fm.features
        loaded = fm.features["loaded123"]
        assert loaded.name == "loaded feature"
        assert loaded.success_count == 3

    def test_pattern_index_built_on_load(self, tmp_path):
        """Pattern index is populated from loaded features."""
        storage = tmp_path / "features"
        storage.mkdir(parents=True)
        fc_data = {
            "code_id": "idx123",
            "name": "indexed",
            "description": "test",
            "trigger_patterns": ["high_energy", "vibration"],
            "action_sequence": [],
            "success_count": 0,
            "failure_count": 0,
            "created_at": time.time(),
            "last_used": time.time(),
            "validation_fingerprint": None,
        }
        (storage / "idx123.json").write_text(json.dumps(fc_data))

        fm = FeatureManager("test", storage_path=storage)
        assert "idx123" in fm.pattern_index["high_energy"]
        assert "idx123" in fm.pattern_index["vibration"]


class TestCreateOrUpdate:
    """Tests for creating and updating feature codes."""

    def test_create_new_feature(self, fm):
        """create_or_update creates a new feature code."""
        fc = fm.create_or_update(
            name="test feature",
            description="test description",
            trigger_patterns=["pattern1"],
            action_sequence=[{"action": "test"}],
        )
        assert fc.code_id in fm.features
        assert fc.name == "test feature"
        assert fc.success_count == 0
        assert fc.failure_count == 0

    def test_update_existing_feature(self, fm):
        """create_or_update merges into existing feature when name unchanged."""
        fc = fm.create_or_update(
            name="my_feature",
            description="original desc",
            trigger_patterns=["a"],
            action_sequence=[{"a": 1}],
        )
        original_id = fc.code_id

        # Update with same name (same identity), new data
        fc2 = fm.create_or_update(
            name="my_feature",  # same name → same ID
            description="updated desc",
            trigger_patterns=["a"],  # same trigger
            action_sequence=[{"b": 2}],
        )
        assert fc2.code_id == original_id
        assert fm.features[original_id].description == "updated desc"
        # Action sequence should be merged (new + old)
        assert len(fm.features[original_id].action_sequence) >= 2

    def test_saves_to_disk(self, fm):
        """Feature is persisted to JSON file."""
        fm.create_or_update(
            name="persistent",
            description="persist me",
            trigger_patterns=["x"],
            action_sequence=[],
        )
        files = list(fm.storage_path.glob("*.json"))
        assert len(files) == 1
        # Verify file content
        data = json.loads(files[0].read_text())
        assert data["name"] == "persistent"

    def test_validation_fingerprint_stored(self, fm):
        """Validation fingerprint is saved with feature."""
        fc = fm.create_or_update(
            name="validated",
            description="with fp",
            trigger_patterns=["p"],
            action_sequence=[],
            validation_fingerprint="fp:abc123",
        )
        # fc is the created FeatureCode instance
        assert fc.validation_fingerprint == "fp:abc123"
        # Also verify persistence
        retrieved = fm.features[fc.code_id]
        assert retrieved.validation_fingerprint == "fp:abc123"


class TestMatch:
    """Tests for pattern matching and retrieval."""

    def test_match_by_trigger_pattern(self, fm):
        """Features match when their trigger pattern appears in perception."""
        fm.create_or_update(
            name="high energy response",
            description="when energy is high",
            trigger_patterns=["high_energy"],
            action_sequence=[{"action": "slow_down"}],
        )
        fm.create_or_update(
            name="vibration handler",
            description="when vibrating",
            trigger_patterns=["vibration"],
            action_sequence=[{"action": "stabilize"}],
        )

        matches = fm.match(["high_energy"])
        assert len(matches) == 1
        assert matches[0].name == "high energy response"

    def test_match_multiple_patterns(self, fm):
        """Multiple matching patterns yield multiple candidates."""
        fm.create_or_update(
            name="combo",
            description="combo feature",
            trigger_patterns=["a", "b"],
            action_sequence=[],
        )
        fm.create_or_update(
            name="single_a",
            description="only a",
            trigger_patterns=["a"],
            action_sequence=[],
        )
        matches = fm.match(["a", "b"])
        # Both match (combo matches both a and b, single_a matches a)
        assert len(matches) >= 2

    def test_match_filters_by_min_efficacy(self, fm):
        """Features with efficacy below threshold are filtered out."""
        fc = fm.create_or_update(
            name="low_quality",
            description="will be filtered",
            trigger_patterns=["test"],
            action_sequence=[],
        )
        # Artificially lower efficacy
        fm.reinforce(fc.code_id, success=False)
        fm.reinforce(fc.code_id, success=False)
        fm.reinforce(fc.code_id, success=False)
        fm.reinforce(fc.code_id, success=False)
        fm.reinforce(fc.code_id, success=True)  # 1/5 = 0.2

        matches = fm.match(["test"], min_efficacy=0.3)
        assert len(matches) == 0

    def test_match_sorted_by_efficacy_and_recency(self, fm):
        """Matches sorted by efficacy × time decay factor."""
        # Create two features with different efficacies
        fc1 = fm.create_or_update(
            name="high_eff",
            description="high",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        for _ in range(10):
            fm.reinforce(fc1.code_id, success=True)

        fc2 = fm.create_or_update(
            name="low_eff",
            description="low",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        for _ in range(10):
            fm.reinforce(fc2.code_id, success=False)

        matches = fm.match(["p"], min_efficacy=0.0)  # Include all efficacies
        assert len(matches) == 2
        assert matches[0].name == "high_eff"
        assert matches[-1].name == "low_eff"


class TestReinforceAndForget:
    """Tests for reinforcement learning and forgetting."""

    def test_reinforce_updates_feature(self, fm):
        """Reinforcement updates success/failure counts and persists."""
        fc = fm.create_or_update(
            name="reinforce_me",
            description="test",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        fm.reinforce(fc.code_id, success=True)
        fm.reinforce(fc.code_id, success=True)
        fm.reinforce(fc.code_id, success=False)

        updated = fm.features[fc.code_id]
        assert updated.success_count == 2
        assert updated.failure_count == 1
        assert updated.efficacy() == 2/3

    def test_reinforce_persists_to_disk(self, fm):
        """Reinforcement updates are saved to disk."""
        fc = fm.create_or_update(
            name="persistent_reinforce",
            description="test",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        fm.reinforce(fc.code_id, success=True)

        # Re-load manager
        fm2 = FeatureManager(fm.infant_id, storage_path=fm.storage_path)
        loaded = fm2.features[fc.code_id]
        assert loaded.success_count == 1

    def test_forget_removes_low_efficacy_feature(self, fm):
        """Features with efficacy < 0.1 and >10 uses are auto-forgotten."""
        fc = fm.create_or_update(
            name="forget_me",
            description="low quality",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        # Make it low efficacy with many trials
        for _ in range(6):
            fm.reinforce(fc.code_id, success=False)
        for _ in range(5):
            fm.reinforce(fc.code_id, success=True)
        # 5/11 = 0.45, not low enough
        assert fc.code_id in fm.features

        # Continue to make it worse
        for _ in range(10):
            fm.reinforce(fc.code_id, success=False)
        # Now 5/21 = 0.19, still not < 0.1
        # Let's make it really bad
        for _ in range(30):
            fm.reinforce(fc.code_id, success=False)
        # Now 5/56 ≈ 0.09 < 0.1, total > 10 → should be forgotten
        assert fc.code_id not in fm.features
        assert fc.code_id not in fm.pattern_index["p"]
        # File should be deleted
        assert not (fm.storage_path / f"{fc.code_id}.json").exists()

    def test_forget_not_triggered_for_recent_features(self, fm):
        """Features with few uses are not forgotten even if efficacy 0."""
        fc = fm.create_or_update(
            name="new_feature",
            description="only tried once and failed",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        fm.reinforce(fc.code_id, success=False)  # 0/1 = 0.0
        # Total uses = 1, < 10 threshold → not forgotten
        assert fc.code_id in fm.features


class TestListAndStats:
    """Tests for listing and statistics."""

    def test_list_all_sorted_by_efficacy(self, fm):
        """list_all returns features sorted by efficacy descending."""
        fm.create_or_update(
            name="low",
            description="low",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        fc_high = fm.create_or_update(
            name="high",
            description="high",
            trigger_patterns=["p"],
            action_sequence=[],
        )
        # Boost high
        for _ in range(10):
            fm.reinforce(fc_high.code_id, success=True)

        all_features = fm.list_all()
        assert all_features[0].name == "high"
        assert all_features[-1].name == "low"

    def test_get_stats_returns_reasonable_values(self, fm):
        """get_stats provides useful summary information."""
        fm.create_or_update(
            name="s1",
            description="s1",
            trigger_patterns=["a"],
            action_sequence=[],
        )
        fm.create_or_update(
            name="s2",
            description="s2",
            trigger_patterns=["b"],
            action_sequence=[],
        )
        stats = fm.get_stats()
        assert stats["total_features"] == 2
        assert stats["patterns_indexed"] == 2
        assert "storage_path" in stats


@pytest.fixture
def fm_with_semantic(tmp_path):
    """FeatureManager with SemanticMapper for Epic 3 tests."""
    mapper = SemanticMapper(embedding_dim=16)
    return FeatureManager(
        "test_infant_semantic",
        storage_path=tmp_path / "features_semantic",
        semantic_mapper=mapper,
    )


class TestEpic3SemanticMemory:
    """Tests for vector semantic memory (Epic 3)."""

    def test_recall_semantic_returns_similar_features(self, fm_with_semantic):
        """recall_semantic finds features by embedding similarity."""
        # Create features with distinct semantic meanings via trigger patterns
        fc1 = fm_with_semantic.create_or_update(
            name="vibration handler",
            description="responds to mechanical vibration",
            trigger_patterns=["vibration", "mechanical"],
            action_sequence=[{"action": "stabilize"}],
        )
        fc2 = fm_with_semantic.create_or_update(
            name="temperature regulator",
            description="responds to thermal changes",
            trigger_patterns=["temperature", "thermal"],
            action_sequence=[{"action": "cool"}],
        )

        # Search for vibration-related concept
        results = fm_with_semantic.recall_semantic("mechanical vibration", k=2)
        assert len(results) >= 1
        # The vibration-related feature should be in results
        names = [f.name for f in results]
        assert "vibration handler" in names

    def test_recall_semantic_empty_when_no_semantic_mapper(self, tmp_path):
        """recall_semantic returns empty without semantic_mapper."""
        fm = FeatureManager("test", storage_path=tmp_path / "features")
        fc = fm.create_or_update(
            name="test", description="test", trigger_patterns=["a"], action_sequence=[]
        )
        results = fm.recall_semantic("query", k=5)
        assert results == []

    def test_recall_by_embedding_direct(self, fm_with_semantic):
        """recall_by_embedding searches by raw vector."""
        fc = fm_with_semantic.create_or_update(
            name="test feature",
            description="test description",
            trigger_patterns=["test"],
            action_sequence=[],
        )
        # Use the feature's own embedding as query
        query_vec = fc.embedding
        assert query_vec is not None
        results = fm_with_semantic.recall_by_embedding(query_vec, k=1)
        assert len(results) == 1
        assert results[0].code_id == fc.code_id

    def test_cluster_active_features_forms_clusters(self, fm_with_semantic):
        """cluster_active_features groups similar features."""
        # Create several related features to form a cluster
        for i in range(5):
            fm_with_semantic.create_or_update(
                name=f"vibration feature {i}",
                description="mechanical vibration response pattern",
                trigger_patterns=[f"vib_{i}"],
                action_sequence=[],
            )
        # Create an outlier
        fm_with_semantic.create_or_update(
            name="temperature sensor",
            description="thermal sensing",
            trigger_patterns=["temperature"],
            action_sequence=[],
        )

        clusters = fm_with_semantic.cluster_active_features(min_samples=3, eps=0.3)
        # Should have at least one cluster with the vibration features
        assert len(clusters) >= 1
        # All vibration features should be in same cluster(s)
        vib_names = [f.name for cluster in clusters.values() for f in cluster if "vibration" in f.name]
        assert len(vib_names) >= 3  # At least 3 of 5 clustered together

    def test_cluster_returns_empty_when_insufficient_samples(self, fm_with_semantic):
        """cluster_active_features returns {} when fewer than min_samples."""
        fm_with_semantic.create_or_update(
            name="solo",
            description="only one",
            trigger_patterns=["solo"],
            action_sequence=[],
        )
        clusters = fm_with_semantic.cluster_active_features(min_samples=3)
        assert clusters == {}

    def test_get_cluster_label_generates_readable_name(self, fm_with_semantic):
        """get_cluster_label returns human-readable cluster name."""
        # Create cluster of features with common keywords
        for i in range(3):
            fm_with_semantic.create_or_update(
                name=f"high energy response {i}",
                description="energy spike handling",
                trigger_patterns=[f"energy_{i}"],
                action_sequence=[],
            )
        clusters = fm_with_semantic.cluster_active_features(min_samples=2, eps=0.5)
        if clusters:
            cluster_id = next(iter(clusters))
            label = fm_with_semantic.get_cluster_label(cluster_id)
            # Should contain common word like "energy" or "response"
            assert "energy" in label or "response" in label

    def test_cluster_assigns_cluster_id_to_features(self, fm_with_semantic):
        """Features get cluster_id attribute after clustering."""
        for i in range(4):
            fm_with_semantic.create_or_update(
                name=f"feature {i}",
                description="similar feature for clustering",
                trigger_patterns=[f"pat_{i}"],
                action_sequence=[],
            )
        fm_with_semantic.cluster_active_features(min_samples=2, eps=0.5)
        # Some features should have cluster_id set
        clustered = [fc for fc in fm_with_semantic.features.values() if fc.cluster_id is not None]
        assert len(clustered) >= 2
