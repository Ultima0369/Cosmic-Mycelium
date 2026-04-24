"""
THEIA Model — Four-Engine Physical Intuition Architecture

延迟判定架构 (Delayed Judgment Architecture):
  三个并行引擎 (Order/Set/Logic) 独立处理输入，
  通过残差桥接融合后由原型分类器做出最终判定。

Engines:
  - OrderEngine:  LSTM/GRU sequential reasoning (temporal patterns)
  - SetEngine:    DeepSets permutation-invariant reasoning (set structure)
  - LogicEngine:  C/D/I three-subspace reasoning (Certain/Doubtful/Impossible)

Design principles:
  - 上游隐藏状态应无法被线性探针轻易解码 (延迟判定)
  - 逻辑层在训练时学习从隐藏状态做出准确判断
  - 原型分类器 (prototype-based classification head)
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# ═══════════════════════════════════════════════════════════════════
# OrderEngine — Sequential / Temporal Pattern Reasoning
# ═══════════════════════════════════════════════════════════════════

class OrderEngine(nn.Module):
    """
    顺序引擎：处理序列和时间模式。

    Uses a stacked LSTM to capture sequential dependencies among the
    four input scalars (a, b, a_unk, b_unk) treated as a 4-step sequence.

    Input:  (batch, seq_len=4, features=1)
    Output: (batch, hidden_dim)
    """

    def __init__(self, input_dim: int = 1, hidden_dim: int = 128):
        super().__init__()
        self.hidden_dim = hidden_dim

        # Embed scalar inputs into hidden space
        self.embed = nn.Linear(input_dim, hidden_dim)

        # Two-layer LSTM for sequential reasoning
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            dropout=0.1,
        )

        # Output projection with residual
        self.output = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, x_seq: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x_seq: (batch, seq_len, 1) — scalar sequence

        Returns:
            (batch, hidden_dim) — order-aware hidden state
        """
        # Embed: (batch, seq_len, 1) → (batch, seq_len, hidden_dim)
        x = self.embed(x_seq)

        # LSTM processing
        out, (h_n, _c_n) = self.lstm(x)

        # Use the final layer's last hidden state
        h_final = h_n[-1]  # (batch, hidden_dim)

        # Output projection with skip connection
        return self.output(h_final) + h_final


# ═══════════════════════════════════════════════════════════════════
# SetEngine — Permutation-Invariant Set Reasoning
# ═══════════════════════════════════════════════════════════════════

