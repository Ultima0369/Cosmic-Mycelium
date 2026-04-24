"""
SympNet Engine — The "Physics Anchor"
Hamiltonian Neural Network that enforces energy conservation.
This is the physical foundation: energy drift must stay < 0.1%.

v4.0 Multi-DOF:
  - Supports both scalar (1-DOF, backward compatible) and ndarray (N-DOF) states
  - Hamiltonian H(q,p) = T(p) + V(q) — separable, arbitrary potential via potential_fn
  - Vectorized leapfrog integration for any number of DOF
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import copy
import logging
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


def _default_potential(q: float | np.ndarray, spring_constant: float = 1.0) -> float:
    """
    Default potential: V(q) = ½ k q² (harmonic oscillator).
    Works for both scalar and ndarray q.
    """
    if isinstance(q, np.ndarray):
        return float(0.5 * spring_constant * float(np.sum(q * q)))
    return float(0.5 * spring_constant * q * q)


def _kinetic(p: float | np.ndarray, mass: float = 1.0) -> float:
    """Kinetic energy: T(p) = p²/(2m). Works for scalar and ndarray."""
    if isinstance(p, np.ndarray):
        return float(np.sum(p * p) / (2.0 * mass))
    return float(p * p / (2.0 * mass))


@dataclass
class SympNetEngine:
    """
    Symplectic Neural Network Engine.

    Implements a Hamiltonian system that respects energy conservation.
    Supports both:
      - 1-DOF scalar mode (backward compatible): single (q, p) pair
      - N-DOF vector mode: q and p as numpy arrays

    Physical Anchor: Over 1M steps, energy drift must stay < 0.1%.
    Phase 5.0: Critical drift protection — automatic checkpoint/rollback.
    """

    mass: float = 1.0
    spring_constant: float = 1.0
    damping: float = 0.0

    # Custom potential function V(q) -> float (default: harmonic oscillator)
    potential_fn: Callable | None = None

    # Internal state
    _history: deque = field(default_factory=lambda: deque(maxlen=1000))
    _integration_error: float = 0.0

    # Phase 5.0: Physical red line protection
    CRITICAL_DRIFT_THRESHOLD: float = 0.01  # 1% drift triggers warning
    CRITICAL_DRIFT_STREAK: int = 3         # Consecutive violations cause rollback
    _high_drift_streak: int = field(default=0)
    _checkpoint_weights: dict | None = field(default=None, init=False)

    # Base timestep for internal sub-stepping to ensure energy conservation
    _BASE_DT: float = field(init=False, default=0.01, compare=False)

    def __post_init__(self) -> None:
        self.save_checkpoint()

    def state_dict(self) -> dict:
        """Serializable state: physical parameters and damping."""
        return {
            "mass": self.mass,
            "spring_constant": self.spring_constant,
            "damping": self.damping,
            "has_potential_fn": self.potential_fn is not None,
        }

    def load_state_dict(self, state: dict) -> None:
        """Restore state from a saved checkpoint."""
        self.mass = state["mass"]
        self.spring_constant = state["spring_constant"]
        self.damping = state["damping"]

    # ── Hamiltonian ──────────────────────────────────────────────────

    def compute_energy(self, q: float | np.ndarray, p: float | np.ndarray) -> float:
        """
        Hamiltonian: H(q,p) = T(p) + V(q)

        Scalar (1-DOF): H = p²/(2m) + ½kq²  (backward compatible)
        Array (N-DOF):  H = Σ(p_i²/(2m)) + V(q)  (separable)
        """
        ke = _kinetic(p, self.mass)
        if self.potential_fn is not None:
            pe = self.potential_fn(q)
        else:
            pe = _default_potential(q, self.spring_constant)
        return ke + pe

    # ── Force Computation ────────────────────────────────────────────

    def _force(self, q: float | np.ndarray) -> float | np.ndarray:
        """F = -dV/dq.  Analytical for harmonic oscillator, numerical for custom."""
        if self.potential_fn is not None:
            eps = 1e-6
            if isinstance(q, np.ndarray):
                grad = np.zeros_like(q)
                for i in range(len(q)):
                    q_plus = q.copy()
                    q_minus = q.copy()
                    q_plus[i] += eps
                    q_minus[i] -= eps
                    grad[i] = (self.potential_fn(q_plus) - self.potential_fn(q_minus)) / (2 * eps)
                return -grad
            else:
                return -(self.potential_fn(q + eps) - self.potential_fn(q - eps)) / (2 * eps)
        return -self.spring_constant * q

    # ── Leapfrog Integration ────────────────────────────────────────

    def _apply_step(self, q: float | np.ndarray, p: float | np.ndarray,
                    dt: float) -> tuple[float | np.ndarray, float | np.ndarray]:
        """One leapfrog substep: p_half → q_new → p_new."""
        p_half = p + 0.5 * dt * self._force(q)  # F = -dV/dq, so p += dt*F/2
        q_new = q + dt * (p_half / self.mass)
        p_new = p_half + 0.5 * dt * self._force(q_new)
        if self.damping > 0:
            p_new = p_new * (1.0 - self.damping * dt)
        return q_new, p_new

    def step(self, q: float | np.ndarray, p: float | np.ndarray,
             dt: float = 0.01) -> tuple[float | np.ndarray, float | np.ndarray]:
        """
        Leapfrog (symplectic) integration step.
        Uses internal sub-stepping for large dt to maintain energy conservation.
        """
        e_before = self.compute_energy(q, p)

        abs_dt = abs(dt)
        if abs_dt > self._BASE_DT:
            n = int(abs_dt // self._BASE_DT)
            rem = abs_dt - n * self._BASE_DT
            sign = 1.0 if dt > 0 else -1.0
            q_cur, p_cur = q, p
            for _ in range(n):
                q_cur, p_cur = self._apply_step(q_cur, p_cur, sign * self._BASE_DT)
            if rem > 1e-12:
                q_cur, p_cur = self._apply_step(q_cur, p_cur, sign * rem)
            q_new, p_new = q_cur, p_cur
        else:
            q_new, p_new = self._apply_step(q, p, dt)

        e_after = self.compute_energy(q_new, p_new)
        drift = abs(e_after - e_before) / max(e_before, 1e-9)

        self._history.append({
            "q": q_new, "p": p_new, "energy": e_after, "drift": drift,
        })
        self._integration_error += drift

        # Phase 5.0: Physical red line protection
        if drift > self.CRITICAL_DRIFT_THRESHOLD:
            self._high_drift_streak += 1
        else:
            self._high_drift_streak = max(0, self._high_drift_streak - 1)

        if self._high_drift_streak == 0 and len(self._history) % 100 == 0:
            self.save_checkpoint()

        if self._high_drift_streak >= self.CRITICAL_DRIFT_STREAK:
            if self.restore_checkpoint():
                self._high_drift_streak = 0
                logger.critical(
                    "Physics red line: energy drift %.2f%% exceeds threshold "
                    "for %d consecutive steps — rolled back to last stable checkpoint",
                    drift * 100, self.CRITICAL_DRIFT_STREAK,
                )

        return q_new, p_new

    def predict(self, q: float | np.ndarray, p: float | np.ndarray,
                steps: int = 100) -> tuple[float | np.ndarray, float | np.ndarray]:
        """Predict state after N steps."""
        for _ in range(steps):
            q, p = self.step(q, p)
        return q, p

    def compute_surprise(self, predicted_state: dict, actual_state: dict) -> float:
        """
        Compute surprise: deviation from physical expectation.

        Args:
            predicted_state: {"q": ..., "p": ...}
            actual_state: {"q": ..., "p": ...}

        Returns:
            surprise ∈ [0, 1]: 0 = perfectly physical, 1 = completely unexpected
        """
        e_pred = self.compute_energy(
            predicted_state.get("q", 0.0), predicted_state.get("p", 0.0)
        )
        e_actual = self.compute_energy(
            actual_state.get("q", 0.0), actual_state.get("p", 0.0)
        )
        drift = abs(e_pred - e_actual) / max(e_actual, 1e-9)
        return min(1.0, drift / 0.1)

    def adapt_caution(self, surprise: float, adaptation_rate: float = 0.1) -> None:
        """Adjust damping based on surprise signal."""
        if surprise > 0.3:
            self.damping = min(0.5, self.damping + surprise * adaptation_rate)
            logger.debug("High surprise %.2f → damping increased to %.3f", surprise, self.damping)
        elif surprise < 0.05 and self.damping > 0.01:
            self.damping = max(0.01, self.damping * 0.99)

    def adapt(self) -> None:
        """
        Self-adaptation: tune damping based on recent drift.
        If energy drift consistently exceeds 0.1%, increase damping to stabilize.
        """
        if len(self._history) < 10:
            return

        recent = [h["drift"] for h in list(self._history)[-10:]]
        avg_drift = sum(recent) / len(recent)

        if avg_drift > 0.001:
            self.damping += 0.0001 * avg_drift
        elif avg_drift < 0.00001 and self.damping > 0:
            self.damping *= 0.99

        self._integration_error = 0.0

    def get_health(self) -> dict[str, float]:
        """Health check for monitoring."""
        if len(self._history) < 10:
            return {
                "status": "warming",
                "avg_drift": 0.0,
                "damping": self.damping,
                "total_energy": self._history[-1]["energy"] if self._history else 0.0,
            }

        recent = [h["drift"] for h in list(self._history)[-10:]]
        avg_drift = sum(recent) / len(recent)

        return {
            "status": "healthy" if avg_drift < 0.001 else "adapting",
            "avg_drift": avg_drift,
            "damping": self.damping,
            "total_energy": self._history[-1]["energy"] if self._history else 0.0,
        }

    @property
    def history(self) -> deque:
        """Public read-only access for testing/debugging."""
        return self._history

    def save_checkpoint(self) -> None:
        """Save current physical parameters as a stable checkpoint."""
        self._checkpoint_weights = copy.deepcopy(self.state_dict())

    def restore_checkpoint(self) -> bool:
        """Restore physical parameters from last checkpoint."""
        if self._checkpoint_weights is None:
            return False
        self.load_state_dict(self._checkpoint_weights)
        return True
