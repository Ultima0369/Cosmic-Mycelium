"""
Unit tests for Sprint 1 Epic 1: Autonomous Research Loop.

Covers: KnowledgeStore add/recall, QuestionGenerator.generate,
ExperimentDesigner.design, end-to-end conduct_research integration.
"""

import numpy as np
import pytest

from cosmic_mycelium.infant.knowledge_store import KnowledgeStore, KnowledgeEntry
from cosmic_mycelium.infant.skills.research.question_generator import (
    QuestionGenerator,
    GeneratedQuestion,
)
from cosmic_mycelium.infant.skills.research.experiment_designer import (
    ExperimentDesigner,
    ExperimentPlan,
)
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper


class TestKnowledgeStore:
    """Test KnowledgeStore CRUD and semantic recall."""

    def test_add_and_get_entry(self):
        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("test-add", mapper)
        entry = KnowledgeEntry(
            entry_id="e1",
            question="能量下降时怎么办？",
            hypothesis="延长 CONTRACT 可以恢复能量",
            experiment_method="adjust_breath_cycle(contract_ms=150)",
            result={"energy_before": 30, "energy_after": 65},
            conclusion="success",
            confidence=0.85,
        )
        store.add(entry)
        retrieved = store.get("e1")
        assert retrieved is not None
        assert retrieved.question == entry.question

    def test_recall_semantic_returns_related_entries(self):
        from cosmic_mycelium.utils.embeddings import text_to_embedding
        from unittest.mock import patch

        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("test-recall-semantic", mapper)

        e1 = KnowledgeEntry(
            entry_id="e1",
            question="能量持续下降",
            hypothesis="需要恢复",
            experiment_method="adjust_breath_cycle(contract_ms=150)",
            result={},
            conclusion="success",
            confidence=0.8,
            # e1 more aligned with query embedding
            embedding=np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32),
        )
        e2 = KnowledgeEntry(
            entry_id="e2",
            question="能量不足",
            hypothesis="需要恢复",
            experiment_method="adjust_breath_cycle(diffuse_ms=200)",
            result={},
            conclusion="failure",
            confidence=0.4,
            # e2 less aligned with query
            embedding=np.array([0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3], dtype=np.float32),
        )
        store.add(e1)
        store.add(e2)

        # Query semantically similar — mock at embeddings module so recall_semantic gets controlled vector
        query_vec = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        with patch("cosmic_mycelium.utils.embeddings.text_to_embedding", return_value=query_vec):
            results = store.recall_semantic("能量下降该怎么恢复", k=2)
        assert len(results) == 2
        # e1 should rank higher (exact match to query vector)
        assert results[0].entry_id == "e1"

    def test_recall_by_confidence_sorts_correctly(self):
        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("test-recall-confidence", mapper)

        low = KnowledgeEntry(
            entry_id="low",
            question="A",
            hypothesis="H",
            experiment_method="m1",
            result={},
            conclusion="success",
            confidence=0.3,
        )
        high = KnowledgeEntry(
            entry_id="high",
            question="B",
            hypothesis="H",
            experiment_method="m2",
            result={},
            conclusion="success",
            confidence=0.9,
        )
        store.add(low)
        store.add(high)

        results = store.recall_by_confidence(k=2)
        assert results[0].entry_id == "high"
        assert results[1].entry_id == "low"

    def test_get_stats_returns_expected_fields(self):
        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("test-stats", mapper)
        entry = KnowledgeEntry(
            entry_id="e1",
            question="Q",
            hypothesis="H",
            experiment_method="m",
            result={},
            conclusion="success",
            confidence=0.7,
        )
        store.add(entry)
        stats = store.get_stats()
        assert stats["total_entries"] == 1
        assert stats["success_count"] == 1
        assert "avg_confidence" in stats


