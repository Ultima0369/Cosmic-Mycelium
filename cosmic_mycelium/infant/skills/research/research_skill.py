"""
Research Skill — 将科研循环封装为可插拔技能

对应 Epic 1 的 QuestionGenerator + ExperimentDesigner + KnowledgeStore 集成。
"""

from __future__ import annotations

import time
from typing import Any

from cosmic_mycelium.infant.knowledge_store import KnowledgeStore
from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext, SkillExecutionError
from cosmic_mycelium.infant.skills.research.experiment_designer import ExperimentDesigner
from cosmic_mycelium.infant.skills.research.question_generator import QuestionGenerator


class ResearchSkill(InfantSkill):
    """
    自主科研技能 — 实现完整的提出假设→设计实验→执行→学习的闭环。

    依赖：
    - knowledge_store (必选): KnowledgeEntry 持久化存储
    - (未来) semantic_mapper: 语义检索增强

    配置参数（通过 execute() 的 params 传入）：
    - num_questions: 生成问题数量（默认 1）
    - recency_days: 知识窗口（默认 30.0）
    - bootstrap: 是否执行自检（默认 False）
    """

    name = "research"
    version = "1.0.0"
    description = "Autonomous research loop: question → experiment → knowledge"
    dependencies = []  # research 是顶层技能，无依赖
    parallelism_policy = ParallelismPolicy.ISOLATED  # Sprint 5: KnowledgeStore now thread-safe

    def __init__(self, knowledge_store: KnowledgeStore | None = None):
        self.knowledge = knowledge_store
        self.question_generator: QuestionGenerator | None = None
        self.experiment_designer: ExperimentDesigner | None = None
        self._initialized = False
        self._last_execution: float = 0.0
        self._execution_count: int = 0

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def initialize(self, context: SkillContext) -> None:
        """
        初始化 research 技能。

        需要 KnowledgeStore 可用，否则抛出异常。
        """
        if self.knowledge is None:
            # 延迟注入：从 SiliconInfant 获取（将在 main.py 中处理）
            # 这里先标记未就绪， execute 时会检查
            pass
        else:
            self.question_generator = QuestionGenerator(self.knowledge)
            self.experiment_designer = ExperimentDesigner()
        self._initialized = True

    def can_activate(self, context: SkillContext) -> bool:
        """
        研究技能激活条件：
        - HIC 未悬置（由 lifecycle manager 保证）
        - 能量 > 50（避免消耗生存能量）
        - 距离上次执行至少 10 周期（避免过度研究）
        - KnowledgeStore 已就绪
        """
        if not self._initialized:
            return False
        if self.knowledge is None:
            return False
        if context.energy_available < 50:
            return False
        # 冷却期：至少间隔 10 周期
        if context.cycle_count - self._last_execution < 10:
            return False
        return True

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行一个微型研究周期。

        Args:
            params: 可选参数
                - num_questions: 生成问题数量（默认 1）
                - recency_days: 知识窗口（默认 30.0）
                - force_bootstrap: 是否强制自检（默认 False）

        Returns:
            {
                "executed": bool,
                "question": str | None,
                "conclusion": str | None,
                "confidence": float | None,
                "error": str | None,
            }
        """
        if not self._initialized or self.question_generator is None:
            raise SkillExecutionError("ResearchSkill not properly initialized")

        try:
            # Bootstrap: 知识库为空时执行自检
            if params.get("force_bootstrap") or self.knowledge.get_stats()["total_entries"] == 0:
                return self._run_bootstrap()

            # 正常研究循环
            num_q = params.get("num_questions", 1)
            recency = params.get("recency_days", 30.0)

            questions = self.question_generator.generate(
                num_questions=num_q,
                recency_days=recency,
            )
            if not questions:
                return {"executed": False, "reason": "no_questions_generated"}

            q = questions[0]
            plan = self.experiment_designer.design(q.question, q.hypothesis)
            entry = self.knowledge.execute_experiment(plan)

            self._last_execution = context.cycle_count if (context := params.get("_context")) else time.time()
            self._execution_count += 1

            return {
                "executed": True,
                "question": q.question,
                "hypothesis": q.hypothesis,
                "conclusion": entry.conclusion,
                "confidence": entry.confidence,
                "entry_id": entry.entry_id,
            }
        except Exception as e:
            raise SkillExecutionError(f"Research cycle failed: {e}") from e

    def _run_bootstrap(self) -> dict[str, Any]:
        """执行启动自检实验（KnowledgeStore 为空时）。"""
        if self.question_generator is None or self.experiment_designer is None:
            raise SkillExecutionError("Not initialized")
        bootstrap_question = "调整呼吸节律对能量恢复有何影响？"
        bootstrap_hypothesis = "延长 CONTRACT 可能提升能量恢复率"
        plan = self.experiment_designer.design(bootstrap_question, bootstrap_hypothesis)
        entry = self.knowledge.execute_experiment(plan)
        self._last_execution = time.time()
        self._execution_count += 1
        return {
            "executed": True,
            "question": bootstrap_question,
            "hypothesis": bootstrap_hypothesis,
            "conclusion": entry.conclusion,
            "confidence": entry.confidence,
            "entry_id": entry.entry_id,
            "bootstrap": True,
        }

    # -------------------------------------------------------------------------
    # Resource Usage
    # -------------------------------------------------------------------------

    def get_resource_usage(self) -> dict[str, float]:
        """
        返回技能资源消耗估算。

        研究技能消耗：
        - 能量: ~5 单位（实验执行成本）
        - 时间: ~0.1s（实验执行时长）
        - 内存: ~10MB（知识库访问）
        """
        return {
            "energy_cost": 5.0,
            "duration_s": 0.1,
            "memory_mb": 10.0,
        }

    # -------------------------------------------------------------------------
    # Status & Shutdown
    # -------------------------------------------------------------------------

    def shutdown(self) -> None:
        """清理资源。"""
        self.question_generator = None
        self.experiment_designer = None
        self._initialized = False

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "initialized": self._initialized,
            "execution_count": self._execution_count,
            "last_execution": self._last_execution,
            "knowledge_entries": self.knowledge.get_stats()["total_entries"] if self.knowledge else 0,
        }
