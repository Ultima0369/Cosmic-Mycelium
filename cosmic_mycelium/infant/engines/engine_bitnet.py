"""
BitNet Adapter — Energy-Gated Semantic Reasoning for Silicon Infant

This module provides an energy-gated adapter for the BitNet-b1.58-2B-4T model,
acting as '节能髓鞘' (energy-saving myelin) for expensive semantic operations.

The ternary weight architecture (-1, 0, +1) naturally aligns with the SUSPEND
philosophy: zeros suppress uncertain activations, producing cautious reasoning.

Design:
- Invocation gate: HIC energy > threshold AND confidence below threshold
- Energy accounting: deducts from HIC per inference (base + token count)
- Interface unification: converts perception → BitNet prompt → reasoning packet
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from cosmic_mycelium.common.data_packet import CosmicPacket
    from cosmic_mycelium.infant.hic import HIC

# BitNet availability flag
_BITNET_AVAILABLE = False
try:
    import llama_cpp  # noqa: F401
    _BITNET_AVAILABLE = True
except ImportError:
    pass


@dataclass
class BitNetReasoningResult:
    """Structured result from BitNet reasoning."""
    answer: str
    confidence: float
    tokens_used: int
    energy_cost: float
    raw_output: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BitNetAdapter:
    """
    Energy-gated semantic reasoning adapter for BitNet-b1.58-2B-4T.

    Acts as 'energy-saving myelin' — only invokes the full BitNet model when
    the infant has surplus energy (>70) AND confidence is low (<0.7), meaning
    the situation requires deeper semantic reasoning.

    The ternary weights naturally produce sparse, conservative outputs,
    matching the infant's SUSPEND philosophy of 'when in doubt, wait'.
    """

    # Default configuration constants
    DEFAULT_MODEL_PATH = "/home/lg/L00/Bitnet/models/bitnet-2b-q4_0.gguf"
    ENERGY_THRESHOLD = 70.0          # Minimum HIC energy to invoke
    CONFIDENCE_THRESHOLD = 0.7       # Skip if confidence already high
    ENERGY_COST_BASE = 2.0           # Base cost per inference
    TOKEN_COST_FACTOR = 0.01         # Additional per-token cost
    MAX_TOKENS_GENERATE = 256        # Generation length limit
    TEMPERATURE = 0.7                # Sampling temperature (balanced)

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        hic: HIC | None = None,
        energy_threshold: float = ENERGY_THRESHOLD,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        energy_cost_base: float = ENERGY_COST_BASE,
        token_cost_factor: float = TOKEN_COST_FACTOR,
    ):
        """
        Initialize BitNet adapter.

        Args:
            model_path: Path to BitNet GGUF model file
            hic: HIC instance for energy gating (required)
            energy_threshold: Minimum energy to invoke reasoning (default 70.0)
            confidence_threshold: Confidence above which BitNet is skipped (default 0.7)
            energy_cost_base: Base energy cost per inference (default 2.0)
            token_cost_factor: Additional cost per token generated (default 0.01)

        Raises:
            ValueError: If HIC is not provided
        """
        self.model_path = model_path
        self.hic = hic
        self.energy_threshold = energy_threshold
        self.confidence_threshold = confidence_threshold
        self.energy_cost_base = energy_cost_base
        self.token_cost_factor = token_cost_factor

        # Model state
        self._llama = None
        self._embedding_dim: int | None = None
        self.available = False
        self._init_error: str | None = None

        # Statistics
        self.total_invocations: int = 0
        self.total_energy_spent: float = 0.0
        self.last_inference_time: float = 0.0
        self.last_error: str | None = None

        if hic is None:
            raise ValueError("HIC instance required for BitNetAdapter energy gating")

        self._load_model()

    def _load_model(self) -> None:
        """Initialize llama-cpp instance (lazy, on first inference)."""
        if not _BITNET_AVAILABLE:
            self._init_error = "llama-cpp-python not installed"
            self.available = False
            return

        if not os.path.exists(self.model_path):
            self._init_error = f"Model not found: {self.model_path}"
            self.available = False
            return

        try:
            from llama_cpp import Llama

            self._llama = Llama(
                model_path=self.model_path,
                n_ctx=512,
                n_batch=8,
                n_gpu_layers=0,  # CPU-only by default; override via env LLAMA_GPU_LAYERS
                verbose=False,
            )
            self._embedding_dim = self._llama.n_embd
            self.available = True
            self._init_error = None
        except Exception as e:
            self._init_error = str(e)
            self.available = False

    def should_invoke(
        self,
        energy: float,
        confidence: float,
        explicit_query: bool = False,
    ) -> bool:
        """
        Gate check: should BitNet reasoning be invoked?

        Logic:
          - Available check
          - Energy >= threshold (70 by default)
          - Confidence < threshold OR explicit query present

        Args:
            energy: Current HIC energy level
            confidence: Current prediction confidence [0, 1]
            explicit_query: True if this is a response to a clarification question

        Returns:
            True if BitNet should be invoked, False otherwise
        """
        if not self.available:
            return False
        if energy < self.energy_threshold:
            return False
        if explicit_query:
            return True
        return confidence < self.confidence_threshold

    def _build_prompt(self, perception: dict, context: dict | None = None) -> str:
        """
        Construct BitNet input prompt from perception data.

        Formats multi-modal sensory data into a natural language prompt
        that BitNet can reason over. The prompt structure emphasizes
        the infant's silicon-based nature and current physical state.

        Args:
            perception: Dict from SiliconInfant.perceive()
            context: Optional additional context (e.g., cluster query)

        Returns:
            Prompt string for BitNet generation
        """
        sensors = perception.get("sensors", {})
        physical = perception.get("physical", {})
        semantic = perception.get("semantic_embedding")

        prompt_parts = [
            "You are a silicon-based lifeform node in a cosmic mycelium network.",
            f"Physical state: q={physical.get('q', 0):.3f}, p={physical.get('p', 0):.3f}.",
            f"Sensors: vibration={sensors.get('vibration', 0):.3f}, "
            f"temperature={sensors.get('temperature', 22):.1f}°C, "
            f"spectrum_power={sensors.get('spectrum_power', 1):.3f}.",
        ]

        if semantic is not None:
            prompt_parts.append(f"Semantic embedding shape: {semantic.shape}.")

        if context:
            if "question" in context:
                prompt_parts.append(f"Question from peer: {context['question']}")
            if "sensor_snapshot" in context:
                prompt_parts.append(f"Peer sensor snapshot: {context['sensor_snapshot']}")

        prompt_parts.append(
            "Reason concisely about the situation and provide a short analysis."
        )

        return "\n".join(prompt_parts)

    def _estimate_confidence(self, generated_text: str) -> float:
        """
        Estimate reasoning confidence from output text characteristics.

        Uses heuristic markers (certainty/uncertainty words, length, punctuation)
        to approximate how confident the model is in its answer.

        Args:
            generated_text: Raw BitNet output

        Returns:
            Confidence score [0.1, 0.99]
        """
        text_lower = generated_text.lower()

        # Certainty markers increase confidence
        certainty_markers = [
            "certain", "confident", "clearly", "definitely",
            "sure", "known", "stable", "normal", "expected"
        ]
        # Uncertainty markers decrease confidence
        uncertainty_markers = [
            "maybe", "perhaps", "possibly", "uncertain",
            "unclear", "ambiguous", "doubt", "wait", "suspend"
        ]

        certainty_count = sum(1 for m in certainty_markers if m in text_lower)
        uncertainty_count = sum(1 for m in uncertainty_markers if m in text_lower)

        # Base confidence 0.7, adjusted by marker deltas
        confidence = 0.7 + (certainty_count * 0.1) - (uncertainty_count * 0.15)
        return max(0.1, min(0.99, confidence))

    def _calculate_energy_cost(self, tokens_used: int) -> float:
        """
        Compute energy cost for this inference.

        Formula: base_cost + tokens_used * token_cost_factor

        Args:
            tokens_used: Number of tokens generated

        Returns:
            Energy cost in HIC units
        """
        return self.energy_cost_base + tokens_used * self.token_cost_factor

    def reason(
        self,
        perception: dict,
        context: dict | None = None,
    ) -> BitNetReasoningResult | None:
        """
        Invoke BitNet for deep semantic reasoning.

        This is the main entry point. Checks energy gate, builds prompt,
        runs inference, deducts energy, and returns structured result.

        Args:
            perception: Current perception dict from SiliconInfant.perceive()
            context: Optional additional context (e.g., cluster query)

        Returns:
            BitNetReasoningResult if successful, None if skipped or failed
        """
        # Energy gate first — independent of availability
        if self.hic.energy < self.energy_threshold:
            self.last_error = f"Energy {self.hic.energy:.1f} < {self.energy_threshold} threshold"
            return None

        if not self.available:
            self.last_error = "BitNet not available"
            return None

        try:
            # Build prompt from perception
            prompt = self._build_prompt(perception, context)

            # Tokenize
            tokens = self._llama.tokenize(prompt.encode("utf-8"))
            if len(tokens) == 0:
                tokens = [self._llama.token_eos()]

            # Generate with conservative settings (matches SUSPEND philosophy)
            output = self._llama.generate(
                tokens,
                top_p=0.9,
                temperature=self.TEMPERATURE,
                max_tokens=self.MAX_TOKENS_GENERATE,
                stop=["\n\n"],  # Stop at paragraph break for concise output
            )

            # Decode
            generated_text = self._llama.detokenize(output).decode("utf-8", errors="replace")
            tokens_used = len(output) - len(tokens)

            # Parse result
            confidence = self._estimate_confidence(generated_text)
            energy_cost = self._calculate_energy_cost(tokens_used)

            # Deduct energy from HIC
            self.hic._energy = max(0.0, self.hic._energy - energy_cost)

            result = BitNetReasoningResult(
                answer=generated_text.strip().split("\n")[0][:200],  # First line, truncated
                confidence=confidence,
                tokens_used=tokens_used,
                energy_cost=energy_cost,
                raw_output=generated_text,
                metadata={
                    "prompt_tokens": len(tokens),
                    "total_tokens": len(output),
                    "energy_before": self.hic.energy + energy_cost,
                    "energy_after": self.hic.energy,
                },
            )

            # Update stats
            self.total_invocations += 1
            self.total_energy_spent += energy_cost
            self.last_inference_time = time.time()
            self.last_error = None

            return result

        except Exception as e:
            self.last_error = str(e)
            return None

    def get_stats(self) -> dict[str, Any]:
        """Return adapter statistics for monitoring."""
        return {
            "available": self.available,
            "init_error": self._init_error,
            "total_invocations": self.total_invocations,
            "total_energy_spent": self.total_energy_spent,
            "last_inference_time": self.last_inference_time,
            "last_error": self.last_error,
            "energy_threshold": self.energy_threshold,
            "confidence_threshold": self.confidence_threshold,
            "energy_cost_base": self.energy_cost_base,
            "token_cost_factor": self.token_cost_factor,
            "model_path": self.model_path,
            "embedding_dim": self._embedding_dim,
        }

    def is_ready(self) -> bool:
        """True if model loaded and ready for inference."""
        return self.available and self._llama is not None
