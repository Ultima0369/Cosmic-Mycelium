"""
Layer 5 — SuperBrain (SuperBrain Layer)
Multi-brain region collaboration, attention competition, global workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from collections import deque
import numpy as np
import time


@dataclass
class RegionConfig:
    """Static configuration for a brain region."""
    name: str
    specialty: str
    capacity: int = 100
    activation_threshold: float = 0.3


@dataclass
class RegionActivity:
    """Snapshot of a region's current activity state."""
    name: str
    activation: float
    memory_count: int
    last_update: float


@dataclass
class BrainRegion:
    """A specialized processing region."""
    name: str
    specialty: str  # e.g., "pattern", "prediction", "action"
    activation: float = 0.0
    working_memory: deque = field(default_factory=lambda: deque(maxlen=100))


class SuperBrain:
    """
    Layer 5: SuperBrain.

    Manages multiple specialized brain regions.
    Handles attention allocation and global workspace broadcasting.
    """

    def __init__(self, region_names: List[str] | None = None):
        self.regions: Dict[str, BrainRegion] = {}
        self.global_workspace: Optional[Dict] = None
        self.attention_threshold = 0.3

        # Default regions (includes executor, not motor)
        default_regions = [
            ("sensory", "perception"),
            ("predictor", "forecasting"),
            ("planner", "planning"),
            ("executor", "action"),
            ("meta", "metacognition"),
        ]

        for name, specialty in region_names or default_regions:
            self.regions[name] = BrainRegion(name=name, specialty=specialty)

    @property
    def num_regions(self) -> int:
        """Number of registered brain regions."""
        return len(self.regions)

    def perceive(self, stimulus: Dict) -> None:
        """Route stimulus to appropriate region."""
        # Simple: always route to sensory first
        sensory = self.regions["sensory"]
        sensory.activation = min(1.0, sensory.activation + 0.3)
        sensory.working_memory.append(stimulus)
        if len(sensory.working_memory) > 100:
            sensory.working_memory.pop(0)

    def predict(self, context: Dict) -> Dict:
        """Generate prediction from predictor region."""
        predictor = self.regions["predictor"]
        predictor.activation = min(1.0, predictor.activation + 0.2)

        # Simplified prediction (in real system, would use learned model)
        prediction = {
            "next_state": context,
            "confidence": predictor.activation,
        }
        return prediction

    def plan(self, goal: Optional[Dict] = None, options: Optional[List[Dict]] = None) -> Optional[Dict]:
        """
        Select best plan from options.
        If options is None, generate synthetic options.
        Returns chosen plan dict with 'path' and 'quality' keys, or None.
        """
        planner = self.regions["planner"]
        planner.activation = min(1.0, planner.activation + 0.4)

        if options is None:
            # Generate synthetic options based on goal hash for determinism
            goal_hash = hash(str(goal)) % 100
            options = [
                {"path": "default", "quality": 0.7},
                {"path": "alternate", "quality": 0.4 + (goal_hash % 30) / 100.0},
            ]

        if not options:
            return None

        best = max(options, key=lambda o: o.get("quality", 0.0))
        if best.get("quality", 0) < 0.5:
            return None

        return {
            "path": best.get("path", "derived"),
            "quality": float(best.get("quality", 0.0)),
        }

    def broadcast_global_workspace(self, content: Dict) -> None:
        """Broadcast to global workspace (all regions can access)."""
        self.global_workspace = content
        # Boost all region activations slightly
        for region in self.regions.values():
            region.activation = min(1.0, region.activation + 0.1)
        # Meta region logs all broadcasts
        if "meta" in self.regions:
            self.regions["meta"].working_memory.append(content)

    def execute(self, action: Dict) -> None:
        """Execute an action via the executor region."""
        executor = self.regions["executor"]
        executor.activation = min(1.0, executor.activation + 0.3)
        executor.working_memory.append(action)
        if len(executor.working_memory) > 100:
            executor.working_memory.popleft()

    def decay_activations(self, decay_factor: float = 0.1) -> None:
        """Activity naturally decays by multiplicative factor."""
        for region in self.regions.values():
            region.activation = max(0.0, region.activation * decay_factor)

    def get_status(self) -> Dict:
        """Return brain status."""
        return {
            "regions": {
                name: {
                    "activation": round(r.activation, 3),
                    "specialty": r.specialty,
                    "working_memory_len": len(r.working_memory),
                }
                for name, r in self.regions.items()
            },
            "global_workspace": self.global_workspace is not None,
        }