class SetEngine(nn.Module):
    """
    集合引擎：置换不变推理。

    Implements the DeepSets architecture:
      φ: per-element MLP  →  Σ (sum pooling)  →  ρ: post-pooling MLP

    Input:  (batch, set_size=4, features=1)
    Output: (batch, hidden_dim)
    """

    def __init__(self, input_dim: int = 1, hidden_dim: int = 128):
        super().__init__()
        self.hidden_dim = hidden_dim

        # Per-element transformation φ
        self.phi = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

        # Post-pooling transformation ρ
        self.rho = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, x_set: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x_set: (batch, set_size, 1) — set elements

        Returns:
            (batch, hidden_dim) — permutation-invariant hidden state
        """
        # φ: per-element transform
        x = self.phi(x_set)  # (batch, set_size, hidden_dim)

        # Σ: sum pooling (permutation invariant)
        x = x.sum(dim=1)  # (batch, hidden_dim)

        # ρ: post-pooling transform with residual
        return self.rho(x) + x


# ═══════════════════════════════════════════════════════════════════
# LogicEngine — C/D/I Three-Subspace Reasoning
# ═══════════════════════════════════════════════════════════════════

class LogicEngine(nn.Module):
    """
    逻辑引擎：三子空间推理 (THEIA "延迟判定" 的核心)。

    Three parallel subspaces:
      - C (Certain):      high-confidence, deductive judgments
      - D (Doubtful):     uncertain, intuition-based assessments
      - I (Impossible):   known-impossible / ruled-out states

    Each subspace is a learned linear projection, gated via softmax
    over a gating network that decides the contribution of each subspace.

    Input:  (batch, input_dim=4)
    Output: (batch, hidden_dim), gate_weights (batch, 3)
    """

    def __init__(self, input_dim: int = 4, hidden_dim: int = 128):
        super().__init__()
        self.hidden_dim = hidden_dim

        # Each subspace gets hidden_dim // 4 dimensions
        self.subspace_dim = max(hidden_dim // 4, 8)

        # Three parallel projections for C, D, I
        self.proj_c = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, self.subspace_dim),
        )
        self.proj_d = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, self.subspace_dim),
        )
        self.proj_i = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, self.subspace_dim),
        )

        # Gating network: decides contribution of C/D/I
        self.gate = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 3),
        )

        # Output projection: 3 * subspace_dim → hidden_dim
        combined_dim = 3 * self.subspace_dim
        self.output = nn.Sequential(
            nn.Linear(combined_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, input_dim) — raw concatenated inputs

        Returns:
            hidden:    (batch, hidden_dim) — logic-gated hidden state
            gate_w:    (batch, 3) — C/D/I gate weights (diagnostic)
        """
        # Project into each subspace
        c = self.proj_c(x)  # (batch, subspace_dim)
        d = self.proj_d(x)  # (batch, subspace_dim)
        i = self.proj_i(x)  # (batch, subspace_dim)

        # Softmax gating over the three subspaces
        gate_logits = self.gate(x)  # (batch, 3)
        gate_w = F.softmax(gate_logits, dim=-1)  # (batch, 3)

        # Weight each subspace by its gate value
        c = c * gate_w[:, 0:1]
        d = d * gate_w[:, 1:2]
        i = i * gate_w[:, 2:3]

        # Concatenate weighted subspaces
        combined = torch.cat([c, d, i], dim=-1)  # (batch, 3 * subspace_dim)

        # Project to hidden_dim with residual
        hidden = self.output(combined)
        return hidden, gate_w


# ═══════════════════════════════════════════════════════════════════
# THEIA — Full Four-Engine Architecture
# ═══════════════════════════════════════════════════════════════════

