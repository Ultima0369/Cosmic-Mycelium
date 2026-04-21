"""
Layer 5 — SuperBrain (SuperBrain Layer)
Multi-brain region collaboration, attention competition, global workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from collections import deque
from enum import Enum
import numpy as np
import time


class RegionPriority(Enum):
	"""Priority levels for global workspace access."""
	LOW = 0.3
	NORMAL = 0.6
	HIGH = 0.9


@dataclass
class RegionConfig:
	"""Static configuration for a brain region."""
	name: str
	specialty: str
	capacity: int = 100
	activation_threshold: float = 0.3
	decay_rate: float = 0.1


@dataclass
class RegionActivity:
	"""Snapshot of a region's current activity state."""
	name: str
	activation: float
	memory_count: int
	last_update: float


@dataclass
class Pathway:
	"""A directed connection between two brain regions."""
	source: str
	target: str
	weight: float = 0.5  # Connection strength [0, 1]
	plasticity: float = 0.1  # Hebbian learning rate


@dataclass
class BrainRegion:
	"""A specialized processing region."""
	name: str
	specialty: str  # e.g., "pattern", "prediction", "action"
	activation: float = 0.0
	working_memory: deque = field(default_factory=lambda: deque(maxlen=100))
	activation_history: List[float] = field(default_factory=list)
	stagnation_counter: int = 0