class TestQuestionGenerator:
    """Test question generation heuristics."""

    def test_generate_from_inconclusive_entry(self):
        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("qg-inconclusive", mapper)
        gen = QuestionGenerator(store)

        entry = KnowledgeEntry(
            entry_id="e1",
            question="为什么结果不明确？",
            hypothesis="可能有干扰",
            experiment_method="test_method",
            result={"var": 0.5},
            conclusion="inconclusive",
            confidence=0.5,
        )
        store.add(entry)

        questions = gen.generate(num_questions=3, inspiration_sources=[entry])
        assert len(questions) == 1
        q = questions[0]
        assert "为什么" in q.question
        assert q.confidence > 0.5

    def test_generate_returns_multiple_from_mixed_sources(self):
        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("qg-mixed", mapper)
        gen = QuestionGenerator(store)

        for i, conf in enumerate([0.5, 0.8, 0.9, 0.4]):
            store.add(
                KnowledgeEntry(
                    entry_id=f"e{i}",
                    question=f"Q{i}",
                    hypothesis=f"H{i}",
                    experiment_method=f"m{i}",
                    result={},
                    conclusion=("inconclusive" if i == 0 else "success" if i < 3 else "failure"),
                    confidence=conf,
                )
            )

        questions = gen.generate(num_questions=5)
        # Should produce at least 2 questions (based on heuristics)
        assert len(questions) >= 2


class TestExperimentDesigner:
    """Test experiment plan generation from questions."""

    def test_design_breath_question(self):
        designer = ExperimentDesigner()
        plan = designer.design(
            question="延长呼吸节律会恢复能量吗？",
            hypothesis="延长 CONTRACT 可以提升能量",
        )
        assert plan.steps[0].tool_name == "adjust_breath_cycle"
        assert "contract_ms" in plan.steps[0].parameters

    def test_design_resonate_question(self):
        designer = ExperimentDesigner()
        plan = designer.design(
            question="与节点 X 共振能带来收益吗？",
            hypothesis="1+1>2",
        )
        assert plan.steps[0].tool_name == "resonate_with_node"

    def test_design_physics_anchor_question(self):
        designer = ExperimentDesigner()
        plan = designer.design(
            question="物理锚还稳定吗？",
            hypothesis="能量漂移应该 < 0.1%",
        )
        assert plan.steps[0].tool_name == "check_physics_anchor"


class TestEndToEndResearch:
    """Integration: full research loop generates and stores knowledge."""

    def test_conduct_research_end_to_end(self):
        from cosmic_mycelium.utils.embeddings import text_to_embedding
        from unittest.mock import patch

        # Setup infant components
        mapper = SemanticMapper(embedding_dim=8)
        store = KnowledgeStore("e2e-test", mapper)
        gen = QuestionGenerator(store)
        designer = ExperimentDesigner()

        # Seed with some history
        seed = KnowledgeEntry(
            entry_id="seed1",
            question="能量下降怎么办？",
            hypothesis="延长 CONTRACT",
            experiment_method="adjust_breath_cycle(contract_ms=150)",
            result={"energy_before": 30, "energy_after": 65},
            conclusion="success",
            confidence=0.85,
        )
        store.add(seed)

        # Generate question
        questions = gen.generate(num_questions=3)
        assert len(questions) >= 1
        first_q = questions[0]

        # Design experiment
        plan = designer.design(first_q.question, first_q.hypothesis)
        assert plan.steps

        # Execute and store
        result_entry = store.execute_experiment(plan)
        assert result_entry.conclusion in ("success", "failure")
        assert result_entry.confidence > 0

        # Verify recall: mock text_to_embedding so the query produces a vector
        # that matches the result_entry's actual embedding, guaranteeing retrieval
        query_snippet = result_entry.question[:10]
        shared_emb = np.array([1.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        result_entry.embedding = shared_emb
        store.vector_index.add(result_entry.entry_id, shared_emb)

        with patch("cosmic_mycelium.utils.embeddings.text_to_embedding", return_value=shared_emb):
            recalled = store.recall_semantic(query_snippet, k=1)
        assert len(recalled) == 1
        assert recalled[0].entry_id == result_entry.entry_id
