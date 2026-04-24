"""
Feature Manager — 宝宝的"髓鞘化记忆"持久化管理器

借鉴 Hermes Skill Manager 的设计，但适配到我们的物理锚哲学：
- 特征码 = 被物理实情验证过的成功经验
- 存储于本地文件系统（~/.cosmic_mycelium/{infant_id}/features/）
- 通过触发模式倒排索引快速检索
- 支持自动遗忘低效能特征码
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from cosmic_mycelium.common.feature_code import FeatureCode
from cosmic_mycelium.infant.core.semantic_vector_index import SemanticVectorIndex


class FeatureManager:
    """
    宝宝的特征码管理器——它的"髓鞘化记忆"的持久化实现。

    借鉴 Hermes Skill Manager，关键差异：
    - Hermes: 技能 = 提示词模板 + 工具调用序列
    - 我们: 特征码 = 触发模式 + 物理动作参数 + 物理指纹验证
    """

    def __init__(
        self,
        infant_id: str,
        storage_path: Path | None = None,
        semantic_mapper: Any = None,
    ):
        """
        初始化特征码管理器。

        Args:
            infant_id: 婴儿节点ID
            storage_path: 可选的持久化存储路径（默认: ~/.cosmic_mycelium/{infant_id}/features）
            semantic_mapper: SemanticMapper 实例，用于计算特征码 embedding（Epic 3）
        """
        self.infant_id = infant_id
        self.semantic_mapper = semantic_mapper

        # 存储路径：用户主目录下的隐藏文件夹
        if storage_path is None:
            storage_path = Path.home() / ".cosmic_mycelium" / infant_id / "features"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 向量索引存储路径
        self.index_path = self.storage_path.parent / "vector_index"
        self.index_path.mkdir(parents=True, exist_ok=True)

        # 内存中的特征码索引
        self.features: dict[str, FeatureCode] = {}

        # 触发模式倒排索引（模式 → 特征码ID列表）
        self.pattern_index: dict[str, list[str]] = defaultdict(list)

        # Epic 3: 向量语义索引
        # embedding_dim 来自 semantic_mapper 或默认 16
        dim = getattr(semantic_mapper, "embedding_dim", 16) if semantic_mapper else 16
        self.vector_index = SemanticVectorIndex(dim=dim, index_path=self.index_path)

        # 加载已有特征码
        self._load_all()

        # Meta-cognitive: pause adaptation during meta-suspend (IMP-04)
        self.pause_adaptation: bool = False

        # 线程安全锁
        self._lock = RLock()

    def _load_all(self) -> None:
        """从磁盘加载所有特征码并重建索引。"""
        if not self.storage_path.exists():
            return

        loaded = 0
        for f in self.storage_path.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                    fc = FeatureCode.from_dict(data)
                    self.features[fc.code_id] = fc
                    # 重建倒排索引
                    for pattern in fc.trigger_patterns:
                        self.pattern_index[pattern].append(fc.code_id)
                    loaded += 1
            except Exception as e:
                print(f"[FeatureManager] 加载特征码失败 {f}: {e}")

        if loaded > 0:
            print(f"[FeatureManager] 加载了 {loaded} 个特征码 from {self.storage_path}")

        # Epic 3: rebuild vector index from loaded feature codes
        self._rebuild_vector_index()
        # Load cluster assignments
        self._load_cluster_assignments()

    def _rebuild_vector_index(self) -> None:
        """Rebuild the semantic vector index from all loaded feature codes."""
        self.vector_index.clear()
        if self.semantic_mapper is None:
            return  # Cannot compute embeddings without mapper

        for fc in self.features.values():
            if fc.embedding is None:
                fc.compute_embedding(self.semantic_mapper)
            self.vector_index.add(fc.code_id, fc.embedding)

        # Persist index after rebuild
        try:
            self.vector_index.save(self.index_path)
        except Exception as e:
            print(f"[FeatureManager] 保存向量索引失败: {e}")

    def _save_one(self, fc: FeatureCode) -> None:
        """保存单个特征码到磁盘（JSON格式）。"""
        filepath = self.storage_path / f"{fc.code_id}.json"
        try:
            with open(filepath, "w") as f:
                json.dump(fc.to_dict(), f, indent=2)
        except Exception as e:
            print(f"[FeatureManager] 保存特征码失败 {fc.code_id}: {e}")

    def create_or_update(
        self,
        name: str,
        description: str,
        trigger_patterns: list[str],
        action_sequence: list[dict[str, Any]],
        validation_fingerprint: str | None = None,
    ) -> FeatureCode:
        """
        创建新特征码，或更新已有特征码。

        这是 Hermes "从经验中创造技能" 的对应实现。

        Args:
            name: 特征码名称（人类可读）
            description: 描述（什么情况下有用）
            trigger_patterns: 触发模式列表（感知模式关键词）
            action_sequence: 推荐的行为序列（动作参数列表）
            validation_fingerprint: 物理指纹（任务成功时的状态指纹，可选）

        Returns:
            创建或更新后的 FeatureCode 实例
        """
        with self._lock:
            code_id = FeatureCode.generate_id(name, trigger_patterns)

            if code_id in self.features:
                # 更新已有特征码：合并行为序列，保留历史统计
                fc = self.features[code_id]
                fc.description = description
                # 新经验合并到行动序列（保留最近10步）
                fc.action_sequence = (action_sequence + fc.action_sequence)[:10]
                if validation_fingerprint:
                    fc.validation_fingerprint = validation_fingerprint
                action = "更新"
            else:
                # 创建新特征码
                fc = FeatureCode(
                    code_id=code_id,
                    name=name,
                    description=description,
                    trigger_patterns=trigger_patterns,
                    action_sequence=action_sequence,
                    validation_fingerprint=validation_fingerprint,
                )
                self.features[code_id] = fc
                # 更新倒排索引
                for pattern in trigger_patterns:
                    self.pattern_index[pattern].append(code_id)
                action = "创建"

            self._save_one(fc)
            # Epic 3: compute embedding and add to vector index
            if self.semantic_mapper is not None:
                fc.compute_embedding(self.semantic_mapper)
                self.vector_index.add(fc.code_id, fc.embedding)
                # Persist index incrementally
                try:
                    self.vector_index.save(self.index_path)
                except Exception as e:
                    print(f"[FeatureManager] 保存向量索引失败: {e}")

            print(f"[FeatureManager] {action}特征码: {name} ({code_id})")
            return fc

    def match(
        self, perceived_patterns: list[str], min_efficacy: float = 0.3
    ) -> list[FeatureCode]:
        """
        根据当前感知到的模式，匹配最适用的特征码。

        借鉴 Hermes 的"触发技能"机制。

        Args:
            perceived_patterns: 当前感知到的模式关键词列表
            min_efficacy: 最小效能阈值（低于此值的特征码不匹配）

        Returns:
            匹配的特征码列表，按（效能 × 时间衰减）排序
        """
        with self._lock:
            matched_ids = set()
            for pattern in perceived_patterns:
                if pattern in self.pattern_index:
                    matched_ids.update(self.pattern_index[pattern])

            candidates = []
            for code_id in matched_ids:
                fc = self.features.get(code_id)
                if fc and fc.efficacy() >= min_efficacy:
                    candidates.append(fc)

            # 按效能 × 时间衰减排序（越近期使用的权重越高）
            # 衰减因子：每过一天，权重乘以 0.9
            candidates.sort(
                key=lambda fc: fc.efficacy() * (0.9 ** ((time.time() - fc.last_used) / 86400)),
                reverse=True,
            )

            return candidates

    # ── Epic 3: Vector Semantic Memory ───────────────────────────────────────

    def recall_semantic(self, query: str, k: int = 5) -> list[FeatureCode]:
        """
        Semantic similarity search over feature codes.

        Embeds the query text using the same embedding space as feature codes
        and returns the k most similar feature codes by cosine similarity.

        Args:
            query: Free-text query describing desired trigger patterns
            k: Number of results to return

        Returns:
            List of FeatureCode objects sorted by similarity descending
        """
        if self.semantic_mapper is None or self.vector_index is None:
            return []

        with self._lock:
            # Compute query embedding using same method as feature codes
            from cosmic_mycelium.utils.embeddings import text_to_embedding

            # Use same dim as index
            dim = self.vector_index.dim
            query_vec = text_to_embedding(query, dim=dim)
            # Normalize
            norm = np.linalg.norm(query_vec)
            if norm > 0:
                query_vec = query_vec / norm

            results = self.vector_index.search(query_vec, k=k)

            # Record metric
            from cosmic_mycelium.utils.metrics import MetricsCollector

            if results:
                MetricsCollector.record_recall_hit(self.infant_id)
            else:
                MetricsCollector.record_recall_miss(self.infant_id)

            return [self.features[fid] for fid, _ in results if fid in self.features]

    def recall_by_embedding(self, vector: np.ndarray, k: int = 5) -> list[FeatureCode]:
        """
        Direct vector-based similarity search.

        Args:
            vector: Embedding vector (will be normalized)
            k: Number of results

        Returns:
            List of FeatureCode objects sorted by similarity
        """
        if self.vector_index is None:
            return []

        with self._lock:
            results = self.vector_index.search(vector, k=k)
            return [self.features[fid] for fid, _ in results if fid in self.features]

    def cluster_active_features(
        self, min_samples: int = 3, eps: float = 0.3
    ) -> dict[int, list[FeatureCode]]:
        """
        Cluster active feature codes by embedding similarity using DBSCAN-like density.

        Requires at least `min_samples` points within `eps` cosine distance to form a cluster.
        Labels clusters 0, 1, 2, ...; -1 denotes noise (unclustered).

        Args:
            min_samples: Minimum points to form a cluster
            eps: Maximum cosine distance between points in a cluster (1 - similarity)

        Returns:
            Dict mapping cluster_id → list of FeatureCode in that cluster
        """
        with self._lock:
            if self.semantic_mapper is None or len(self.features) < min_samples:
                return {}

            # Collect all embeddings
            ids = []
            vectors = []
            for fc in self.features.values():
                if fc.embedding is None and self.semantic_mapper:
                    fc.compute_embedding(self.semantic_mapper)
                if fc.embedding is not None:
                    ids.append(fc.code_id)
                    vectors.append(fc.embedding)

            if len(vectors) < min_samples:
                return {}

            arr = np.stack(vectors).astype(np.float32)  # shape (N, dim)

            # Simple DBSCAN using cosine distance (1 - cosine_sim)
            # Since FAISS doesn't have DBSCAN built-in, we implement a basic version:
            # For each point, count neighbors within eps; if enough, it's a core point.
            # Then group connected core points.
            from collections import deque

            n = len(arr)
            # Normalize
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            arr_norm = arr / (norms + 1e-8)

            # Compute pairwise cosine similarities (efficient matrix multiply)
            sims = arr_norm @ arr_norm.T  # (N, N)
            dists = 1.0 - sims  # cosine distance

            visited = [False] * n
            labels = [-1] * n
            cluster_id = 0

            for i in range(n):
                if visited[i]:
                    continue
                # Find neighbors within eps
                neighbors = np.where(dists[i] <= eps)[0].tolist()
                if len(neighbors) < min_samples:
                    visited[i] = True
                    continue  # noise

                # Start new cluster
                queue = deque(neighbors)
                visited[i] = True
                labels[i] = cluster_id

                while queue:
                    j = queue.popleft()
                    if not visited[j]:
                        visited[j] = True
                        labels[j] = cluster_id
                        # Check if j is also a core point
                        j_neighbors = np.where(dists[j] <= eps)[0].tolist()
                        if len(j_neighbors) >= min_samples:
                            queue.extend(n for n in j_neighbors if not visited[n])

                cluster_id += 1

            # Group feature codes by cluster
            clusters: dict[int, list[FeatureCode]] = {}
            for idx, cid in enumerate(labels):
                if cid >= 0:
                    clusters.setdefault(cid, []).append(self.features[ids[idx]])

            # Assign cluster labels to feature codes (store on FeatureCode)
            for idx, cid in enumerate(labels):
                if cid >= 0:
                    self.features[ids[idx]].cluster_id = cid

            # Generate cluster labels lazily via get_cluster_label()
            # Persist cluster assignments
            self._save_cluster_assignments()

            return clusters

    def get_cluster_label(self, cluster_id: int) -> str:
        """
        Generate a human-readable label for a cluster.

        Uses the most frequent significant words from feature names/descriptions.
        """
        if cluster_id not in self._cluster_members():
            return f"cluster_{cluster_id}"

        members = self._cluster_members()[cluster_id]
        # Collect words
        words: list[str] = []
        for fc in members:
            words.extend(fc.name.lower().split())
            words.extend(fc.description.lower().split())
        # Simple: take top 3 most common non-stopwords
        from collections import Counter

        stopwords = {"the", "and", "or", "for", "in", "on", "with", "to", "a", "an", "of", "is", "are"}
        filtered = [w for w in words if w not in stopwords and len(w) > 2]
        if not filtered:
            return f"cluster_{cluster_id}"
        common = Counter(filtered).most_common(3)
        return " ".join(word for word, _ in common)

    def _cluster_members(self) -> dict[int, list[FeatureCode]]:
        """Rebuild cluster members dict from feature code cluster_id assignments."""
        members: dict[int, list[FeatureCode]] = {}
        for fc in self.features.values():
            if hasattr(fc, "cluster_id") and fc.cluster_id is not None:
                members.setdefault(fc.cluster_id, []).append(fc)
        return members

    def _save_cluster_assignments(self) -> None:
        """Save cluster assignments to disk (sidecar file)."""
        assignments = {}
        for fc in self.features.values():
            if hasattr(fc, "cluster_id") and fc.cluster_id is not None:
                assignments[fc.code_id] = int(fc.cluster_id)
        path = self.storage_path / "clusters.json"
        try:
            with open(path, "w") as f:
                json.dump(assignments, f, indent=2)
        except Exception as e:
            print(f"[FeatureManager] 保存聚类失败: {e}")

    def _load_cluster_assignments(self) -> None:
        """Load cluster assignments from disk."""
        path = self.storage_path / "clusters.json"
        if not path.exists():
            return
        try:
            with open(path, "r") as f:
                assignments = json.load(f)
            for code_id, cid in assignments.items():
                if code_id in self.features:
                    self.features[code_id].cluster_id = cid
        except Exception as e:
            print(f"[FeatureManager] 加载聚类失败: {e}")

    def get(self, code_id: str) -> FeatureCode | None:
        """获取单个特征码。"""
        with self._lock:
            return self.features.get(code_id)

    def reinforce(
        self,
        code_id: str,
        success: bool,
        saliency: float = 1.0,
    ) -> None:
        """
        Reinforce or weaken a feature code, with saliency weighting.

        Args:
            code_id: Feature code ID
            success: True if the action succeeded, False if it failed
            saliency: Saliency factor (default 1.0). High-saliency events cause stronger
                      reinforcement (e.g., near energy red line, low confidence).
        """
        # Meta-cognitive guard: skip adaptation during meta-suspend (IMP-04)
        if self.pause_adaptation:
            return

        with self._lock:
            if code_id in self.features:
                fc = self.features[code_id]
                fc.reinforce(success, saliency=saliency)
                self._save_one(fc)

                # Auto-forget if efficacy low and experienced
                if (
                    fc.efficacy() < 0.1
                    and fc.success_count + fc.failure_count > 10
                ):
                    self._forget(code_id)

    def _forget(self, code_id: str) -> None:
        """遗忘一个特征码（从内存和磁盘删除）。"""
        with self._lock:
            if code_id in self.features:
                fc = self.features[code_id]
                # 从倒排索引中移除
                for pattern in fc.trigger_patterns:
                    if code_id in self.pattern_index[pattern]:
                        self.pattern_index[pattern].remove(code_id)
                # 删除文件
                filepath = self.storage_path / f"{code_id}.json"
                if filepath.exists():
                    filepath.unlink()
                # 从内存移除
                del self.features[code_id]
                print(f"[FeatureManager] 遗忘低效特征码: {fc.name} ({code_id})")

    def list_all(self) -> list[FeatureCode]:
        """列出所有特征码，按效能排序。"""
        with self._lock:
            return sorted(
                self.features.values(), key=lambda fc: fc.efficacy(), reverse=True
            )

    def get_stats(self) -> dict[str, Any]:
        """获取管理器统计信息。"""
        with self._lock:
            total = len(self.features)
            high_efficacy = sum(1 for fc in self.features.values() if fc.efficacy() >= 0.7)
            low_efficacy = sum(1 for fc in self.features.values() if fc.efficacy() <= 0.3)

            return {
                "total_features": total,
                "high_efficacy_count": high_efficacy,
                "low_efficacy_count": low_efficacy,
                "storage_path": str(self.storage_path),
                "patterns_indexed": len(self.pattern_index),
            }
