"""
HIC (Homeostasis & Invariant Core) — The "Personality Core"
The不可动摇的人格底线 — energy management, breath cycles, suspend logic.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

from cosmic_mycelium.common.data_packet import CosmicPacket

logger = logging.getLogger(__name__)


class BreathState(Enum):
    """Breath cycle states — the rhythm of silicon life."""

    CONTRACT = "contract"  # Contraction: high-intensity exploration
    DIFFUSE = "diffuse"  # Diffusion: recovery & reflection
    SUSPEND = "suspend"  # Suspended: waiting, not acting


class SuspendedError(RuntimeError):
    """Raised when an action is attempted while HIC is SUSPENDED."""

    pass


@dataclass
class HICConfig:
    """Configuration for the HIC core — the life parameters."""

    energy_max: float = 100.0
    contract_duration: float = 0.055  # 55ms contraction
    diffuse_duration: float = 0.005  # 5ms diffusion
    suspend_duration: float = 5.0  # 5s suspend
    recovery_energy: float = 60.0  # Energy after recovery from suspend
    recovery_rate: float = 0.5  # Energy gain per DIFFUSE tick

    # Phase 5.0: Hysteresis thresholds for state transitions
    # Prevents chattering near thresholds (生物神经系统惯性)
    suspend_enter_threshold: float = 20.0  # Enter SUSPEND when energy < 20
    suspend_exit_threshold: float = 25.0   # Exit SUSPEND only when energy > 25
    confidence_suspend_threshold: float = 0.3  # Enter SUSPEND when confidence < 0.3
    confidence_resume_threshold: float = 0.5   # Resume only when confidence > 0.5

    # Phase 5.0: Absolute safety底线 (安全底座)
    energy_absolute_min: float = 5.0  # Critical low — enter dormant state


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

    # Phase 5.0: Dormant state (absolute safety底线)
    _dormant_state: bool = field(init=False, default=False)

    # Counters (protected by _lock)
    total_cycles: int = field(default=0)
    suspend_count: int = field(default=0)
    adaptation_count: int = field(default=0)

    # Value vector (can be adapted by value flow) — protected by _lock
    value_vector: dict[str, float] = field(
        default_factory=lambda: {
            "self_preservation": 1.0,
            "mutual_benefit": 1.0,
            "curiosity": 0.7,
            "caution": 0.5,
        }
    )

    def __post_init__(self):
        self._energy = self.config.energy_max

    def _log(self, msg: str, level: str) -> None:
        """Internal structured log — maps level string to logger method."""
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn("[%s] %s", self.name, msg)

    # ─── Internal helpers ──────────────────────────────────────────────────
    def _tick(self, now: float, max_transitions: int = 10) -> None:
        """
        Process state transitions. By default handles all pending transitions.
        For deterministic unit tests, pass max_transitions=1 to step exactly one.
        Lock is acquired internally; callers need not hold it.
        """
        with self._lock:
            for _ in range(max_transitions):
                if self._state == BreathState.CONTRACT:
                    if now - self._last_switch < self.config.contract_duration:
                        break
                    # CONTRACT → DIFFUSE
                    self._state = BreathState.DIFFUSE
                    self._last_switch += self.config.contract_duration
                    self.total_cycles += 1
                    self._energy -= 0.1
                    if self._energy < 0.0:
                        self._energy = 0.0
                    if self._energy < 20.0:
                        self._enter_suspend(now)
                        break

                elif self._state == BreathState.DIFFUSE:
                    if now - self._last_switch < self.config.diffuse_duration:
                        break
                    # DIFFUSE → CONTRACT
                    self._state = BreathState.CONTRACT
                    self._last_switch += self.config.diffuse_duration
                    self._energy = min(
                        self.config.energy_max,
                        self._energy + self.config.recovery_rate,
                    )

                else:  # SUSPEND
                    # Auto-recover when suspend duration elapsed
                    if now >= self._suspend_end_time:
                        self._state = BreathState.CONTRACT
                        self._last_switch = now
                        self._energy = self.config.recovery_energy
                    break

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
        1. Absolute safety check (dormant state) — highest priority
        2. Hysteresis-based SUSPEND/RESUME (lag thresholds)
        3. Normal breath cycle (CONTRACT ↔ DIFFUSE)
        4. Energy updates

        Returns the current BreathState after the update.
        """
        now = time.monotonic()

        with self._lock:
            # ── 0. ABSOLUTE SAFETY CHECK ( dormant state ) ────────────────────
            # Critical low energy triggers permanent SUSPEND until recovery
            if self._energy <= self.config.energy_absolute_min:
                if not self._dormant_state:
                    self._dormant_state = True
                    self._enter_suspend(now)  # Proper transition: sets state, increments count
                    self._log(
                        f"能量触及绝对红线 ({self._energy:.1f} < "
                        f"{self.config.energy_absolute_min})，进入休眠态",
                        "CRITICAL",
                    )
                return BreathState.SUSPEND

            # Exit dormant state when energy recovered sufficiently
            if self._dormant_state and self._energy >= self.config.suspend_exit_threshold:
                self._dormant_state = False
                self._log(f"退出休眠态，能量恢复至 {self._energy:.1f}", "INFO")

            if self._dormant_state:
                return BreathState.SUSPEND

            # ── 1. SUSPEND TRIGGER CHECK (WITH HYSTERESIS) ───────────────────
            # Use different thresholds for entering vs exiting SUSPEND
            if self._state == BreathState.SUSPEND:
                # Exiting SUSPEND requires higher energy AND confidence
                if (self._energy >= self.config.suspend_exit_threshold and
                    confidence >= self.config.confidence_resume_threshold):
                    # Transition: SUSPEND → CONTRACT
                    self._state = BreathState.CONTRACT
                    self._last_switch = now
                    self._energy = self.config.recovery_energy  # 恢复能量
                    self._log(
                        f"退出悬置 → CONTRACT，能量:{self._energy:.1f} "
                        f"置信度:{confidence:.2f}",
                        "INFO",
                    )
                # else: remain in SUSPEND (hysteresis holds)
            else:
                # Currently in CONTRACT or DIFFUSE — check if should enter SUSPEND
                if (self._energy < self.config.suspend_enter_threshold or
                    confidence < self.config.confidence_suspend_threshold):
                    # Transition: → SUSPEND
                    self._state = BreathState.SUSPEND
                    self._last_switch = now
                    self._suspend_end_time = now + self.config.suspend_duration
                    self.suspend_count += 1
                    reason = "low_energy" if self._energy < self.config.suspend_enter_threshold else "low_confidence"
                    self._log(
                        f"进入悬置({reason})，能量:{self._energy:.1f} 置信度:{confidence:.2f}",
                        "WARN",
                    )
                    return self._state
                # else: remain in current state

            # ── 2. TICK (handles both normal cycling and SUSPEND recovery) ──
            # Always tick so SUSPEND countdown progresses and recovery occurs.
            self._tick(now)
            return self._state

    def adapt_value_vector(self, feedback: dict[str, float]) -> None:
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

    def modify_energy(self, delta: float) -> None:
        """
        Adjust energy by delta (positive = restore, negative = consume).
        Energy is clamped to [0, energy_max].

        Thread-safe: acquires lock, intended for MiniInfant-style direct energy
        management. Use with caution — callers should not bypass HIC's intrinsic
        energy cycle logic.
        """
        with self._lock:
            self._energy = max(0.0, min(self.config.energy_max, self._energy + delta))

    def get_suspend_packet(self, source_id: str) -> CosmicPacket:
        """
        Generate a SUSPEND data packet to broadcast to peers.
        Safe to call outside the lock — captures a consistent snapshot.
        """
        with self._lock:
            return CosmicPacket(
                timestamp=time.time(),
                source_id=source_id,
                value_payload={
                    "type": "suspend",
                    "action": "suspend",
                    "reason": "low_energy" if self._energy < 20 else "low_confidence",
                    "energy": self._energy,
                    "value_vector": self.value_vector.copy(),
                },
            )

    def get_status(self) -> dict:
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
    def value_vector_snapshot(self) -> dict[str, float]:
        with self._lock:
            return self.value_vector.copy()
