"""
Layer 3 — Slime Mold Explorer (Slime Mold Layer)
Motivation-vision path search, multi-objective optimization.
Mimics slime mold's parallel "discharge" and convergence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import random
import time


@dataclass
class Spore:
    """A parallel exploration branch."""
    id: str
    path: List[str] = field(default_factory=list)
    energy: float = 1.0
    quality: float = 0.0
    age: int = 0


class SlimeExplorer:
    """
    Layer 3: Slime Mold Exploration.

    Explores multiple paths in parallel like slime mold branches.
    Selects best path via "convergence" (like slime mold choosing food source).
    """

    def __init__(self, num_spores: int = 10):
        self.num_spores = num_spores
        self.spores: List[Spore] = []
        self.pheromone_map: Dict[str, float] = {}
        self.success_history: list = []
        self.rng = random.Random(42)  # Deterministic RNG for reproducible exploration
        self._spore_counter = 0  # For deterministic IDs

    def explore(self, context: Dict, goal_hint: Optional[str] = None) -> List[Spore]:
        """
        Release spores to explore multiple paths simultaneously.
        Returns list of spores with their explored paths.
        """
        self.spores.clear()
        for i in range(self.num_spores):
            # Deterministic ID using counter + RNG-derived component
            spore_id = f"spore_{self._spore_counter:06d}_{i}"
            self._spore_counter += 1

            spore = Spore(
                id=spore_id,
                energy=self.rng.uniform(0.5, 1.5),
            )

            # Generate a random path (simplified exploration)
            path_length = self.rng.randint(1, 5)
            for step in range(path_length):
                action = f"action_{step}_{self.rng.randint(0, 9)}"
                spore.path.append(action)

            # Evaluate path quality
            spore.quality = self._evaluate_path(spore.path, goal_hint)
            self.spores.append(spore)

        return self.spores

    def _evaluate_path(self, path: List[str], goal: Optional[str]) -> float:
        """Evaluate how good a path is."""
        if not path:
            return 0.0

        # Pheromone strength (paths taken before are more attractive)
        path_key = "->".join(path)
        pheromone = self.pheromone_map.get(path_key, 0.1)

        # Goal alignment
        goal_bonus = 0.0
        if goal and path:
            if goal.lower() in path[-1].lower():
                goal_bonus = 0.5

        return pheromone * 0.7 + goal_bonus * 0.3

    def converge(self, threshold: float = 0.6, spores: Optional[List[Spore]] = None) -> Optional[Spore]:
        """
        Converge on the best spore (best path).
        Returns None if no spore meets confidence threshold.
        If spores not provided, uses self.spores.
        """
        spores = spores if spores is not None else self.spores
        if not spores:
            return None

        best = max(spores, key=lambda s: s.quality)

        if best.quality < threshold:
            return None  # Confidence too low

        # Reinforce successful path
        path_key = "->".join(best.path)
        self.pheromone_map[path_key] = self.pheromone_map.get(path_key, 0.0) * 1.2

        # Evaporate all pheromones slightly
        for key in list(self.pheromone_map.keys()):
            self.pheromone_map[key] *= 0.99
            if self.pheromone_map[key] < 0.01:
                del self.pheromone_map[key]

        self.success_history.append({
            "path": best.path,
            "quality": best.quality,
            "timestamp": time.time(),
        })

        return best

    def plan(self, context: Dict, goal_hint: Optional[str] = None) -> tuple[Optional[Dict], float]:
        """
        Full explore-converge cycle.
        Returns (best_plan, confidence) or (None, 0.0) if no confident plan.
        """
        spores = self.explore(context, goal_hint)
        best = self.converge(spores=spores)  # Use keyword to avoid threshold confusion

        if best:
            return {
                "path": best.path,
                "quality": best.quality,
                "energy": best.energy,
            }, best.quality
        return None, 0.0

    def reinforce_path(self, path: List[str], delta: float = 0.1, decay: float = 1.0) -> float:
        """
        Explicitly reinforce a path's pheromone.

        Formula: new = (current + delta) * decay

        Args:
            path: List of action strings forming the path.
            delta: Amount to add to pheromone.
            decay: Multiplicative factor applied after addition (default 1.0 = no decay).

        Returns:
            New pheromone value for the path.
        """
        path_key = "->".join(path)
        current = self.pheromone_map.get(path_key, 0.0)
        new_val = (current + delta) * decay
        self.pheromone_map[path_key] = new_val
        return new_val
