# 借鉴 autoresearch 的知识条目数据结构示例
# 用于 Cosmic Mycelium 宝宝的"经验记忆"向量化存储与检索

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time


@dataclass
class KnowledgeEntry:
    """
    借鉴 autoresearch 的知识条目结构，适配宝宝的特征码知识库。

    对应关系：
    - question  → 感知到的态势（"什么情况？"）
    - hypothesis → 特征码的初步判断（"我猜这是 X 模式"）
    - experiment_method → 行动序列（"我打算试试 A→B→C"）
    - result → 物理实情反馈（"实际发生了什么"）
    - conclusion → 是否髓鞘化（"这个路径有效/无效"）
    - confidence → 效能/置信度（"我对这个判断有多大把握"）
    """
    entry_id: str
    question: str                # 宝宝感知到的态势/情境描述
    hypothesis: str              # 宝宝生成的预测或假设（对应 SlimeExplorer 的路径意图）
    experiment_method: str       # 宝宝采取的行动序列（feature_code path）
    result: Dict[str, Any]       # 物理实情反馈（sensor readings, HIC energy, etc.）
    conclusion: str              # 验证结论：success / failure / inconclusive
    confidence: float            # 置信度 [0, 1]，对应突显加权中的 saliency
    created_at: float = field(default_factory=time.time)
    embedding: Optional[Any] = None  # 向量嵌入（np.ndarray），用于相似检索

    def to_feature_code(self) -> str:
        """将此知识条目转换为宝宝的 feature_code 格式（SHA256 前8位）。"""
        import hashlib
        content = f"{self.question}|{self.hypothesis}|{self.experiment_method}"
        return hashlib.sha256(content.encode()).hexdigest()[:8]

    def compute_saliency(self) -> float:
        """根据结论和置信度计算突显度，用于 MyelinationMemory.reinforce()。"""
        base = self.confidence
        if self.conclusion == "success":
            return min(2.0, base * 1.5)  # 成功 + 高置信 = 高突显
        elif self.conclusion == "failure":
            return max(0.5, base * 0.5)  # 失败降低突显，但不完全遗忘
        else:
            return base * 0.8  # inconclusive 中等突显


# 使用示例：
if __name__ == "__main__":
    entry = KnowledgeEntry(
        entry_id="k001",
        question="能量持续下降时，调整呼吸节律能否恢复？",
        hypothesis="延长 CONTRACT 阶段可能提升能量恢复率",
        experiment_method="hic.adjust_duration(contract=0.1, diffuse=0.01)",
        result={"energy_before": 30.0, "energy_after": 65.0, "cycles": 5},
        conclusion="success",
        confidence=0.85,
    )
    print(f"Feature code: {entry.to_feature_code()}")
    print(f"Saliency: {entry.compute_saliency():.2f}")
