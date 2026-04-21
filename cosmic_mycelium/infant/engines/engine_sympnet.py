"""
SympNet Engine — The "Physics Anchor"
Hamiltonian Neural Network that enforces energy conservation.
This is the physical foundation: energy drift must stay < 0.1%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple
from collections import deque
import numpy as np


@dataclass
class SympNetEngine:
    """
    Symplectic Neural Network Engine.

    Implements a Hamiltonian Neural Network (HNN) that learns and respects
    energy conservation. In MVP, it's a harmonic oscillator with symplectic
    integration (leapfrog).

    Physical Anchor: Over 1M steps, energy drift must stay < 0.1%.
    """

    mass: float = 1.0
    spring_constant: float = 1.0
    damping: float = 0.0

    # Internal state
    _history: deque = field(default_factory=lambda: deque(maxlen=1000))
    _integration_error: float = 0.0

    # Base timestep for internal sub-stepping to ensure energy conservation
    _BASE_DT: float = field(init=False, default=0.01, compare=False)

    def compute_energy(self, q: float, p: float) -> float:
        """
        Hamiltonian: H(q,p) = p²/(2m) + ½ k q²
        """
        kinetic = (p * p) / (2.0 * self.mass)
        potential = 0.5 * self.spring_constant * (q * q)
        return kinetic + potential

    def _apply_step(self, q: float, p: float, dt: float) -> Tuple[float, float]:
        """
        Apply one corrected leapfrog substep.
        Force = -k * q (no mass division in force term).
        """
        p_half = p - 0.5 * dt * self.spring_constant * q
        q_new = q + dt * (p_half / self.mass)
        p_new = p_half - 0.5 * dt * self.spring_constant * q_new
        if self.damping > 0:
            p_new *= (1.0 - self.damping * dt)
        return q_new, p_new

    def step(self, q: float, p: float, dt: float = 0.01) -> Tuple[float, float]:
        """
        Leapfrog (symplectic) integration step.

        Uses internal sub-stepping for large dt to maintain energy conservation.
        """
        e_before = self.compute_energy(q, p)

        # Determine if sub-stepping is needed
        abs_dt = abs(dt)
        if abs_dt > self._BASE_DT:
            # Sub-step with fixed base timestep
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
            "q": q_new,
            "p": p_new,
            "energy": e_after,
            "drift": drift,
        })
        self._integration_error += drift

        return q_new, p_new

    def predict(self, q: float, p: float, steps: int = 100) -> Tuple[float, float]:
        """Predict state after N steps."""
        for _ in range(steps):
            q, p = self.step(q, p)
        return q, p

    def adapt(self) -> None:
        """
        Self-adaptation: tune damping based on recent drift.

        If energy drift consistently exceeds 0.1%, slightly increase damping
        to stabilize. This is the "being rewritten by physics" mechanism.
        """
        if len(self._history) < 10:
            return

        recent = [h["drift"] for h in list(self._history)[-10:]]
        avg_drift = sum(recent) / len(recent)

        # Threshold: 0.1%
        if avg_drift > 0.001:
            # Increase damping to suppress drift
            self.damping += 0.0001 * avg_drift
        elif avg_drift < 0.00001 and self.damping > 0:
            # Decay damping slowly
            self.damping *= 0.99

        self._integration_error = 0.0

    def get_health(self) -> Dict[str, float]:
        """Health check — used for monitoring."""
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
        """Public read-only access to history for testing/debugging."""
        return self._history
