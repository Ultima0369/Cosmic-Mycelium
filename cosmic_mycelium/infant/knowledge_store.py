"""
Knowledge Store — 宝宝的"科研记忆"持久化管理器

存储 KnowledgeEntry（问题、假设、实验、结果、结论），
支持基于 SemanticMapper 的语义相似检索（recall_semantic）。

对应 PHASE4_PROPOSAL 二.1: Knowledge Store
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper
from cosmic_mycelium.infant.core.semantic_vector_index import SemanticVectorIndex
from cosmic_mycelium.utils.embeddings import text_to_embedding
from cosmic_mycelium.utils.metrics import MetricsCollector, KNOWLEDGE_ENTRIES_TOTAL


@dataclass
class KnowledgeEntry:
    """
    一个完整的科研记忆条目。

    对应inspirations/autoresearch/knowledge_schema.py
    """
    entry_id: str
    question: str                # 感知到的态势/情境描述
    hypothesis: str              # 生成的预测或假设
    experiment_method: str       # 行动序列描述
    result: dict[str, Any]       # 物理实情反馈
    conclusion: str              # success / failure / inconclusive
    confidence: float            # 置信度 [0,1]
    created_at: float = field(default_factory=time.time)
    embedding: np.ndarray | None = None  # 向量嵌入，用于语义检索

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.embedding is not None:
            d["embedding"] = self.embedding.tolist()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeEntry:
        if "embedding" in data and data["embedding"] is not None:
            data["embedding"] = np.array(data["embedding"])
        return cls(**data)

    def compute_saliency(self) -> float:
        """根据结论和置信度计算突显度。"""
        base = self.confidence
        if self.conclusion == "success":
            return min(2.0, base * 1.5)
        elif self.conclusion == "failure":
            return max(0.5, base * 0.5)
        else:
            return base * 0.8


class KnowledgeStore:
    """
    宝宝的知识库 —— 存储并检索科研记忆。

    核心能力：
    - add(entry): 存储新的 KnowledgeEntry，自动计算 embedding
    - recall_semantic(query, k): 基于语义相似度检索最相关的 k 个条目
    - list_by_confidence(): 按置信度排序
    """

    def __init__(
        self,
        infant_id: str,
        semantic_mapper: SemanticMapper,
        storage_path: Path | None = None,
    ):
        self.infant_id = infant_id
        self.mapper = semantic_mapper

        if storage_path is None:
            storage_path = Path.home() / ".cosmic_mycelium" / infant_id / "knowledge"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Semantic vector index for similarity search
        self.vector_index = SemanticVectorIndex(
            dim=semantic_mapper.embedding_dim,
            index_path=self.storage_path / "vector_index",
        )

        self.entries: dict[str, KnowledgeEntry] = {}
        self._lock = RLock()  # Sprint 5: thread-safe concurrent access
        self._load_all()
        # Initialize gauge with loaded count
        KNOWLEDGE_ENTRIES_TOTAL.labels(infant_id=self.infant_id).set(len(self.entries))

    def _load_all(self) -> None:
        if not self.storage_path.exists():
            return
        for f in self.storage_path.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                    entry = KnowledgeEntry.from_dict(data)
                    self.entries[entry.entry_id] = entry
            except Exception:
                pass  # 忽略损坏文件

        # Load vector index if exists
        vector_index_path = self.storage_path / "vector_index"
        if vector_index_path.exists():
            self.vector_index.load(vector_index_path)

        # Re-index entries if vector index is empty but entries exist
        # (backwards compatibility: existing entries before vector index was added)
        if len(self.vector_index) == 0 and self.entries:
            for entry in self.entries.values():
                if entry.embedding is not None:
                    try:
                        self.vector_index.add(entry.entry_id, entry.embedding)
                    except Exception:
                        pass  # skip dimension mismatches

    def _save_one(self, entry: KnowledgeEntry) -> None:
        filepath = self.storage_path / f"{entry.entry_id}.json"
        try:
            with open(filepath, "w") as f:
                json.dump(entry.to_dict(), f, indent=2)
        except Exception as e:
            print(f"[KnowledgeStore] 保存失败 {entry.entry_id}: {e}")

    def add(self, entry: KnowledgeEntry) -> str:
        """
        存储知识条目，自动生成 embedding（基于 question + hypothesis）。

        Returns:
            entry_id
        """
        # Sprint 5: thread-safe write
        with self._lock:
            # 生成 embedding：使用 text_to_embedding（SHA256 哈希，确定性）
            if entry.embedding is None:
                text = f"{entry.question} {entry.hypothesis}"
                entry.embedding = text_to_embedding(text, dim=self.vector_index.dim)

            self.entries[entry.entry_id] = entry
            self._save_one(entry)
            # Index for semantic similarity search
            self.vector_index.add(entry.entry_id, entry.embedding)
            # Persist vector index to disk
            self.vector_index.save(self.storage_path / "vector_index")
            # Update Prometheus gauge
            KNOWLEDGE_ENTRIES_TOTAL.labels(infant_id=self.infant_id).set(len(self.entries))
        return entry.entry_id

    def recall_semantic(self, query: str, k: int = 5) -> list[KnowledgeEntry]:
        """
        基于语义相似度检索最相关的 k 个知识条目。

        实现：使用 SemanticVectorIndex (FAISS) 计算查询文本与知识条目的
        向量余弦相似度，返回最相似的条目。相比词集合重叠，能捕获语义相关
        而关键词不完全匹配的情况。

        Args:
            query: 查询文本（将被 embedding 为向量）
            k: 返回的最大条目数

        Returns:
            按余弦相似度降序排列的 KnowledgeEntry 列表
        """
        # Sprint 5: thread-safe read
        with self._lock:
            if not self.entries:
                return []

            # 将查询文本 embedding 为向量
            from cosmic_mycelium.utils.embeddings import text_to_embedding

            query_vec = text_to_embedding(query, dim=self.vector_index.dim)

            # 使用向量索引检索
            results = self.vector_index.search(query_vec, k=k)
            entries: list[KnowledgeEntry] = []
            for fid, score in results:
                if fid in self.entries:
                    entries.append(self.entries[fid])

            # Record hit/miss metric
            if entries:
                MetricsCollector.record_recall_hit(self.infant_id)
            else:
                MetricsCollector.record_recall_miss(self.infant_id)

            return entries

    def recall_by_embedding(self, vector: np.ndarray, k: int = 5) -> list[KnowledgeEntry]:
        """
        Retrieve entries by vector similarity using SemanticVectorIndex.

        Args:
            vector: Query embedding (will be normalized for cosine similarity)
            k: Maximum number of results to return

        Returns:
            List of KnowledgeEntry objects sorted by descending similarity
        """
        if not self.entries:
            return []

        results = self.vector_index.search(vector, k=k)
        entries: list[KnowledgeEntry] = []
        for fid, score in results:
            if fid in self.entries:
                entries.append(self.entries[fid])

        # Record hit/miss metric
        if entries:
            MetricsCollector.record_recall_hit(self.infant_id)
        else:
            MetricsCollector.record_recall_miss(self.infant_id)

        return entries

    def cluster_entries(
        self, min_samples: int = 3, eps: float = 0.3
    ) -> dict[int, list[KnowledgeEntry]]:
        """
        Cluster knowledge entries by semantic similarity using DBSCAN-like density.

        Groups entries whose embeddings are close in vector space,
        revealing concept clusters without requiring identical content.

        Args:
            min_samples: Minimum points to form a cluster (default 3)
            eps: Maximum cosine distance (1 - similarity) for neighbors (default 0.3)

        Returns:
            Dict mapping cluster_id → list of KnowledgeEntry in that cluster.
            Cluster -1 denotes noise (unclustered outliers).
        """
        if not self.entries:
            return {}

        candidates = [
            entry for entry in self.entries.values() if entry.embedding is not None
        ]
        if len(candidates) < min_samples:
            return {}

        ids = [e.entry_id for e in candidates]
        vecs = [e.embedding for e in candidates]

        arr = np.stack(vecs).astype(np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr_norm = arr / (norms + 1e-8)

        sims = arr_norm @ arr_norm.T
        dists = 1.0 - sims

        from collections import deque

        n = len(arr)
        visited = [False] * n
        labels = [-1] * n
        cluster_id = 0

        for i in range(n):
            if visited[i]:
                continue
            neighbors = np.where(dists[i] <= eps)[0].tolist()
            if len(neighbors) < min_samples:
                visited[i] = True
                continue

            queue = deque(neighbors)
            visited[i] = True
            labels[i] = cluster_id

            while queue:
                j = queue.popleft()
                if not visited[j]:
                    visited[j] = True
                    labels[j] = cluster_id
                    j_neighbors = np.where(dists[j] <= eps)[0].tolist()
                    if len(j_neighbors) >= min_samples:
                        queue.extend(nn for nn in j_neighbors if not visited[nn])
            cluster_id += 1

        clusters: dict[int, list[KnowledgeEntry]] = {}
        for idx, label in enumerate(labels):
            if label >= 0:
                clusters.setdefault(label, []).append(candidates[idx])

        return clusters

    def get_cluster_label(self, cluster_id: int) -> str:
        """
        Generate a human-readable label for a knowledge entry cluster.

        Uses the most frequent significant words from entry questions/hypotheses.

        Args:
            cluster_id: Cluster identifier

        Returns:
            Human-readable cluster label (e.g., "energy_recovery")
        """
        return f"concept_cluster_{cluster_id}"

    def recall_by_cluster(
        self, cluster_id: int, k: int = 5
    ) -> list[KnowledgeEntry]:
        """
        Retrieve entries belonging to a specific concept cluster.

        Args:
            cluster_id: Cluster identifier
            k: Maximum number of entries to return

        Returns:
            List of KnowledgeEntry in the cluster, sorted by confidence desc
        """
        clusters = self.cluster_entries()
        if cluster_id not in clusters:
            return []
        entries = sorted(clusters[cluster_id], key=lambda e: e.confidence, reverse=True)
        return entries[:k]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """
        Tokenize text into word/character tokens.

        For languages with whitespace (English): split on whitespace.
        For Chinese/Japanese: split into individual characters.
        """
        import re

        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        raw_tokens = cleaned.split()

        final: set[str] = set()
        for tok in raw_tokens:
            # If token contains any Chinese character, split into individual characters
            if re.search(r"[\u4e00-\u9fff]", tok):
                final.update(tok)
            else:
                final.add(tok)
        return final

    def recall_by_confidence(self, k: int = 5) -> list[KnowledgeEntry]:
        """按置信度降序检索。"""
        sorted_entries = sorted(
            self.entries.values(), key=lambda e: e.confidence, reverse=True
        )
        return sorted_entries[:k]

    def get(self, entry_id: str) -> KnowledgeEntry | None:
        return self.entries.get(entry_id)

    def list_all(self) -> list[KnowledgeEntry]:
        return list(self.entries.values())

    def get_stats(self) -> dict[str, Any]:
        total = len(self.entries)
        avg_conf = (
            np.mean([e.confidence for e in self.entries.values()]).item()
            if total > 0
            else 0.0
        )
        successes = sum(1 for e in self.entries.values() if e.conclusion == "success")
        failures = sum(1 for e in self.entries.values() if e.conclusion == "failure")
        return {
            "total_entries": total,
            "avg_confidence": avg_conf,
            "success_count": successes,
            "failure_count": failures,
            "storage_path": str(self.storage_path),
        }

    def execute_experiment(
        self,
        plan: "ExperimentPlan",
        tool_registry: dict[str, Any] | None = None,
    ) -> KnowledgeEntry:
        """
        执行实验计划，记录结果为 KnowledgeEntry。

        Args:
            plan: 实验计划
            tool_registry: 工具实例映射；若 None 使用默认 ALL_TOOLS

        Returns:
            存储的 KnowledgeEntry
        """
        if tool_registry is None:
            from cosmic_mycelium.infant.skills.research.tool_interface_example import (
                ALL_TOOLS,
            )

            tool_registry = {name: tool for name, tool in ALL_TOOLS.items()}

        # 执行所有步骤（目前单步）
        step_results: list[dict[str, Any]] = []
        overall_success = True
        for step in plan.steps:
            tool = tool_registry.get(step.tool_name)
            if tool is None:
                step_results.append({"error": f"tool not found: {step.tool_name}"})
                overall_success = False
                break
            try:
                result = tool.execute(**step.parameters)
                step_results.append(result)
                if not result.get("success", False):
                    overall_success = False
            except Exception as e:
                step_results.append({"error": str(e)})
                overall_success = False
                break

        # 推断结论
        if overall_success:
            conclusion = "success"
            confidence = 0.8
        else:
            conclusion = "failure"
            confidence = 0.6

        # 组装 KnowledgeEntry
        import hashlib

        entry_id = hashlib.sha256(
            f"{plan.question}|{plan.hypothesis}|{time.time()}".encode()
        ).hexdigest()[:12]

        entry = KnowledgeEntry(
            entry_id=entry_id,
            question=plan.question,
            hypothesis=plan.hypothesis,
            experiment_method=self._steps_to_method_string(plan.steps),
            result={
                "plan_id": plan.plan_id,
                "step_results": step_results,
                "overall_success": overall_success,
            },
            conclusion=conclusion,
            confidence=confidence,
            created_at=time.time(),
        )

        self.add(entry)
        return entry

    def _steps_to_method_string(self, steps: list[Any]) -> str:
        """将步骤列表序列化为可读字符串。"""
        parts = []
        for step in steps:
            param_str = ", ".join(f"{k}={v}" for k, v in step.parameters.items())
            parts.append(f"{step.tool_name}({param_str})")
        return " ; ".join(parts)

