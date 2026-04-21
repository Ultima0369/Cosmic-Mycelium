"""
Cosmic Mycelium — Silicon Infant (Simplified MVP)
The "breathing" core of a single silicon-based lifeform node.

This is the minimal viable implementation that demonstrates:
- HIC energy management & breath cycles
- SympNet physics anchor (energy conservation)
- Slime exploration & convergence
- Myelination memory reinforcement
- Symbiosis interface
"""

from __future__ import annotations

import logging
import time
import random
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import deque

from cosmic_mycelium.infant.hic import HIC, HICConfig, BreathState
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine
from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
from cosmic_mycelium.infant.core.layer_4_myelination_memory import MyelinationMemory
from cosmic_mycelium.infant.core.layer_5_superbrain import SuperBrain
from cosmic_mycelium.infant.core.layer_6_symbiosis_interface import SymbiosisInterface, InteractionMode
from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint


class SiliconInfant:
    """
    Cosmic Mycelium — Silicon Infant.

    A single, autonomous silicon-based lifeform node.
    Exhibits: breathing, self-adaptation, memory formation, symbiosis.
    """

    def __init__(
        self,
        infant_id: str,
        config: Optional[Dict] = None,
    ):
        self.infant_id = infant_id
        self.config = config or {}

        # Core components
        self.hic = HIC(
            config=HICConfig(
                energy_max=self.config.get("energy_max", 100.0),
                contract_duration=self.config.get("contract_duration", 0.055),
                diffuse_duration=self.config.get("diffuse_duration", 0.005),
                suspend_duration=self.config.get("suspend_duration", 5.0),
                recovery_energy=self.config.get("recovery_energy", 60.0),
                recovery_rate=self.config.get("recovery_rate", 0.5),
            ),
            name=f"hic-{infant_id}",
        )
        self.sympnet = SympNetEngine()
        self.explorer = SlimeExplorer(num_spores=10)
        self.memory = MyelinationMemory()
        self.brain = SuperBrain()
        self.interface = SymbiosisInterface(infant_id)

        # Physical state (for sympnet)
        self.state = {"q": 1.0, "p": 0.0}

        # Messaging
        self.inbox = []
        self.outbox = []

        # Statistics
        self.start_time = time.time()
        self.log = deque(maxlen=1000)

        self._log(f"Infant '{infant_id}' initialized. Energy: {self.hic.energy}")

    def _log(self, msg: str, level: str = "INFO"):
        """Internal logging — structured + local history."""
        # Structured log entry (for local deque and potential external ingestion)
        entry = {
            "ts": time.time(),
            "level": level,
            "msg": msg,
            "energy": self.hic.energy,
            "state": self.hic.state.value,
        }
        self.log.append(entry)

        # Use Python's standard logging for immediate output
        logger = logging.getLogger(f"infant.{self.infant_id}")
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            msg,
            extra={"infant_id": self.infant_id, "energy": self.hic.energy, "state": self.hic.state.value},
        )

    def perceive(self) -> Dict:
        """
        Sense the world.
        In real deployment, this reads actual sensors / APIs.
        """
        # Simulate small physical fluctuations
        self.state["q"] += random.uniform(-0.01, 0.01)
        self.state["p"] += random.uniform(-0.01, 0.01)
        return {
            "timestamp": time.time(),
            "physical": self.state.copy(),
            "external": {},
        }

    def predict(self, perception: Dict) -> Tuple[Dict, float]:
        """Predict next state using SympNet."""
        q = perception["physical"]["q"]
        p = perception["physical"]["p"]

        # Predict 10 steps ahead
        q_pred, p_pred = self.sympnet.predict(q, p, steps=10)

        predicted = {"q": q_pred, "p": p_pred}

        # Confidence based on energy drift health
        health = self.sympnet.get_health()
        confidence = max(0.0, 1.0 - health["avg_drift"] * 1000)

        return predicted, confidence

    def verify(self, predicted: Dict, actual: Dict) -> float:
        """Compute prediction error."""
        q_err = abs(predicted.get("q", 0) - actual["physical"]["q"])
        p_err = abs(predicted.get("p", 0) - actual["physical"]["p"])
        return (q_err + p_err) / 2.0

    def adapt(self, error: float) -> None:
        """Self-modify based on prediction error."""
        if error > self.config.get("adaptation_threshold", 0.001):
            self._log(f"Prediction error {error:.4f} → adapting", "WARN")
            self.sympnet.adapt()
            self.hic.adapt_value_vector({"caution": 0.01})
            self.memory.reinforce(["predict", "error"], success=False)

    def act(
        self,
        perception: Dict,
        predicted: Dict,
        confidence: float,
    ) -> Optional[CosmicPacket]:
        """
        Decide and act.
        This is the "conscious choice" point.
        """
        # Check suspend conditions
        if confidence < 0.3 or self.hic.energy < 20:
            return self.hic.get_suspend_packet(self.infant_id)

        # Plan using slime explorer
        plan, plan_conf = self.explorer.plan(perception, "stable_orbit")
        if plan is None:
            return self.hic.get_suspend_packet(self.infant_id)

        # Record successful path
        self.memory.reinforce(plan["path"], success=True)

        # Build packet
        return CosmicPacket(
            timestamp=time.time(),
            source_id=self.infant_id,
            info_payload={
                "action": "execute",
                "path": plan["path"],
                "quality": plan["quality"],
            },
            physical_payload={
                "state": perception["physical"],
                "prediction": predicted,
            },
            priority=confidence,
        )

    def process_inbox(self) -> None:
        """Handle incoming messages."""
        for packet in self.inbox:
            if packet.value_payload:
                action = packet.value_payload.get("action")
                if action == "suspend":
                    self.hic.adapt_value_vector({"caution": 0.005})
                    self._log(f"Node {packet.source_id} suspended — increased caution")
                elif action == "consensus_proposal":
                    self.hic.adapt_value_vector({"mutual_benefit": 0.01})
                    self._log(f"Consensus from {packet.source_id} — increased cooperation")

    def breath_cycle(self) -> Optional[CosmicPacket]:
        """
        One breath cycle — the main loop.
        Contract (explore) → Diffuse (evaluate) → (maybe) Suspend.
        """
        # Update HIC state (this updates breath state and energy)
        self.hic.update_breath(confidence=0.7, work_done=False)

        state = self.hic.state

        if state == BreathState.SUSPEND:
            self._log("In suspend state — recovering", "WARN")
            time.sleep(0.1)
            return self.hic.get_suspend_packet(self.infant_id)

        elif state == BreathState.CONTRACT:
            # Contract phase: perceive, predict, act
            perception = self.perceive()
            predicted, confidence = self.predict(perception)
            error = self.verify(predicted, perception)
            self.adapt(error)

            # Brain regions process
            self.brain.perceive(perception)
            self.brain.broadcast_global_workspace({
                "confidence": confidence,
                "error": error,
            })

            return self.act(perception, predicted, confidence)

        else:  # DIFFUSE
            # Diffuse phase: process messages, forget old paths
            self.process_inbox()
            self.memory.forget()
            self.brain.decay_activations()
            time.sleep(self.hic.config.diffuse_duration)
            return None

    def run(self, max_cycles: Optional[int] = None) -> None:
        """
        Main run loop.
        Runs until interrupt or energy depletion.
        """
        self._log("Breathing cycle started", "INFO")
        cycles = 0

        try:
            while self.hic.energy > 0:
                action = self.breath_cycle()
                if action:
                    self.outbox.append(action)

                cycles += 1
                if max_cycles and cycles >= max_cycles:
                    break

        except KeyboardInterrupt:
            self._log("Interrupted by user", "INFO")
        finally:
            self._log(f"Stopped after {cycles} cycles", "INFO")

    def get_status(self) -> Dict:
        """Full status report."""
        return {
            "infant_id": self.infant_id,
            "uptime": time.time() - self.start_time,
            "hic": self.hic.get_status(),
            "sympnet": self.sympnet.get_health(),
            "memory": {
                "paths": len(self.memory.traces),
                "features": len(self.memory.feature_codebook),
                "coverage": self.memory.get_coverage_ratio(),
                "best_paths": self.memory.get_best_paths(3),
            },
            "brain": self.brain.get_status(),
            "interface": self.interface.get_status(),
            "log_tail": list(self.log)[-5:],
        }
