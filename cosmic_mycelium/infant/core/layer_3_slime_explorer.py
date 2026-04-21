"""
Layer 3 — Slime Mold Explorer (Slime Mold Layer)
Motivation-vision path search, multi-objective optimization.
Mimics slime mold's parallel "discharge" and convergence with learned heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import random
import time
import numpy as np


@dataclass
class Spore:
    """A parallel exploration branch with resource budget."""
    id: str
    path: List[str] = field(default_factory=list)
    energy: float = 1.0
    quality: float = 0.0
    age: int = 0
    visited_nodes: set[str] = field(default_factory=set)


class SlimeExplorer:
    """
    Layer 3: Slime Mold Exploration.

    Explores multiple paths in parallel like slime mold branches.
    Selects best path via "convergence" (like slime mold choosing food source).

    Learning: Pheromone-based path reinforcement with evaporation.
    """

    def __init__(
        self,
        num_spores: int = 10,
        exploration_factor: float = 0.3,
        pheromone_evaporation: float = 0.99,
        min_path_length: int = 1,
        max_path_length: int = 5,
    ):
        self.num_spores = num_spores
        self.exploration_factor = exploration_factor
        self.pheromone_evaporation = pheromone_evaporation
        self.min_path_length = min_path_length
        self.max_path_length = max_path_length
        self.spores: List[Spore] = []
        self.pheromone_map: Dict[str, float] = {}
        self.success_history: list = []
        self.rng = random.Random(42)  # Deterministic RNG
        self._spore_counter = 0

    def explore(self, context: Dict, goal_hint: Optional[str] = None) -> List[Spore]:
        """
        Release spores to explore multiple paths simultaneously.
        Each spore follows a probabilistic policy.
        """
        self.spores.clear()
        available_actions = self._discover_actions(context)

        for i in range(self.num_spores):
            spore_id = f"spore_{self._spore_counter:06d}_{i}"
            self._spore_counter += 1

            spore = Spore(id=spore_id, energy=self.rng.uniform(0.5, 1.5))
            current = "start"

            # Generate path with length ∈ [min, max]
            target_len = self.rng.randint(self.min_path_length, self.max_path_length)

            for step in range(target_len):
                candidates = [a for a in available_actions if a not in spore.visited_nodes]
                if not candidates:
                    break

                # Weighted selection by pheromone
                path_so_far = "->".join(spore.path) if spore.path else current
                scores = []
                for action in candidates:
                    test_path = f"{path_so_far}->{action}" if path_so_far else action
                    pheromone = self.pheromone_map.get(test_path, 0.1)
                    goal_bonus = 1.5 if (goal_hint and goal_hint.lower() in action.lower()) else 1.0
                    scores.append(pheromone * goal_bonus)

                if self.rng.random() < self.exploration_factor:
                    choice = self.rng.choice(candidates)
                else:
                    # Softmax selection
                    scores_np = np.array(scores)
                    exp_scores = np.exp(scores_np - scores_np.max())
                    probs = exp_scores / np.sum(exp_scores)
                    choice = self.rng.choices(candidates, weights=probs)[0]

                spore.path.append(choice)
                spore.visited_nodes.add(choice)

            spore.quality = self._evaluate_path(spore.path, goal_hint)
            self.spores.append(spore)

        return self.spores

    def _discover_actions(self, context: Dict) -> List[str]:
        """Extract available actions from context (default: action_0 to action_9)."""
        if "actions" in context:
            return list(context["actions"])
        return [f"action_{i}" for i in range(10)]

    def _evaluate_path(self, path: List[str], goal: Optional[str]) -> float:
        """Evaluate how good a path is (0.0 to 1.0+)."""
        if not path:
            return 0.0

        path_key = "->".join(path)
        pheromone = self.pheromone_map.get(path_key, 0.1)

        # Goal alignment bonus (check last action)
        goal_bonus = 0.5 if (goal and path and goal.lower() in path[-1].lower()) else 0.0

        return float(pheromone * 0.7 + goal_bonus * 0.3)

    def converge(self, threshold: float = 0.6, spores: Optional[List[Spore]] = None) -> Optional[Spore]:
        """
        Converge on the best spore (best path).
        Returns None if no spore meets confidence threshold.
        """
        spores = spores if spores is not None else self.spores
        if not spores:
            return None

        best = max(spores, key=lambda s: s.quality)

        if best.quality < threshold:
            return None

        # Reinforce successful path with pure multiplicative boost
        path_key = "->".join(best.path)
        current = self.pheromone_map.get(path_key, 0.0)
        self.pheromone_map[path_key] = current * 1.2

        # Evaporate all pheromones slightly
        for key in list(self.pheromone_map.keys()):
            self.pheromone_map[key] *= self.pheromone_evaporation
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
        Returns (best_plan, confidence) or (None, 0.0).
        """
        spores = self.explore(context, goal_hint)
        best = self.converge(spores=spores)

        if best:
            return {
                "path": best.path,
                "quality": best.quality,
                "energy": best.energy,
                "steps": len(best.path),
            }, best.quality
        return None, 0.0

    def reinforce_path(self, path: List[str], delta: float = 0.1, decay: float = 1.0) -> float:
        """
        Explicitly reinforce a path's pheromone (external feedback).

        Formula: new = (current + delta) * decay

        Returns:
            New pheromone value for the path.
        """
        path_key = "->".join(path)
        current = self.pheromone_map.get(path_key, 0.0)
        new_val = (current + delta) * decay
        self.pheromone_map[path_key] = new_val
        return new_val

    def get_status(self) -> Dict:
        """Return explorer status for monitoring."""
        return {
            "spores_generated": self._spore_counter,
            "active_pheromone_paths": len(self.pheromone_map),
            "success_history_len": len(self.success_history),
        }
