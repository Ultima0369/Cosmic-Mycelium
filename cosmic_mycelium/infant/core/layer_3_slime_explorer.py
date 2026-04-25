"""
Layer 3 — Slime Mold Explorer (Slime Mold Layer)
Motivation-vision path search, multi-objective optimization.
Mimics slime mold's parallel "discharge" and convergence with learned heuristics.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Spore:
    """A parallel exploration branch with resource budget."""

    id: str
    path: list[str] = field(default_factory=list)
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

    Trauma integration: paths that overlap with trauma memories are penalized,
    and repeated avoidance accumulates repression potential that can trigger
    involuntary flashbacks.
    """

    def __init__(
        self,
        num_spores: int = 10,
        exploration_factor: float = 0.3,
        pheromone_evaporation: float = 0.99,
        min_path_length: int = 1,
        max_path_length: int = 5,
        trauma_memory: Any = None,
        fractal_bus: Any = None,
    ):
        self.num_spores = num_spores
        self.exploration_factor = exploration_factor
        self.pheromone_evaporation = pheromone_evaporation
        self.min_path_length = min_path_length
        self.max_path_length = max_path_length
        self.spores: list[Spore] = []
        self.pheromone_map: dict[str, float] = {}
        self.success_history: list = []
        self.rng = random.Random(42)  # Deterministic RNG
        self._spore_counter = 0
        # Trauma/flashback integration
        self.trauma_memory = trauma_memory
        self._flashback_active: bool = False
        self._flashback_context: dict | None = None
        # Fractal Dialogue integration (collective wisdom)
        self.fractal_bus = fractal_bus
        self.max_success_history: int = 1000

    def explore(self, context: dict, goal_hint: str | None = None) -> list[Spore]:
        """
        Release spores to explore multiple paths simultaneously.
        Each spore follows a probabilistic policy.

        Spore count is dynamically adjusted based on energy and confidence:
          - energy > 50 and confidence < 0.5: max spores (大胆探索)
          - energy > 30: normal
          - energy ≤ 30 or SUSPEND risk: minimal (节能)

        v4.0: Spore count = f(energy, confidence, breath_state).
        """
        self.spores.clear()
        available_actions = self._discover_actions(context)

        # ── Dynamic spore allocation (v4.0, opt-in via context keys) ──
        energy = context.get("energy")
        confidence = context.get("confidence")
        num_spores = self.num_spores  # default: use configured value

        # ── 集体不安感知：MESH 有创伤回声时减少探索量 ──
        collective_unease = False
        if self.fractal_bus is not None:
            try:
                collective_unease = self.fractal_bus.has_collective_trauma()
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.warning("SlimeExplorer: has_collective_trauma failed: %s", e)
                collective_unease = False

        if energy is not None and confidence is not None:
            if energy > 50.0 and confidence < 0.5:
                num_spores = self.num_spores  # max: 大胆探索
            elif energy > 30.0:
                num_spores = max(3, self.num_spores // 2)  # normal
            else:
                num_spores = max(2, self.num_spores // 5)  # 节能模式

        # 集体不安：群体有创伤回声时收缩探索（谨慎）
        if collective_unease:
            num_spores = max(2, num_spores // 2)

        # ── 导入群体共享路径：别的节点成功过的路径信息素加成 ──
        if self.fractal_bus is not None:
            try:
                shared = self.fractal_bus.get_shared_paths(min_quality=0.5)
                for entry in shared:
                    shared_path = entry.get("path", "")
                    # 给共享路径增加信息素，让后续探索偏向它
                    current = self.pheromone_map.get(shared_path, 0.0)
                    self.pheromone_map[shared_path] = max(current, entry["quality"] * 0.5)
            except (RuntimeError, ConnectionError, TypeError) as e:
                logger.warning("SlimeExplorer: get_shared_paths failed: %s", e)

        for i in range(num_spores):
            spore_id = f"spore_{self._spore_counter:06d}_{i}"
            self._spore_counter += 1

            spore = Spore(id=spore_id, energy=self.rng.uniform(0.5, 1.5))
            current = "start"

            # Generate path with length ∈ [min, max]
            target_len = self.rng.randint(self.min_path_length, self.max_path_length)

            for _ in range(target_len):
                candidates = [
                    a for a in available_actions if a not in spore.visited_nodes
                ]
                if not candidates:
                    break

                # Weighted selection by pheromone
                path_so_far = "->".join(spore.path) if spore.path else current
                scores = []
                for action in candidates:
                    test_path = f"{path_so_far}->{action}" if path_so_far else action
                    pheromone = self.pheromone_map.get(test_path, 0.1)
                    goal_bonus = (
                        1.5
                        if (goal_hint and goal_hint.lower() in action.lower())
                        else 1.0
                    )
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

    def _discover_actions(self, context: dict) -> list[str]:
        """Extract available actions from context (default: action_0 to action_9)."""
        if "actions" in context:
            return list(context["actions"])
        return [f"action_{i}" for i in range(10)]

    def _evaluate_path(self, path: list[str], goal: str | None) -> float:
        """Evaluate how good a path is (0.0 to 1.0+)."""
        if not path:
            return 0.0

        path_key = "->".join(path)
        pheromone = self.pheromone_map.get(path_key, 0.1)

        # Goal alignment bonus (check last action)
        goal_bonus = (
            0.5 if (goal and path and goal.lower() in path[-1].lower()) else 0.0
        )

        # ── Individual trauma penalty ──
        trauma_penalty = 0.0
        if self.trauma_memory is not None:
            for trauma_path in self.trauma_memory.trauma_paths:
                trauma_prefix = trauma_path.split("->")[0] if "->" in trauma_path else trauma_path
                if path_key.startswith(trauma_prefix) or path_key == trauma_path:
                    trauma_penalty = 0.5
                    break

        # ── Collective trauma penalty (群体本能) ──
        collective_penalty = 0.0
        if self.fractal_bus is not None:
            try:
                if self.fractal_bus.has_collective_trauma():
                    # 集体不安：降低所有探索路径的评分（"氛围不对"）
                    collective_penalty = 0.2
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.warning("SlimeExplorer: has_collective_trauma failed in _evaluate_path: %s", e)

        total_penalty = trauma_penalty * 0.5 + collective_penalty
        return float(pheromone * 0.7 + goal_bonus * 0.3 - total_penalty * 0.3)

    def converge(
        self, threshold: float = 0.6, spores: list[Spore] | None = None
    ) -> Spore | None:
        """
        Converge on the best spore (best path).
        Returns None if no spore meets confidence threshold.

        Trauma integration: after convergence, if trauma_memory is available,
        accumulates repression for avoided trauma paths and checks for flashback triggers.
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

        self.success_history.append(
            {
                "path": best.path,
                "quality": best.quality,
                "timestamp": time.time(),
            }
        )

        # 裁剪成功历史，防止无限增长
        if len(self.success_history) > self.max_success_history:
            self.success_history = self.success_history[-self.max_success_history:]

        # ── Trauma repression accumulation ──
        if self.trauma_memory is not None and len(self.trauma_memory.trauma_paths) > 0:
            chosen_path_str = "->".join(best.path)
            for trauma_path in self.trauma_memory.trauma_paths:
                # If we actively avoided a trauma path, accumulate repression
                if chosen_path_str != trauma_path:
                    self.trauma_memory.accumulate_repression(trauma_path)

            # Check for flashback triggers
            flashbacks = self.trauma_memory.check_flashback_trigger()
            if flashbacks:
                self._flashback_active = True
                self._flashback_context = {
                    "triggered_at": time.time(),
                    "flashbacks": flashbacks,
                }

        # ── 共享成功路径到 MESH（一个节点的成果成为群体的启发式）──
        if self.fractal_bus is not None and best.quality >= 0.6:
            try:
                self.fractal_bus.publish_path_success(
                    path=best.path,
                    quality=best.quality,
                    source_id=getattr(self, "_source_id", "explorer"),
                )
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.warning("SlimeExplorer: publish_path_success failed: %s", e)

        return best

    def plan(
        self, context: dict, goal_hint: str | None = None
    ) -> tuple[dict | None, float]:
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

    def reinforce_path(
        self, path: list[str], delta: float = 0.1, decay: float = 1.0
    ) -> float:
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

    def get_status(self) -> dict:
        """Return explorer status for monitoring."""
        return {
            "spores_generated": self._spore_counter,
            "active_pheromone_paths": len(self.pheromone_map),
            "success_history_len": len(self.success_history),
        }
