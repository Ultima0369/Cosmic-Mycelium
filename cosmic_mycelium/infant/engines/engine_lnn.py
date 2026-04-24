"""
Engine LNN — Liquid Neural Network (LTC)
基于 ncps 库的液态时间常数网络，实现动态节律的时序处理能力。

LTC (Liquid Time-Constant) 网络特点：
- 每个神经元有独立的时间常数，能自适应不同时间尺度
- 适合处理不规则采样、异步的时序数据
- 符合物理锚原则：内部状态连续演化，能量守恒

这是宝宝应对复杂集群环境的"宏观生态"引擎核心。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import tensorflow as tf
    import torch

# LTC 是 ncps 库的核心，尝试导入多个后端
# 优先级: keras (Keras 3 / TF 2.16+) > torch > tf (TF 2.15 legacy)
LTC_AVAILABLE = False
LTC_BACKEND = None
LTCLayer = None

try:
    from ncps.keras import LTC as _LTCLayer

    LTCLayer = _LTCLayer
    import tensorflow as tf

    LTC_AVAILABLE = True
    LTC_BACKEND = "keras"
except ImportError:
    pass

if not LTC_AVAILABLE:
    try:
        from ncps.torch import LTC as _LTCLayer

        LTCLayer = _LTCLayer
        import torch

        LTC_AVAILABLE = True
        LTC_BACKEND = "torch"
    except ImportError:
        pass

if not LTC_AVAILABLE:
    try:
        from ncps.tf import LTC as _LTCLayer

        LTCLayer = _LTCLayer
        import tensorflow as tf

        LTC_AVAILABLE = True
        LTC_BACKEND = "tf"
    except ImportError:
        pass


@dataclass
class LNNState:
    """LNN 内部状态（Lagrangian 坐标）。"""

    q: np.ndarray  # 广义坐标
    p: np.ndarray  # 广义动量


class LNNEngine:
    """
    液态神经网络引擎 (Liquid Neural Network)。

    封装 ncps 的 LTC (Liquid Time-Constant) 网络，用于：
    - 时序模式识别
    - 能量消耗预测
    - 跨节点共振模式学习

    Phase 4.2 集成点：
    - 在婴儿的 CONTRACT 阶段调用，处理历史时序数据
    - 预测未来能量趋势，辅助呼吸节律动态调整
    - 接收来自其他节点的高维向量，学习协作模式
    """

    def __init__(
        self,
        input_dim: int = 16,
        hidden_units: int = 64,
        batch_size: int = 1,
        return_sequences: bool = False,
    ):
        """
        初始化 LTC 网络。

        Args:
            input_dim: 输入特征维度（例如能量历史序列长度）
            hidden_units: LTC 隐藏层神经元数量（液态神经元数）
            batch_size: 批大小（推理阶段通常为1）
            return_sequences: 是否返回完整序列还是最后一步输出
        """
        self.input_dim = input_dim
        self.hidden_units = hidden_units
        self.batch_size = batch_size
        self.return_sequences = return_sequences

        if LTC_AVAILABLE and LTCLayer is not None:
            if LTC_BACKEND in ("keras", "tf"):
                # Keras / TensorFlow 后端
                inputs = tf.keras.Input(shape=(None, input_dim))
                ltc_layer: Any = LTCLayer(
                    units=hidden_units,
                    return_sequences=return_sequences,
                    return_state=True,
                )
                outputs, next_state = ltc_layer(inputs, initial_state=None)
                self.model = tf.keras.Model(inputs=inputs, outputs=[outputs, next_state])
                self.model.compile(optimizer="adam", loss="mse")
            elif LTC_BACKEND == "torch":
                # PyTorch 后端
                self.model = LTCLayer(
                    input_size=input_dim,
                    hidden_size=hidden_units,
                    batch_first=True,
                )
                # Torch 后端不需要 compile
            else:
                self.model = None
        else:
            self.model = None
            print(
                "[WARN] LNNEngine: ncps not available or no compatible backend found, "
                "using fallback mode"
            )

        # 内部状态跟踪（用于跨批次/跨调用的状态传递）
        self._last_state: Any = None
        self._last_timestamp: float | None = None

    def predict(self, sequence: np.ndarray) -> tuple[np.ndarray, LNNState]:
        """
        对时序数据进行推理预测。

        Args:
            sequence: 输入序列，形状 (time_steps, input_dim) 或 (batch, time_steps, input_dim)

        Returns:
            (prediction, state) — 预测结果和当前网络内部状态
        """
        if self.model is None:
            # Fallback: 返回零向量和空状态
            return np.zeros((1, self.hidden_units)), LNNState(q=np.zeros(0), p=np.zeros(0))

        if LTC_BACKEND == "torch":
            return self._predict_torch(sequence)
        else:
            return self._predict_keras(sequence)

    def _predict_keras(self, sequence: np.ndarray) -> tuple[np.ndarray, LNNState]:
        """Keras/TensorFlow 后端推理。"""
        # 确保输入是3D: (batch, time_steps, input_dim)
        if sequence.ndim == 2:
            sequence = sequence[np.newaxis, ...]

        predictions, next_state = self.model.predict(sequence, verbose=0)

        # 提取 LTC 状态 (q=膜电位, p=恢复变量)
        if hasattr(next_state, "q"):
            q = next_state.q.numpy() if hasattr(next_state.q, "numpy") else next_state.q
            p = next_state.p.numpy() if hasattr(next_state.p, "numpy") else next_state.p
        elif isinstance(next_state, (list, tuple)) and len(next_state) >= 2:
            q = np.array(next_state[0])
            p = np.array(next_state[1])
        else:
            q = np.array(next_state)
            p = np.zeros_like(q)
        state = LNNState(q=q, p=p)
        self._last_state = state
        return predictions, state

    def _predict_torch(self, sequence: np.ndarray) -> tuple[np.ndarray, LNNState]:
        """PyTorch 后端推理。"""
        # 确保输入是3D: (batch, time_steps, input_dim)
        if sequence.ndim == 2:
            sequence = sequence[np.newaxis, ...]

        with torch.no_grad():
            seq_tensor = torch.tensor(sequence, dtype=torch.float32)
            if self._last_state is not None:
                hx = (
                    torch.tensor(self._last_state.q),
                    torch.tensor(self._last_state.p),
                )
                output, next_state = self.model(seq_tensor, hx=hx)
            else:
                output, next_state = self.model(seq_tensor)

        # 提取状态
        if isinstance(next_state, (list, tuple)) and len(next_state) >= 2:
            q = next_state[0].cpu().numpy()
            p = next_state[1].cpu().numpy()
        else:
            q = next_state.cpu().numpy() if hasattr(next_state, "cpu") else np.array(next_state)
            p = np.zeros_like(q)
        state = LNNState(q=q, p=p)
        self._last_state = state

        output_np = output.cpu().numpy() if hasattr(output, "cpu") else np.array(output)
        return output_np, state

    def step(self, observation: np.ndarray) -> tuple[np.ndarray, LNNState]:
        """
        单步推理（增量式）。

        与 `predict` 不同，`step` 可以携带内部状态跨调用，
        适合流式处理。

        Args:
            observation: 单步观察，形状 (input_dim,)

        Returns:
            (output, state) — 输出和更新后的内部状态
        """
        if self.model is None:
            return np.zeros(self.hidden_units), LNNState(q=np.zeros(0), p=np.zeros(0))

        if LTC_BACKEND == "torch":
            return self._step_torch(observation)
        else:
            return self._step_keras(observation)

    def _step_keras(self, observation: np.ndarray) -> tuple[np.ndarray, LNNState]:
        """Keras 单步。"""
        obs_batch = observation[np.newaxis, np.newaxis, :]
        if self._last_state is not None:
            # Keras LTC 接受初始状态
            # 状态格式: (h, c) 或 LNNState
            initial = (self._last_state.q, self._last_state.p)
            predictions, next_state = self.model.predict(obs_batch, verbose=0)
        else:
            predictions, next_state = self.model.predict(obs_batch, verbose=0)

        if hasattr(next_state, "q"):
            q = next_state.q.numpy() if hasattr(next_state.q, "numpy") else next_state.q
            p = next_state.p.numpy() if hasattr(next_state.p, "numpy") else next_state.p
        elif isinstance(next_state, (list, tuple)) and len(next_state) >= 2:
            q = np.array(next_state[0])
            p = np.array(next_state[1])
        else:
            q = np.array(next_state)
            p = np.zeros_like(q)
        state = LNNState(q=q, p=p)
        self._last_state = state

        output = predictions[0, -1, :] if predictions.ndim == 3 else predictions[0]
        return output, state

    def _step_torch(self, observation: np.ndarray) -> tuple[np.ndarray, LNNState]:
        """PyTorch 单步。"""
        import torch

        obs_batch = observation[np.newaxis, np.newaxis, :].astype(np.float32)
        with torch.no_grad():
            obs_tensor = torch.tensor(obs_batch)
            if self._last_state is not None:
                hx = (
                    torch.tensor(self._last_state.q),
                    torch.tensor(self._last_state.p),
                )
                output, next_state = self.model(obs_tensor, hx=hx)
            else:
                output, next_state = self.model(obs_tensor)

        if isinstance(next_state, (list, tuple)) and len(next_state) >= 2:
            q = next_state[0].cpu().numpy()
            p = next_state[1].cpu().numpy()
        else:
            q = next_state.cpu().numpy() if hasattr(next_state, "cpu") else np.array(next_state)
            p = np.zeros_like(q)
        state = LNNState(q=q, p=p)
        self._last_state = state

        output_np = output.cpu().numpy() if hasattr(output, "cpu") else np.array(output)
        return output_np[0, -1, :], state

    def reset(self) -> None:
        """重置内部状态（用于新序列开始）。"""
        self._last_state = None
        self._last_timestamp = None

    def predict_energy_trend(self, energy_history: list[float]) -> float:
        """
        Predict energy trend from variable-length energy history.

        Handles dimension mapping internally: accepts variable-length
        energy history, pads it to match self.input_dim (energy values
        in column 0, remaining dimensions zero-filled), processes through
        the LNN, and returns a scalar energy trend prediction.

        Args:
            energy_history: Variable-length list of energy values.

        Returns:
            Scalar energy trend prediction (mean of LNN hidden-unit outputs).
        """
        if self.model is None:
            return 0.0

        # Build padded sequence: (history_len, input_dim) with energy in column 0
        history_len = len(energy_history)
        seq = np.zeros((history_len, self.input_dim))
        seq[:, 0] = np.array(energy_history, dtype=float)

        # Run prediction on full sequence to capture temporal trend
        prediction, _ = self.predict(seq)

        # Reduce hidden-unit outputs to scalar trend
        return float(np.mean(prediction))

    def energy(self) -> float:
        """
        计算网络内部能量（类物理量）。
        LTC 网络的类物理能量：∑(p²/(2m) + ½kq²)，其中 m=1, k=1。
        这个能量应保持有界（物理锚）。
        """
        if self._last_state is None:
            return 0.0
        q = self._last_state.q
        p = self._last_state.p
        kinetic = 0.5 * np.sum(p**2)
        potential = 0.5 * np.sum(q**2)
        return float(kinetic + potential)

    def is_available(self) -> bool:
        """检查 LTC 后端是否可用。"""
        return LTC_AVAILABLE and self.model is not None

    def get_backend(self) -> str | None:
        """获取当前使用的后端名称。"""
        return LTC_BACKEND
