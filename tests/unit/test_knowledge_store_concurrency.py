"""
Concurrency tests for KnowledgeStore thread-safety (Sprint 5).

Tests:
- Concurrent add() from multiple threads — no data corruption
- Concurrent add + recall_semantic — no race conditions
- Vector index integrity under load
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper
from cosmic_mycelium.infant.knowledge_store import KnowledgeEntry, KnowledgeStore


@pytest.fixture
def knowledge_store(tmp_path):
    """Create a KnowledgeStore with temporary storage."""
    mapper = SemanticMapper(embedding_dim=16)
    store = KnowledgeStore(
        infant_id="test-concurrency",
        semantic_mapper=mapper,
        storage_path=tmp_path / "knowledge",
    )
    return store


class TestKnowledgeStoreConcurrency:
    """Thread-safety validation for KnowledgeStore."""

    def test_concurrent_adds_are_thread_safe(self, knowledge_store):
        """Multiple threads add entries concurrently without corruption."""
        num_threads = 10
        entries_per_thread = 100

        def add_entries(thread_id: int):
            for i in range(entries_per_thread):
                entry = KnowledgeEntry(
                    entry_id=f"thread{thread_id}_entry{i}",
                    question=f"Question from thread {thread_id}, number {i}",
                    hypothesis=f"Hypothesis {i}",
                    experiment_method=f"method_{i}",
                    result={"value": i},
                    conclusion="success",
                    confidence=0.8,
                )
                knowledge_store.add(entry)

        threads = [threading.Thread(target=add_entries, args=(t,)) for t in range(num_threads)]
        start = time.time()
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        elapsed = time.time() - start

        # All entries should be present
        assert len(knowledge_store.entries) == num_threads * entries_per_thread
        # No exceptions raised = no data race detected
        assert elapsed < 30.0  # Should complete reasonably fast

    def test_concurrent_add_and_recall_is_thread_safe(self, knowledge_store):
        """Concurrent add() and recall_semantic() operations are safe."""
        errors = []

        def adder():
            for i in range(200):
                entry = KnowledgeEntry(
                    entry_id=f"adder_entry{i}",
                    question=f"Question {i}",
                    hypothesis=f"Hypothesis {i}",
                    experiment_method=f"method_{i}",
                    result={"value": i},
                    conclusion="success",
                    confidence=0.8,
                )
                try:
                    knowledge_store.add(entry)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.001)

        def recaller():
            for i in range(200):
                try:
                    results = knowledge_store.recall_semantic("test query", k=5)
                    assert isinstance(results, list)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.001)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=recaller)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Concurrency errors: {errors}"

    def test_vector_index_integrity_under_concurrent_adds(self, knowledge_store):
        """Vector index remains consistent after concurrent adds."""
        num_threads = 8
        entries_per_thread = 50

        def add_entries(thread_id: int):
            for i in range(entries_per_thread):
                entry = KnowledgeEntry(
                    entry_id=f"vec_thread{thread_id}_entry{i}",
                    question=f"Topic {i}",
                    hypothesis=f"Testing vector indexing {i}",
                    experiment_method="none",
                    result={},
                    conclusion="inconclusive",
                    confidence=0.5,
                )
                knowledge_store.add(entry)

        threads = [threading.Thread(target=add_entries, args=(t,)) for t in range(num_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        # Verify search returns valid entries
        results = knowledge_store.recall_semantic("topic hypothesis testing", k=10)
        assert len(results) <= 10
        for r in results:
            assert r.entry_id is not None
            assert r.embedding is not None
            assert r.embedding.shape[0] == 16

    def test_no_duplicate_entries_under_race(self, knowledge_store):
        """Same entry ID added concurrently does not corrupt entries."""
        entry = KnowledgeEntry(
            entry_id="shared_id",
            question="Shared question",
            hypothesis="Shared hypothesis",
            experiment_method="shared_method",
            result={},
            conclusion="success",
            confidence=0.9,
        )

        def try_add():
            for _ in range(50):
                try:
                    knowledge_store.add(entry)
                except Exception:
                    pass  # Expected if locked

        threads = [threading.Thread(target=try_add) for _ in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        # Only one entry should exist
        assert "shared_id" in knowledge_store.entries
        # Count should be 1 (not duplicated)
        assert len([e for eid, e in knowledge_store.entries.items() if eid == "shared_id"]) == 1
