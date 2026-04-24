"""
PhysicsExperimentSkill — THEIA Physics Engine Wrapper

Wraps THEIAEngine (pre-trained physics intuition model) as a pluggable skill.
Provides safe/unsafe/uncertain verdicts and integrates with HIC caution system.

Phase: Epic 2 (Skill Plugin System — Built-in Skills)
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext, SkillExecutionError

if TYPE_CHECKING:
    from cosmic_mycelium.infant.hic import HIC
    from cosmic_mycelium.infant.engines.engine_theia import THEIAEngine


class PhysicsExperimentSkill(InfantSkill):
    """
    Physics safety validation via THEIA pre-trained model.

    Queries THEIA to determine whether a physical action is safe/feasible.
    Integrates with HIC's caution system: sets high caution on unsafe/unknown.

    Usage:
        skill.execute({
            "physical_data": {"a": q_value, "b": p_value},
            "min_confidence": 0.7,      # optional, default 0.7
            "probe_hidden": False,       # optional, return hidden state
        })

    Returns:
        {
            "verdict": int,              # 1=safe, 0=unsafe, 2=unknown
            "confidence": float,         # [0, 1]
            "status": "safe" | "unsafe" | "uncertain" | "error" | "degraded",
            "caution_triggered": bool,   # whether HIC caution was raised
            "inference_time_ms": float,
            "energy_cost": float,
        }

    Dependencies: none (THEIAEngine loaded lazily)
    """

    name = "physics_experiment"
    version = "1.0.0"
    description = "Physics intuition via THEIA model — safety validation for actions"
    dependencies = []  # standalone; THEIAEngine optional dependency
    parallelism_policy = ParallelismPolicy.ISOLATED  # Sprint 2: own cache only, no shared writes

    def __init__(
        self,
        model_path: str | None = None,
        hic: HIC | None = None,
    ):
        """
        Args:
            model_path: Path to THEIA checkpoint (.pt). If None, engine loads lazily on first use.
            hic: Optional HIC instance for caution integration.
        """
        self._model_path = model_path
        self.hic = hic
        self._engine: THEIAEngine | None = None
        self._initialized = False
        self._last_execution: float = 0.0
        self._execution_count: int = 0
        self._cooldown: float = 0.5  # minimum seconds between physics queries
        self._verdict_cache: OrderedDict[tuple, int] = OrderedDict()  # LRU cache
        self._cache_max_size = 100

    # -------------------------------------------------------------------------
    # InfantSkill Protocol
    # -------------------------------------------------------------------------

    def initialize(self, context: SkillContext) -> None:
        """Initialize skill (engine loads lazily on first execute)."""
        self._initialized = True

    def can_activate(self, context: SkillContext) -> bool:
        """
        Physics query activation:
        - Initialized
        - Energy >= 4 (THEIA inference cost)
        - Cooldown elapsed
        """
        if not self._initialized:
            return False
        if context.energy_available < 4:
            return False
        if time.time() - self._last_execution < self._cooldown:
            return False
        return True

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a physics safety check.

        Args:
            params:
                physical_data: dict with 'a' and 'b' numeric values
                min_confidence: float (default 0.7)
                probe_hidden: bool (default False)

        Returns:
            Dict with verdict, confidence, status, and optional hidden_state.
        """
        if not self._initialized:
            raise SkillExecutionError("PhysicsExperimentSkill not initialized")

        physical_data = params.get("physical_data")
        if not physical_data or "a" not in physical_data or "b" not in physical_data:
            return {
                "status": "error",
                "error": "missing required key(s) in physical_data: need 'a' and 'b'",
                "energy_cost": 0.1,
            }

        min_conf = params.get("min_confidence", 0.7)
        probe_hidden = params.get("probe_hidden", False)

        # Lazy engine load
        if self._engine is None:
            loaded = self._load_engine()
            if not loaded:
                # Engine unavailable — degraded mode
                return self._degraded_response(physical_data)

        # Check cache
        cache_key = self._make_cache_key(physical_data, min_conf)
        if cache_key in self._verdict_cache:
            cached_verdict = self._verdict_cache.pop(cache_key)
            self._verdict_cache[cache_key] = cached_verdict  # move to end (LRU)
            # Determine status from cached verdict (same logic as fresh inference)
            if cached_verdict.verdict == 1 and cached_verdict.confidence >= min_conf:
                status = "safe"
                caution = False
            elif cached_verdict.verdict == 0 or cached_verdict.confidence < min_conf:
                status = "unsafe" if cached_verdict.verdict == 0 else "uncertain"
                caution = True
            else:
                status = "unknown"
                caution = True
            return {
                "verdict": cached_verdict.verdict,
                "confidence": cached_verdict.confidence,
                "status": status,
                "caution_triggered": caution,
                "inference_time_ms": 0.0,
                "energy_cost": 0.5,
            }

        # Execute THEIA inference
        try:
            result = self._engine.intuit(
                physical_data,
                a_unk=False,
                b_unk=False,
                return_hidden=probe_hidden,
            )
        except Exception as e:
            # Engine failure — degraded mode
            return self._degraded_response(physical_data, error=str(e))

        # Determine status
        if result.verdict == 1 and result.confidence >= min_conf:
            status = "safe"
            caution = False
        elif result.verdict == 0 or result.confidence < min_conf:
            status = "unsafe" if result.verdict == 0 else "uncertain"
            caution = True
        else:
            status = "unknown"
            caution = True

        # Trigger HIC caution if needed
        if caution and self.hic is not None:
            try:
                self.hic.adjust_caution(True)
            except Exception:
                pass  # HIC may not have adjust_caution

        # Cache result
        self._verdict_cache[cache_key] = result
        if len(self._verdict_cache) > self._cache_max_size:
            self._verdict_cache.popitem(last=False)  # evict LRU

        self._last_execution = time.time()
        self._execution_count += 1

        return {
            "verdict": result.verdict,
            "confidence": round(result.confidence, 4),
            "status": status,
            "caution_triggered": caution,
            "inference_time_ms": round(result.inference_time_ms, 2),
            "energy_cost": 4.0,
        }

    def get_resource_usage(self) -> dict[str, float]:
        """
        Physics inference cost:
        - Energy: ~4 units (THEIA forward pass)
        - Duration: ~0.05s (50ms inference on CPU)
        - Memory: ~50MB (model weights + activations)
        """
        return {"energy_cost": 4.0, "duration_s": 0.05, "memory_mb": 50.0}

    def shutdown(self) -> None:
        """Release THEIA engine resources."""
        self._engine = None
        self._initialized = False
        self._verdict_cache.clear()

    def get_status(self) -> dict[str, Any]:
        """Return skill health and engine state."""
        return {
            "name": self.name,
            "version": self.version,
            "initialized": self._initialized,
            "execution_count": self._execution_count,
            "last_execution": self._last_execution,
            "engine_ready": self._engine is not None,
            "cache_size": len(self._verdict_cache),
        }

    # -------------------------------------------------------------------------
    # Internal: Engine loading
    # -------------------------------------------------------------------------

    def _load_engine(self) -> bool:
        """
        Lazily load THEIAEngine from model_path or environment.

        Returns True if engine loaded, False if unavailable (degraded mode).
        """
        if self._engine is not None:
            return True

        model_path = self._model_path
        if model_path is None:
            import os
            model_path = os.environ.get("THEIA_MODEL_PATH")

        if not model_path:
            self._engine = None
            return False

        try:
            from cosmic_mycelium.infant.engines.engine_theia import THEIAEngine
            self._engine = THEIAEngine(model_path)
            return True
        except Exception:
            self._engine = None
            return False

    def _degraded_response(self, physical_data: dict, error: str = "") -> dict[str, Any]:
        """
        Return degraded-mode response when THEIA engine unavailable.

        Conservative default: treat as uncertain → high caution.
        """
        return {
            "verdict": None,
            "confidence": 0.0,
            "status": "degraded",
            "caution_triggered": True,
            "error": error or "THEIA engine unavailable",
            "inference_time_ms": 0.0,
            "energy_cost": 0.1,
        }

    def _make_cache_key(self, physical_data: dict, min_conf: float) -> tuple:
        """
        Create hashable cache key from physical_data parameters.

        Rounds floats to reduce cache misses from minor variations.
        """
        a = round(float(physical_data.get("a", 0.0)), 3)
        b = round(float(physical_data.get("b", 0.0)), 3)
        return (a, b, min_conf)