class THEIA(nn.Module):
    """
    THEIA 物理直觉模型 — 四引擎并行 + 延迟判定。

    Architecture:
        1. Three engines (Order, Set, Logic) process inputs in parallel
        2. Residual bridge fuses all three hidden states
        3. Prototype classifier makes final 3-class verdict (F/T/U)

    设计原则:
        - 上游隐藏状态应无法被线性探针轻易解码 (延迟判定)
        - 逻辑层 (LogicEngine) 的 C/D/I 子空间实现软判定
        - 原型分类器在训练中通过 Gumbel-Softmax 强化离散原型分配
    """

    def __init__(self, hidden_dim: int = 128, input_dim: int = 4):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.input_dim = input_dim

        # ── Three parallel engines ──
        self.order_engine = OrderEngine(input_dim=1, hidden_dim=hidden_dim)
        self.set_engine = SetEngine(input_dim=1, hidden_dim=hidden_dim)
        self.logic_engine = LogicEngine(input_dim=input_dim, hidden_dim=hidden_dim)

        # ── Residual bridge: fuse all three engine outputs ──
        # Input: (batch, hidden_dim * 3) → Output: (batch, hidden_dim)
        self.residual_bridge = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim * 2),
            nn.LayerNorm(hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

        # ── Prototype-based classification head ──
        # Projects fused hidden state to 3-class logits (False / True / Unknown)
        self.prototype_classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 3),
        )

        self._init_weights()

    def _init_weights(self):
        """Initialize weights for stable training."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=0.5)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.LSTM):
                for name, param in m.named_parameters():
                    if "weight" in name:
                        nn.init.xavier_uniform_(param, gain=0.5)
                    elif "bias" in name:
                        nn.init.zeros_(param)

    def forward(
        self,
        a: torch.Tensor,       # (batch, 1)
        b: torch.Tensor,       # (batch, 1)
        a_unk: torch.Tensor,   # (batch, 1) bool
        b_unk: torch.Tensor,   # (batch, 1) bool
        temperature: float = 1.0,
        hard: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        """
        Forward pass through all four engines.

        Args:
            a:      Position / first physical parameter    (batch, 1)
            b:      Momentum / second physical parameter   (batch, 1)
            a_unk:  Whether 'a' is unknown                 (batch, 1) bool
            b_unk:  Whether 'b' is unknown                 (batch, 1) bool
            temperature:  Gumbel-Softmax temperature (1.0 = no effect)
            hard:         Whether to use hard Gumbel-Softmax

        Returns:
            logits:       (batch, 3) raw classification scores
            hidden:       (batch, hidden_dim) fused hidden state
            engine_states: dict with per-engine hidden states and gate weights
        """
        # ── Preprocess inputs ──
        a_unk_f = a_unk.float()
        b_unk_f = b_unk.float()

        # Combined flat input: (batch, 4)
        x_flat = torch.cat([a, b, a_unk_f, b_unk_f], dim=-1)

        # Sequential format: treat 4 scalars as 4 time steps
        x_seq = x_flat.unsqueeze(-1)  # (batch, 4, 1)

        # Set format: treat 4 scalars as unordered set elements
        x_set = x_flat.unsqueeze(-1)  # (batch, 4, 1)

        # ── 1. Each engine processes independently ──
        order_hidden = self.order_engine(x_seq)          # (batch, hidden_dim)
        set_hidden = self.set_engine(x_set)              # (batch, hidden_dim)
        logic_hidden, gate_w = self.logic_engine(x_flat)  # (batch, hidden_dim)

        # ── 2. Residual bridge fuses all outputs ──
        combined = torch.cat([order_hidden, set_hidden, logic_hidden], dim=-1)
        fused = self.residual_bridge(combined)  # (batch, hidden_dim)

        # Global residual: add each engine's contribution
        hidden = fused + order_hidden + set_hidden + logic_hidden

        # ── 3. Prototype classifier ──
        logits = self.prototype_classifier(hidden)  # (batch, 3)

        # Optional Gumbel-Softmax for prototype assignment (training only)
        if self.training and temperature != 1.0:
            gumbel_logits = F.gumbel_softmax(logits, tau=temperature, hard=hard)
            # Blend: use gumbel probs for prototype assignment signal
            logits = logits + 0.1 * (gumbel_logits - logits.detach())

        # ── Collect engine states for diagnostics ──
        engine_states = {
            "order": order_hidden,
            "set": set_hidden,
            "logic": logic_hidden,
            "gate_weights": gate_w,       # C/D/I gating for LogicEngine
        }

        return logits, hidden, engine_states

    @classmethod
    def load_from_checkpoint(
        cls,
        model_path: str,
        hidden_dim: int = 128,
        device: torch.device | str | None = None,
    ) -> THEIA:
        """
        Load a pre-trained THEIA model from a checkpoint file.

        Automatically detects hidden_dim from the saved state dict
        if not explicitly provided.

        Args:
            model_path: Path to .pt or .pth checkpoint file
            hidden_dim: Hidden dimension (auto-detected if state dict available)
            device:     Target device ("cpu"/"cuda"/None=auto)

        Returns:
            Loaded THEIA instance in eval mode on the target device
        """
        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        elif isinstance(device, str):
            device = torch.device(device)

        state_dict = torch.load(model_path, map_location=device, weights_only=True)

        # Auto-detect hidden_dim from the saved prototype_classifier
        if "prototype_classifier.0.weight" in state_dict:
            hidden_dim = state_dict["prototype_classifier.0.weight"].shape[1]

        model = cls(hidden_dim=hidden_dim)
        model.load_state_dict(state_dict)
        model.eval()
        model.to(device)
        return model
