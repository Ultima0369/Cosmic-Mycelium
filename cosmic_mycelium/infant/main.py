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
from cosmic_mycelium.infant.core.layer_2_semantic_mapper import SemanticMapper
from cosmic_mycelium.infant.core.layer_3_slime_explorer import SlimeExplorer
from cosmic_mycelium.infant.core.layer_4_myelination_memory import MyelinationMemory
from cosmic_mycelium.infant.core.layer_5_superbrain import SuperBrain
from cosmic_mycelium.infant.core.layer_6_symbiosis_interface import SymbiosisInterface, InteractionMode
from cosmic_mycelium.infant.sensors import SensorArray, SensorType
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
        # Layer 2: Semantic Mapper — maps physical → semantic concepts
        embedding_dim = self.config.get("embedding_dim", 16)
        self.semantic_mapper = SemanticMapper(embedding_dim=embedding_dim)
        self.explorer = SlimeExplorer(num_spores=self.config.get("num_spores", 10))
        self.memory = MyelinationMemory()
        self.brain = SuperBrain()
        self.interface = SymbiosisInterface(infant_id)

        # Sensor array — real-world multi-modal perception
        self.sensors = SensorArray()

        # Physical state (derived from sensors, cached)
        self.state = {"q": 1.0, "p": 0.0}
        self._last_perception: Optional[Dict] = None
        self._latest_embedding: Optional[object] = None  # np.ndarray from SemanticMapper

        # Network reference (set by MyceliumNetwork.join)
        self.network: Optional[Any] = None

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
        Sense the world via multi-modal sensor array.
        Reads vibration, temperature, spectrum and maps to physical state (q, p).
        Also maps physical state to semantic concept (L2).
        """
        # Read all sensors
        sensor_data = self.sensors.read_all()

        # Map multi-modal sensors → physical state (q, p)
        vibration = sensor_data["vibration"]
        temperature = sensor_data["temperature"]
        spectrum = sensor_data["spectrum_power"]

        # Update physical state with bounded random walk
        self.state["p"] = max(-1.0, min(1.0, self.state["p"] + vibration * 0.01 + random.uniform(-0.005, 0.005)))
        self.state["q"] = max(-1.0, min(1.0, self.state["q"] + (temperature - 22.0) * 0.001 + spectrum * 0.005))

        # L2: Map physical state to semantic concept
        physical_state = self.state.copy()
        concept = self.semantic_mapper.map(physical_state)
        self._latest_embedding = concept.feature_vector.copy()

        # Attach raw sensor data and semantic embedding to perception
        perception = {
            "timestamp": time.time(),
            "physical": physical_state,
            "sensors": sensor_data,
            "semantic_embedding": self._latest_embedding,
            "external": {},
        }
        self._last_perception = perception
        return perception

    def disambiguate_intent(self, perception: Dict, confidence: float) -> Optional[str]:
        """
        Intent disambiguation: when confidence is low, generate clarification question.

        Returns:
            Clarification question string, or None if confidence is adequate.
        """
        if confidence >= 0.5:
            return None  # No ambiguity

        # Analyze sensor pattern to infer likely cause of low confidence
        sensors = perception.get("sensors", {})
        vibration = sensors.get("vibration", 0)
        temperature = sensors.get("temperature", 22.0)
        spectrum = sensors.get("spectrum_power", 0)

        # Heuristic: match low-confidence patterns to question templates
        if vibration > 0.2:
            return "Is that vibration from machinery or environmental movement?"
        if temperature > 28.0 or temperature < 16.0:
            return f"Temperature is {temperature:.1f}°C — is that expected?"
        if spectrum < 0.2:
            return "Light level very low — should I wait for more illumination?"
        if spectrum > 2.0:
            return "Very bright environment — requires adaptation?"

        # Generic fallback
        return "Perception unclear — what should I focus on?"

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

        # Intent disambiguation: if low confidence, emit a clarification request
        question = self.disambiguate_intent(perception, confidence)
        if question:
            # Enter low-confidence SUSPEND but with a clarifying question
            self._log(f"Clarification needed: {question}", "WARN")
            # Emit a query packet to potential partners (suspended until answered)
            return CosmicPacket(
                timestamp=time.time(),
                source_id=self.infant_id,
                destination_id="broadcast",
                value_payload={
                    "action": "query",
                    "question": question,
                    "context": perception.get("sensors", {}),
                },
            )

        # Plan using slime explorer
        plan, plan_conf = self.explorer.plan(perception, "stable_orbit")
        if plan is None:
            return self.hic.get_suspend_packet(self.infant_id)

        # Record successful path
        self.memory.reinforce(plan["path"], success=True)

        # Build packet — action broadcast to network
        return CosmicPacket(
            timestamp=time.time(),
            source_id=self.infant_id,
            value_payload={
                "action": "plan_execution",
                "plan": plan,
                "confidence": plan_conf,
                "sensor_snapshot": perception.get("sensors", {}),
            },
        )

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
            time.sleep(self.hic.config.suspend_duration)
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

    def get_embedding(self) -> Optional[object]:
        """Return latest semantic embedding (for resonance)."""
        return self._latest_embedding

    def get_physical_fingerprint(self) -> str:
        """Generate physical fingerprint from current physical state."""
        return PhysicalFingerprint.generate(self.state)

    def apply_resonance_bonus(self, partner_id: str, similarity: float) -> None:
        """
        Apply 1+1>2 energy bonus from high-resonance with partner.

        Args:
            partner_id: The partner infant ID.
            similarity: Cosine similarity [0,1] of semantic embeddings.
        """
        if similarity < 0.6:
            return  # Below resonance threshold
        # Synergy bonus: max 0.2 energy, scaled by similarity above threshold
        bonus = min(0.2, (similarity - 0.6) * 0.5)
        self.hic._energy = min(self.hic.config.energy_max, self.hic._energy + bonus)
        # Record positive interaction with partner
        self.interface.perceive_partner(partner_id, trust=0.6, mode=InteractionMode.COLLABORATE)
        self._log(f"Resonance bonus +{bonus:.3f} with {partner_id} (sim={similarity:.2f})")