class SuperBrain:
	"""
	Layer 5: SuperBrain.

	Manages multiple specialized brain regions.
	Handles attention allocation and global workspace broadcasting.

	Neural logic:
	- Competition: Regions compete via softmax over activations (optional)
	- Cooperation: Weighted pathways enable inter-region influence
	- Global workspace: Content broadcast to all regions
	- Meta-cognition: Tracks region health and stagnation
	"""

	def __init__(
		self,
		region_names: List[Tuple[str, str]] | None = None,
		attention_temp: float = 1.0,
		max_global_workspace_size: int = 10,
		activation_normalization: bool = True,
		competition_enabled: bool = False,  # Default off for backward compat
	):
		"""
		Args:
			region_names: List of (name, specialty) tuples.
			attention_temp: Softmax temperature for attention competition.
			max_global_workspace_size: Max items retained in global workspace.
			activation_normalization: Whether to normalize total activation.
			competition_enabled: If True, broadcast requires winner from competition.
		"""
		self.regions: Dict[str, BrainRegion] = {}
		self.pathways: List[Pathway] = []
		self.global_workspace: Dict[str, Any] = {}
		self.global_workspace_priority: float = 0.0
		self.attention_temp = attention_temp
		self.max_global_workspace_size = max_global_workspace_size
		self.normalize_activation = activation_normalization
		self.competition_enabled = competition_enabled
		self._step_counter = 0

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

		# Default inter-region pathways (sparse connectivity)
		self._initialize_default_pathways()

	def _initialize_default_pathways(self) -> None:
		"""Create initial sparse connectivity between regions."""
		default_connections = [
			("sensory", "predictor", 0.7),
			("predictor", "planner", 0.6),
			("planner", "executor", 0.8),
			("executor", "sensory", 0.3),  # feedback
			("meta", "sensory", 0.4),
			("meta", "planner", 0.5),
			("meta", "executor", 0.4),
		]
		for src, tgt, weight in default_connections:
			if src in self.regions and tgt in self.regions:
				self.pathways.append(Pathway(source=src, target=tgt, weight=weight))

	@property
	def num_regions(self) -> int:
		"""Number of registered brain regions."""
		return len(self.regions)

	def _apply_pathway_influence(self, source_name: str, influence: float = 0.1) -> None:
		"""Propagate activation from source to connected targets via pathways."""
		source_activation = self.regions[source_name].activation
		for pathway in self.pathways:
			if pathway.source == source_name:
				target = self.regions.get(pathway.target)
				if target:
					# Hebbian-style: co-activation strengthens pathway
					pathway.weight = min(1.0, pathway.weight + pathway.plasticity * source_activation * target.activation)
					# Propagate activation scaled by pathway weight
					target.activation = min(1.0, target.activation + influence * source_activation * pathway.weight)

	def _normalize_activations(self) -> None:
		"""Normalize region activations to prevent runaway dominance."""
		if not self.normalize_activation:
			return
		total = sum(r.activation for r in self.regions.values())
		if total > 1.0:
			scale = 1.0 / total
			for region in self.regions.values():
				region.activation *= scale

	def _competition_step(self) -> str:
		"""
		Run attention competition: regions compete for global workspace access.
		Uses softmax over activations weighted by attention temperature.

		Returns:
			Name of winning region (or None if all below threshold).
		"""
		activations = np.array([r.activation for r in self.regions.values()])
		names = list(self.regions.keys())

		if len(activations) == 0:
			return None

		# Softmax selection with temperature
		if self.attention_temp > 0:
			exp_acts = np.exp(activations / self.attention_temp)
			probs = exp_acts / np.sum(exp_acts)
			# Select winner via softmax-weighted random choice
			winner_idx = np.random.choice(len(names), p=probs)
			winner = names[winner_idx]
			winner_prob = probs[winner_idx]
		else:
			# Greedy: highest activation wins
			winner_idx = np.argmax(activations)
			winner = names[winner_idx]
			winner_prob = 1.0

		# Only broadcast if activation exceeds threshold
		if self.regions[winner].activation >= 0.3 and winner_prob > 0.1:
			return winner
		return None

	def _check_stagnation(self) -> Dict[str, int]:
		"""
		Meta-cognition: detect regions that haven't activated recently.
		Returns dict of region -> stagnation count.
		"""
		stagnation = {}
		for name, region in self.regions.items():
			region.stagnation_counter += 1
			if region.activation_history and region.activation_history[-1] > 0.2:
				region.stagnation_counter = 0  # Reset on recent activation
			stagnation[name] = region.stagnation_counter
		return stagnation

	def perceive(self, stimulus: Dict) -> None:
		"""Route stimulus to appropriate region."""
		sensory = self.regions["sensory"]
		sensory.activation = min(1.0, sensory.activation + 0.3)
		sensory.working_memory.append(stimulus)
		if len(sensory.working_memory) > 100:
			sensory.working_memory.popleft()

		# Apply pathway influence
		self._apply_pathway_influence("sensory", influence=0.05)
		self._normalize_activations()

	def predict(self, context: Dict) -> Dict:
		"""Generate prediction from predictor region."""
		predictor = self.regions["predictor"]
		predictor.activation = min(1.0, predictor.activation + 0.2)
		predictor.working_memory.append({"context": context, "ts": time.time()})

		# Apply pathway influence
		self._apply_pathway_influence("predictor", influence=0.03)
		self._normalize_activations()

		return {
			"next_state": context,
			"confidence": predictor.activation,
		}

	def plan(self, goal: Optional[Dict] = None, options: Optional[List[Dict]] = None) -> Optional[Dict]:
		"""
		Select best plan from options.
		If options is None, generate synthetic options.
		Returns chosen plan dict with 'path' and 'quality' keys, or None.
		"""
		planner = self.regions["planner"]
		planner.activation = min(1.0, planner.activation + 0.4)

		if options is None:
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

		# Apply pathway influence from planner to executor
		self._apply_pathway_influence("planner", influence=0.05)
		self._normalize_activations()

		return {
			"path": best.get("path", "derived"),
			"quality": float(best.get("quality", 0.0)),
		}

	def broadcast_global_workspace(self, content: Dict, priority: float = 0.6) -> bool:
		"""
		Broadcast to global workspace.
		If competition_enabled=True, uses winner-take-all attention selection.
		Otherwise, broadcasts unconditionally (legacy behavior).

		Args:
			content: Message to broadcast.
			priority: Priority level [0, 1] — higher = more urgent.

		Returns:
			True if broadcast succeeded.
		"""
		if self.competition_enabled:
			winner = self._competition_step()
			if winner is None:
				return False
			if priority < self.regions[winner].activation:
				return False
			source = winner
		else:
			# Legacy: pick highest activation region as source
			source = max(self.regions.items(), key=lambda item: item[1].activation)[0] if self.regions else None

		self.global_workspace = {
			"content": content,
			"source": source,
			"priority": priority,
			"timestamp": time.time(),
		}
		self.global_workspace_priority = priority

		# Boost all region activations slightly (global broadcast effect)
		for region in self.regions.values():
			region.activation = min(1.0, region.activation + 0.1)
			region.activation_history.append(region.activation)
			if len(region.activation_history) > 100:
				region.activation_history.pop(0)

		# Meta region logs both raw content (backward compat) and full workspace
		if "meta" in self.regions:
			self.regions["meta"].working_memory.append(content)  # Raw content for legacy query
			self.regions["meta"].working_memory.append(self.global_workspace.copy())

		self._step_counter += 1
		return True

	def execute(self, action: Dict) -> None:
		"""Execute an action via the executor region."""
		executor = self.regions["executor"]
		executor.activation = min(1.0, executor.activation + 0.3)
		executor.working_memory.append(action)
		if len(executor.working_memory) > 100:
			executor.working_memory.popleft()

		self._apply_pathway_influence("executor", influence=0.04)
		self._normalize_activations()

	def decay_activations(self, decay_factor: float = 0.1) -> None:
		"""Activity naturally decays by multiplicative factor."""
		for region in self.regions.values():
			region.activation = max(0.0, region.activation * decay_factor)

	def adjust_pathway(self, source: str, target: str, delta: float) -> bool:
		"""
		Hebbian plasticity: strengthen/weaken connection between regions.
		Co-activated pathways strengthen (positive delta), unused weaken.

		Args:
			source: Source region name.
			target: Target region name.
			delta: Change in weight (positive = strengthen).

		Returns:
			True if pathway adjusted, False if not found.
		"""
		for pathway in self.pathways:
			if pathway.source == source and pathway.target == target:
				pathway.weight = max(0.0, min(1.0, pathway.weight + delta))
				return True
		return False

	def get_region_health(self) -> Dict[str, Dict[str, float]]:
		"""
		Meta-cognition: assess health of each region.
		Returns per-region metrics: activation_mean, activation_variance, stagnation.
		"""
		health = {}
		stagnation = self._check_stagnation()

		for name, region in self.regions.items():
			activations = region.activation_history[-20:] if region.activation_history else [region.activation]
			health[name] = {
				"activation_mean": float(np.mean(activations)),
				"activation_variance": float(np.var(activations)),
				"stagnation": float(stagnation[name]),
				"memory_utilization": len(region.working_memory) / region.working_memory.maxlen,
			}
		return health

	def get_status(self) -> Dict:
		"""Return brain status."""
		return {
			"regions": {
				name: {
					"activation": round(r.activation, 3),
					"specialty": r.specialty,
					"working_memory_len": len(r.working_memory),
					"stagnation": r.stagnation_counter,
				}
				for name, r in self.regions.items()
			},
			"global_workspace": self.global_workspace is not None,
			"global_workspace_source": self.global_workspace.get("source") if self.global_workspace else None,
			"pathway_count": len(self.pathways),
			"step_counter": self._step_counter,
		}
