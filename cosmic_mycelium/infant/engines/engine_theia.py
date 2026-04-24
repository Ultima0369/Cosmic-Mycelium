"""
THEIA Engine — Physics Intuition Adapter

Wraps the four-engine THEIA model (Order / Set / Logic + Residual Bridge)
for use within the infant cognition layer.

独立运行的物理直觉引擎，基于预训练的 THEIA 模型。
提供延迟判定检验接口，不参与宝宝的自我演化循环。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from cosmic_mycelium.common.theia_model import THEIA

try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class THEIAIntuitionResult:
    """THEIA 物理直觉推理结果。"""
    verdict: int  # 0=False, 1=True, 2=Unknown
    confidence: float  # 判定置信度 [0, 1]
    hidden_state: np.ndarray | None = None  # 上游隐藏状态 (用于线性探针检验)
    raw_logits: np.ndarray | None = None  # 原始 logits
    inference_time_ms: float = 0.0  # 推理耗时
    metadata: dict[str, Any] = field(default_factory=dict)


class THEIAEngine:
    """
    物理直觉引擎封装 — 四引擎 THEIA 架构。

    内部模型:
        - OrderEngine:  序列 / 时间模式推理 (LSTM)
        - SetEngine:    集合 / 置换不变推理 (DeepSets)
        - LogicEngine:  C/D/I 三子空间推理 (延迟判定核心)
        - Residual Bridge + Prototype Classifier (最终判定)

    职责:
        - 加载预训练的 THEIA 模型
        - 将宝宝的物理状态转换为 THEIA 输入格式 (序列 + 集合双格式)
        - 收集所有三个引擎的隐藏状态
        - 使用原型分类器执行最终判定
        - 提供延迟判定检验接口 (probe 隐藏状态)

    注意: THEIA 是独立模块，不记录到 FeatureManager，不参与髓鞘化循环。
    """

    def __init__(
        self,
        model_path: str | Path,
        device: str | None = None,
        probe_lambda: float = 0.5,
    ):
        """
        初始化 THEIA 引擎。

        Args:
            model_path: 预训练模型权重文件路径 (.pt)
            device: 推理设备 ("cpu"/"cuda"/None=自动)
            probe_lambda: 探针阻尼系数 (优化目标: 0.9-1.0 更强延迟)

        Raises:
            ImportError: PyTorch 未安装
            FileNotFoundError: 模型文件不存在
        """
        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for THEIA. Install with: pip install torch"
            )

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"THEIA model not found: {model_path}")

        self.model_path = model_path
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.probe_lambda = probe_lambda

        # 加载四引擎 THEIA 模型
        from cosmic_mycelium.common.theia_model import THEIA

        self.model = THEIA.load_from_checkpoint(str(model_path), device=self.device)

        # 延迟判定探针 (可选: sklearn LogisticRegression, 懒加载)
        self._probe = None

        # 统计
        self._inference_count = 0
        self._total_inference_time = 0.0

    def intuit(
        self,
        physical_data: dict[str, float],
        *,
        a_unk: bool = False,
        b_unk: bool = False,
        return_hidden: bool = False,
    ) -> THEIAIntuitionResult:
        """
        执行物理直觉推理。

        内部流程:
            1. 将物理数据转换为序列格式和集合格式
            2. 三个引擎 (Order/Set/Logic) 并行处理
            3. 残差桥接融合三个隐藏状态
            4. 原型分类器做出最终三分类判定

        Args:
            physical_data: 物理状态字典，需包含 'a' 和 'b' 两个数值
            a_unk: 参数 a 是否未知
            b_unk: 参数 b 是否未知
            return_hidden: 是否返回隐藏状态 (用于探针检验)

        Returns:
            THEIAIntuitionResult: 推理结果

        示例:
            >>> engine.intuit({"a": q, "b": p})
            THEIAIntuitionResult(verdict=1, confidence=0.92, ...)
        """
        start = time.perf_counter()

        with torch.no_grad():
            # 构建输入张量 — 序列格式和集合格式在模型内部自动构建
            a_t = torch.tensor(
                [[float(physical_data["a"])]], dtype=torch.float32
            ).to(self.device)
            b_t = torch.tensor(
                [[float(physical_data["b"])]], dtype=torch.float32
            ).to(self.device)
            a_unk_t = torch.tensor([[a_unk]], dtype=torch.bool).to(self.device)
            b_unk_t = torch.tensor([[b_unk]], dtype=torch.bool).to(self.device)

            # 四引擎前向传播 — 返回 (logits, fused_hidden, engine_states)
            logits, hidden, engine_states = self.model(
                a_t, b_t, a_unk_t, b_unk_t
            )

            probs = F.softmax(logits, dim=-1)
            verdict = torch.argmax(probs, dim=-1).item()
            confidence = probs[0, verdict].item()

        elapsed = (time.perf_counter() - start) * 1000

        self._inference_count += 1
        self._total_inference_time += elapsed

        hidden_np = hidden.cpu().numpy() if return_hidden else None
        logits_np = logits.cpu().numpy()

        # 收集引擎状态元数据 (用于调试和探针检验)
        engine_meta: dict[str, Any] = {"probe_lambda": self.probe_lambda}

        if return_hidden:
            engine_meta["engine_hidden_order"] = (
                engine_states["order"].cpu().numpy()
            )
            engine_meta["engine_hidden_set"] = (
                engine_states["set"].cpu().numpy()
            )
            engine_meta["engine_hidden_logic"] = (
                engine_states["logic"].cpu().numpy()
            )
            engine_meta["gate_weights_cdi"] = (
                engine_states["gate_weights"].cpu().numpy()
            )

        return THEIAIntuitionResult(
            verdict=int(verdict),
            confidence=float(confidence),
            hidden_state=hidden_np,
            raw_logits=logits_np,
            inference_time_ms=elapsed,
            metadata=engine_meta,
        )

    def is_physics_safe(
        self,
        physical_data: dict[str, float],
        min_confidence: float = 0.7,
    ) -> bool:
        """
        快速检查：当前物理状态是否"安全"（可行）。

        Args:
            physical_data: 物理状态
            min_confidence: 置信度阈值

        Returns:
            True 如果 verdict=1 (True) 且 confidence >= min_confidence
        """
        result = self.intuit(physical_data)
        return result.verdict == 1 and result.confidence >= min_confidence

    def should_trigger_caution(
        self,
        physical_data: dict[str, float],
        efficacy_threshold: float = 0.5,
    ) -> bool:
        """
        检查是否应该触发"谨慎"模式。

        当 THEIA 判定为 False (物理不可行) 或 Unknown (不确定) 时，
        建议增加 caution 价值维度权重。

        Args:
            physical_data: 物理状态
            efficacy_threshold: 效能阈值 (低于此值视为低置信度)

        Returns:
            True 如果应该提高谨慎权重
        """
        result = self.intuit(physical_data)
        # verdict: 0=False (危险), 1=True (安全), 2=Unknown (不确定)
        return result.verdict in (0, 2) or result.confidence < efficacy_threshold

    def get_stats(self) -> dict[str, Any]:
        """返回引擎统计信息。"""
        avg_time = (
            self._total_inference_time / self._inference_count
            if self._inference_count > 0 else 0.0
        )
        return {
            "model_path": str(self.model_path),
            "device": self.device,
            "hidden_dim": self.model.hidden_dim,
            "inference_count": self._inference_count,
            "avg_inference_time_ms": round(avg_time, 3),
            "probe_lambda": self.probe_lambda,
        }

    # ── 延迟判定检验接口 (用于调试/验证) ──

    def probe_hidden_state(
        self,
        hidden_states: np.ndarray,
        labels: np.ndarray,
    ) -> float:
        """
        使用线性探针解码隐藏状态，检验延迟判定强度。

        对 Order/Set/Logic 三个引擎的隐藏状态分别进行线性探针检验，
        综合评估上游隐藏状态的信息泄露程度。

        Args:
            hidden_states: (N, hidden_dim) 融合后隐藏状态
            labels: (N,) 真实标签 (0/1/2)

        Returns:
            线性解码准确率 (期望 < 40% 表示强延迟判定)
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score

        probe = LogisticRegression(max_iter=1000)
        probe.fit(hidden_states, labels)
        pred = probe.predict(hidden_states)
        acc = accuracy_score(labels, pred)
        # probe_lambda 越高，上游信息越少，准确率应越接近随机 (33%)
        return acc

    def probe_engine_states(
        self,
        engine_hidden: np.ndarray,
        labels: np.ndarray,
        engine_name: str = "",
    ) -> float:
        """
        对单个引擎的隐藏状态进行线性探针检验。

        Args:
            engine_hidden: (N, hidden_dim) 单个引擎的输出隐藏状态
            labels: (N,) 真实标签
            engine_name: 引擎名称 (用于日志)

        Returns:
            线性解码准确率
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score

        probe = LogisticRegression(max_iter=1000)
        probe.fit(engine_hidden, labels)
        pred = probe.predict(engine_hidden)
        return accuracy_score(labels, pred)
