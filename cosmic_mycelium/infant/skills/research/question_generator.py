"""
Question Generator — 宝宝的"好奇之心"

基于当前知识库摘要，提出新颖的、可验证的科学问题或假设。
对应 PHASE4_PROPOSAL 二.1: Question Generator

设计灵感: inspirations/autoresearch/hypothesis_prompt_template.txt
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from cosmic_mycelium.infant.knowledge_store import KnowledgeStore, KnowledgeEntry


@dataclass
class GeneratedQuestion:
    """一个问题生成结果。"""
    question: str
    hypothesis: str
    verification_method: str
    success_criteria: str
    confidence: float = 0.5  # 初始置信度
    generated_at: float = field(default_factory=time.time)
    source_entries: list[str] = field(default_factory=list)  # 引用的知识条目ID


class QuestionGenerator:
    """
    自主提出科研问题的模块。

    工作原理：
    1. 从 KnowledgeStore 采样近期条目（按时间或置信度）
    2. 构建"当前知识库摘要"（问题 + 假设的文本集合）
    3. 应用 hypothesis_prompt_template.txt 启发式规则生成新问题
    4. 返回 1-3 个候选问题

    Phase 4.2: 未来可替换为 LLM 调用（通过 InfantTool 接口）
    """

    def __init__(self, knowledge_store: KnowledgeStore):
        self.knowledge = knowledge_store

    def generate(
        self,
        num_questions: int = 3,
        recency_days: float = 7.0,
        inspiration_sources: list[KnowledgeEntry] | None = None,
    ) -> list[GeneratedQuestion]:
        """
        生成新的科学问题。

        Args:
            num_questions: 希望生成的问题数量（实际可能更少）
            recency_days: 仅考虑最近 N 天内的知识条目作为灵感来源
            inspiration_sources: 可选，显式指定灵感来源条目

        Returns:
            GeneratedQuestion 列表（最多 num_questions 个）
        """
        # 1. 获取灵感来源
        if inspiration_sources is None:
            cutoff = time.time() - recency_days * 86400
            recent = [
                e for e in self.knowledge.list_all()
                if e.created_at >= cutoff
            ]
            # 优先选择高置信度条目（成熟知识）与低置信度条目（知识空白）的混合
            high_conf = sorted(
                recent, key=lambda e: e.confidence, reverse=True
            )[:max(1, num_questions * 2)]
            low_conf = sorted(
                recent, key=lambda e: e.confidence
            )[:max(1, num_questions)]
            sources = list({e.entry_id: e for e in high_conf + low_conf}.values())
        else:
            sources = inspiration_sources

        if not sources:
            return []

        # 2. 对每个来源应用启发式规则生成问题
        questions: list[GeneratedQuestion] = []
        for entry in sources[:num_questions]:
            q = self._generate_from_entry(entry)
            if q:
                questions.append(q)

        return questions

    def _generate_from_entry(self, entry: KnowledgeEntry) -> GeneratedQuestion | None:
        """
        基于单个知识条目，应用模板启发式生成一个问题。

        启发式（来自 hypothesis_prompt_template.txt）：
        1. 寻找"张力"或"空白"：当前结论 inconclusive 或 confidence 中等
        2. 提出可验证的问题：可通过实验（工具调用）验证
        3. 给出验证方法和成功标准
        """
        # 启发式 1: 对于 inconclusive 的结论，追问"为什么不确定？"
        if entry.conclusion == "inconclusive":
            question = f"为什么实验「{entry.experiment_method}」的结果不明确？"
            hypothesis = "可能存在未被控制的干扰变量，或测量精度不足。"
            verification = "重复实验 3 次，记录每次 sensor 读数；计算方差。"
            success = "方差 < 0.1，或发现某个传感器的异常模式。"
            confidence = 0.6
        # 启发式 2: 对于低置信度成功，追问"可复现吗？"
        elif entry.confidence < 0.7 and entry.conclusion == "success":
            question = f"「{entry.hypothesis}」的成果能在不同参数下复现吗？"
            hypothesis = "该成功可能依赖于特定的初始条件；改变参数会失效。"
            verification = "调整实验参数（如 duration、threshold）进行 3 次变体实验。"
            success = "超过 50% 的变体仍保持 success 结论。"
            confidence = 0.65
        # 启发式 3: 对于失败，追问"反向操作会怎样？"
        elif entry.conclusion == "failure":
            question = f"如果反向执行「{entry.experiment_method}」，会得到相反结果吗？"
            hypothesis = "失败可能是方向性错误；反向操作可能成功。"
            verification = "执行对称的实验（如 CONTRACT 时间加倍 vs 减半）。"
            success = "反向操作的成功率 > 70%。"
            confidence = 0.55
        # 启发式 4: 高置信度成功 — 探索边界
        elif entry.confidence >= 0.9 and entry.conclusion == "success":
            question = f"「{entry.hypothesis}」的极限在哪里？"
            hypothesis = "当前成功条件可能有一个有效范围，超出范围会失效。"
            verification = "逐步增加/减少关键参数，绘制效能曲线。"
            success = "找到效能下降 50% 的临界点。"
            confidence = 0.75
        # 启发式 5: 成功但置信度中等 — 追问优化空间
        elif entry.conclusion == "success" and entry.confidence >= 0.7:
            question = f"「{entry.experiment_method}」还能做得更好吗？"
            hypothesis = "当前参数可能未达最优，存在调优空间。"
            verification = "在参数附近进行网格搜索，观察成功率变化。"
            success = "找到比当前效能高 10% 以上的参数组合。"
            confidence = 0.7
        else:
            return None

        return GeneratedQuestion(
            question=question,
            hypothesis=hypothesis,
            verification_method=verification,
            success_criteria=success,
            confidence=confidence,
            source_entries=[entry.entry_id],
        )

    def get_status(self) -> dict[str, Any]:
        return {
            "knowledge_entries": len(self.knowledge.list_all()),
            "recent_generation_rate": 0.0,  # TODO
        }
