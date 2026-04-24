"""
Feature Code — 宝宝的可复用"髓鞘化经验"

借鉴 Hermes Skill 的数据结构，但改造为适合"物理锚"哲学的特征码：
- 被物理实情验证过的高价值行为模式
- 可被髓鞘化（强化）或遗忘（弱化）
- 通过触发模式匹配来调用
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


@dataclass
class FeatureCode:
    """
    宝宝的可复用"特征码"——被髓鞘化的成功经验。

    相当于 Hermes 的 Skill，但绑定物理验证：
    - 触发条件基于感知模式（振动频谱、温度梯度等）
    - 行动序列是物理动作参数（呼吸频率调整、能量分配等）
    - 必须经过物理实情指纹验证才能成为高可信度特征码
    """

    # 核心标识
    code_id: str  # 唯一ID（由内容哈希生成）
    name: str  # 人类可读的名称
    description: str  # 描述：这个特征码在什么情况下有用

    # 触发条件（感知模式）
    trigger_patterns: list[str]  # 如 ["high_energy", "vibration_spike"]

    # 行为序列（推荐动作参数）
    action_sequence: list[dict[str, Any]]  # 如 [{"action": "adjust_breath", "factor": 0.8}]

    # 髓鞘化元数据
    success_count: int = 0
    failure_count: int = 0
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    # 物理锚：这个特征码的"可信度"必须经过物理实情检验
    validation_fingerprint: str | None = None  # 关联的物理指纹（任务成功时的状态指纹）

    # Epic 3: 向量语义记忆 — 嵌入缓存
    embedding: np.ndarray | None = None  # 归一化向量，用于语义检索
    cluster_id: int | None = None  # 所属聚类ID（聚类分析后设置）

    def compute_embedding(
        self, semantic_mapper: Any, dim: int | None = None
    ) -> np.ndarray:
        """
        Compute embedding vector for this feature code using SemanticMapper.

        Embeds the concatenated text: "{name} {description} {' '.join(trigger_patterns)}"
        into the same embedding space as SemanticConcept vectors.

        Args:
            semantic_mapper: Initialized SemanticMapper instance
            dim: Optional override for embedding dimension (default: semantic_mapper.embedding_dim)

        Returns:
            Normalized embedding vector (np.ndarray)
        """
        if dim is None:
            dim = getattr(semantic_mapper, "embedding_dim", 16)

        # Build text representation
        text_parts = [self.name, self.description] + self.trigger_patterns
        text = " ".join(filter(None, text_parts))

        from cosmic_mycelium.utils.embeddings import text_to_embedding

        embedding = text_to_embedding(text, dim=dim)

        # Normalize to unit length for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        self.embedding = embedding
        return embedding

    def efficacy(self) -> float:
        """
        计算特征码的"效能"（成功率）。

        返回 [0, 1] 区间，未经验证返回 0.5（中性）。
        随着使用次数增加，效能评估更可靠。
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # 未经验证，保持中立
        return self.success_count / total

    def reinforce(self, success: bool, saliency: float = 1.0) -> None:
        """
        Reinforce or weaken this feature code based on outcome, weighted by saliency.

        Args:
            success: True if the action led to a successful outcome.
            saliency: Saliency factor (0.1 ~ 2.0). High-saliency events (near energy red line,
                      strong resonance) create deeper memories. Default 1.0.
        """
        # Base reinforcement amount (1.0 = one unit of experience)
        increment = 1.0 * saliency
        if success:
            self.success_count += increment
        else:
            self.failure_count += increment
        self.last_used = time.time()

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化存储）。"""
        data = asdict(self)
        # Convert embedding ndarray to list for JSON serialization
        if self.embedding is not None:
            data["embedding"] = self.embedding.tolist()
        else:
            data["embedding"] = None
        # cluster_id is included via asdict already (since it's a field)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureCode:
        """从字典反序列化。"""
        emb_data = data.pop("embedding", None)
        fc = cls(**data)
        if emb_data is not None:
            fc.embedding = np.array(emb_data, dtype=np.float32)
        return fc

    @classmethod
    def generate_id(cls, name: str, trigger_patterns: list[str]) -> str:
        """
        基于内容和触发模式生成唯一ID。

        使用 SHA256 截断前12字符，保证可重复性和紧凑性。
        """
        content = f"{name}:{sorted(trigger_patterns)}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]
