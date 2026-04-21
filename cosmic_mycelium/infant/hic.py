"""
HIC (Homeostasis & Invariant Core) — The "Personality Core"
The不可动摇的人格底线 — energy management, breath cycles, suspend logic.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

from cosmic_mycelium.common.data_packet import CosmicPacket


class BreathState(Enum):
    """Breath cycle states — the rhythm of silicon life."""
    CONTRACT = "contract"   # Contraction: high-intensity exploration
    DIFFUSE = "diffuse"     # Diffusion: recovery & reflection
    SUSPEND = "suspend"     # Suspended: waiting, not acting


class SuspendedError(RuntimeError):
    """Raised when an action is attempted while HIC is SUSPENDED."""
    pass


@dataclass
class HICConfig:
    """Configuration for the HIC core — the life parameters."""
    energy_max: float = 100.0
    contract_duration: float = 0.055   # 55ms contraction
    diffuse_duration: float = 0.005    # 5ms diffusion
    suspend_duration: float = 5.0      # 5s suspend
    recovery_energy: float = 60.0      # Energy after recovery from suspend
    recovery_rate: float = 0.5         # Energy gain per DIFFUSE tick


@dataclass
class HIC:
    """
    Homeostasis & Invariant Core.

    The "人格底线" — the irreducible core that defines the infant's
    boundaries: energy limits, breath rhythm, suspension triggers.

    This is what makes the infant a "being" rather than a "tool".
    """

    # Configuration (immutable after construction)
    config: HICConfig = field(default_factory=HICConfig)

    # Identity
    name: str = field(default="hic-core")

    # Thread safety — all mutable state guarded by this lock
    _lock: threading.RLock = field(init=False, default_factory=threading.RLock)

    # Private mutable state (ALL access must hold _lock)
    _energy: float = field(init=False)
    _state: BreathState = field(init=False, default=BreathState.CONTRACT)
    _last_switch: float = field(init=False, default_factory=time.monotonic)
    _suspend_end_time: float = field(init=False, default=0.0)

    # Counters (protected by _lock)
    total_cycles: int = field(default=0)
    suspend_count: int = field(default=0)
    adaptation_count: int = field(default=0)

    # Value vector (can be adapted by value flow) — protected by _lock
    value_vector: Dict[str, float] = field(default_factory=lambda: {
        "self_preservation": 1.0,
        "mutual_benefit": 1.0,
        "curiosity": 0.7,
        "caution": 0.5,
    })

    def __post_init__(self):
        self._energy = self.config.energy_max

    # ─── Internal helpers (all assume lock already held) ─────────────────────
    def _tick(self, now: float) -> None:
        """Advance the breath cycle one step. Caller MUST hold _lock."""
        if self._state == BreathState.CONTRACT:
            if now - self._last_switch >= self.config.contract_duration:
                self._state = BreathState.DIFFUSE
                self._last_switch = now
                self.total_cycles += 1
                self._energy -= 0.1  # Work consumes energy

        elif self._state == BreathState.DIFFUSE:
            if now - self._last_switch >= self.config.diffuse_duration:
                self._state = BreathState.CONTRACT
                self._last_switch = now
                self._energy = min(
                    self.config.energy_max,
                    self._energy + self.config.recovery_rate,
                )

        elif self._state == BreathState.SUSPEND:
            if now >= self._suspend_end_time:
                # Recovery complete — restore to configured recovery_energy (not additive)
                self._state = BreathState.CONTRACT
                self._last_switch = now
                self._energy = self.config.recovery_energy

    def _enter_suspend(self, now: float) -> None:
        """Transition into SUSPEND state. Caller MUST hold _lock."""
        self._state = BreathState.SUSPEND
        self._last_switch = now
        self._suspend_end_time = now + self.config.suspend_duration
        self.suspend_count += 1

    # ─── Public API (all state changes atomic under _lock) ───────────────────
    def update_breath(self, confidence: float, work_done: bool) -> BreathState:
        """
        Advance the breath cycle — the infant's heartbeat.

        Priority order (all atomic under a single lock):
        1. SUSPEND check (highest priority — survival first)
        2. Normal breath cycle (CONTRACT ↔ DIFFUSE)
        3. Energy updates

        Returns the current BreathState after the update.
        """
        now = time.monotonic()

        with self._lock:
            # ── 1. SUSPEND TRIGGER CHECK ────────────────────────────────────
            # Enter SUSPEND if energy critically low or confidence collapsed.
            if self._energy < 20.0 or confidence < 0.3:
                if self._state != BreathState.SUSPEND:
                    self._enter_suspend(now)
            # else: conditions met — we stay in (or return to) CONTRACT/DIFFUSE

            # ── 2. TICK (handles both normal cycling and SUSPEND recovery) ──
            # Always tick so SUSPEND countdown progresses and recovery occurs.
            self._tick(now)
            return self._state

    def adapt_value_vector(self, feedback: Dict[str, float]) -> None:
        """
        Adapt intrinsic values based on external feedback.
        This is the "value flow" rewriting the HIC's personality.
        """
        with self._lock:
            for key, delta in feedback.items():
                if key in self.value_vector:
                    new_val = self.value_vector[key] + delta
                    self.value_vector[key] = max(0.1, min(2.0, new_val))
            self.adaptation_count += 1

    def get_suspend_packet(self, source_id: str) -> "CosmicPacket":
        """
        Generate a SUSPEND data packet to broadcast to peers.
        Safe to call outside the lock — captures a consistent snapshot.
        """
        with self._lock:
            return CosmicPacket(
                timestamp=time.time(),
                source_id=source_id,
                value_payload={
                    "action": "suspend",
                    "reason": "low_energy" if self._energy < 20 else "low_confidence",
                    "energy": self._energy,
                    "value_vector": self.value_vector.copy(),
                },
            )

    def get_status(self) -> Dict:
        """Full status snapshot — consistent view of all HIC counters."""
        with self._lock:
            return {
                "energy": self._energy,
                "energy_max": self.config.energy_max,
                "state": self._state.value,
                "total_cycles": self.total_cycles,
                "suspend_count": self.suspend_count,
                "adaptation_count": self.adaptation_count,
                "value_vector": self.value_vector.copy(),
                "contract_duration": self.config.contract_duration,
                "diffuse_duration": self.config.diffuse_duration,
                "suspend_duration": self.config.suspend_duration,
            }

    # ─── Read-only properties (brief lock, no mutation) ─────────────────────
    @property
    def energy(self) -> float:
        with self._lock:
            return self._energy

    @property
    def state(self) -> BreathState:
        with self._lock:
            return self._state

    @property
    def is_suspended(self) -> bool:
        with self._lock:
            return self._state == BreathState.SUSPEND

    @property
    def suspend_remaining(self) -> float:
        """Seconds remaining in current SUSPEND (0 if not suspended)."""
        with self._lock:
            if self._state != BreathState.SUSPEND:
                return 0.0
            remaining = self._suspend_end_time - time.monotonic()
            return max(0.0, remaining)

    @property
    def value_vector_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return self.value_vector.copy()
