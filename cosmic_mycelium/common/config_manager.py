"""
ConfigManager — Multi-Scale Configuration
Handles scale parameters (infant/cluster/global) and per-layer defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import os


@dataclass
class ScaleConfig:
    """Configuration for one fractal scale."""
    name: str
    # Per-layer sub-configs
    abstract_segmenter: Dict[str, Any] = field(default_factory=dict)
    semantic_mapper: Dict[str, Any] = field(default_factory=dict)
    slime_explorer: Dict[str, Any] = field(default_factory=dict)
    myelination: Dict[str, Any] = field(default_factory=dict)
    superbrain: Dict[str, Any] = field(default_factory=dict)
    symbiosis: Dict[str, Any] = field(default_factory=dict)
    # Scale-level parameters (HIC, etc.)
    params: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """
    Manages configuration across fractal scales.

    Three predefined scales:
      - infant: Personal computer (1 node)
      - cluster: Lab cluster (10s-100s nodes)
      - global: Planet-scale (1000s+ nodes)

    Each scale inherits base config and overrides specific parameters.
    """

    # Valid layer names for per-layer config access
    VALID_LAYERS = {
        "abstract_segmenter",
        "semantic_mapper",
        "slime_explorer",
        "myelination",
        "superbrain",
        "symbiosis",
    }
    VALID_SCALES = {"infant", "cluster", "global", "hic"}

    # Predefined scale configurations
    SCALES = {
        "infant": ScaleConfig(
            name="infant",
            abstract_segmenter={"windows": 6, "base_duration": 0.055},
            semantic_mapper={"embedding_dim": 16},
            slime_explorer={"num_spores": 10},
            myelination={"max_traces": 1000},
            superbrain={"regions": ["sensory", "predictor", "planner", "motor", "meta"]},
            symbiosis={"max_partners": 10},
            params={
                "energy_max": 100.0,
                "contract_duration": 0.055,
                "diffuse_duration": 0.005,
                "suspend_duration": 5.0,
                "recovery_energy": 60.0,
                "recovery_rate": 0.5,
            },
        ),
        "cluster": ScaleConfig(
            name="cluster",
            abstract_segmenter={"windows": 8, "base_duration": 0.1},
            semantic_mapper={"embedding_dim": 64},
            slime_explorer={"num_spores": 50},
            myelination={"max_traces": 10000},
            superbrain={"regions": ["sensory", "predictor", "planner", "motor", "meta", "consensus"]},
            symbiosis={"max_partners": 100},
            params={
                "energy_max": 100.0,
                "contract_duration": 0.055,
                "diffuse_duration": 0.005,
                "suspend_duration": 5.0,
                "recovery_energy": 60.0,
                "recovery_rate": 0.5,
            },
        ),
        "global": ScaleConfig(
            name="global",
            abstract_segmenter={"windows": 12, "base_duration": 1.0},
            semantic_mapper={"embedding_dim": 256},
            slime_explorer={"num_spores": 200},
            myelination={"max_traces": 100000},
            superbrain={"regions": ["sensory", "predictor", "planner", "motor", "meta", "consensus", "orchestrator"]},
            symbiosis={"max_partners": 10000},
            params={
                "energy_max": 100.0,
                "contract_duration": 0.055,
                "diffuse_duration": 0.005,
                "suspend_duration": 5.0,
                "recovery_energy": 60.0,
                "recovery_rate": 0.5,
            },
        ),
    }

    def __init__(self, scale: str = "infant"):
        self.scale = scale
        self.config = self.SCALES.get(scale, self.SCALES["infant"])
        self._apply_env_overrides()

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides (simplified)."""
        # Not implementing full override logic for brevity
        pass

    @classmethod
    def for_infant(cls) -> "ConfigManager":
        return cls("infant")

    @classmethod
    def for_cluster(cls) -> "ConfigManager":
        return cls("cluster")

    @classmethod
    def for_global(cls) -> "ConfigManager":
        return cls("global")

    def get(self, layer: str, param: str, default: Any = None) -> Any:
        """
        Get a config parameter.

        Layer can be:
        - A scale name: "infant", "cluster", "global", "hic" (returns scale-level params)
        - A layer name: "semantic_mapper", "slime_explorer", etc. (returns per-layer config)

        Defense-in-depth: only explicit allowlist layers are accepted. Unknown
        layers return default (if provided) or raise KeyError.
        """
        # Validate layer against explicit allowlist (reject arbitrary attribute access)
        if layer in self.VALID_SCALES:
            layer_cfg = self.config.params
        elif layer in self.VALID_LAYERS:
            layer_cfg = getattr(self.config, layer)
        else:
            # Unknown layer — return default or raise (preserves backward compat)
            if default is not None:
                return default
            raise KeyError(f"Unknown layer: {layer}")

        if param in layer_cfg:
            return layer_cfg[param]
        if default is not None:
            return default
        raise KeyError(f"Parameter '{param}' not found in layer '{layer}'")

    def as_dict(self) -> Dict[str, Any]:
        """Export full configuration across all scales."""
        return {
            "infant": {
                "params": self.SCALES["infant"].params,
                "abstract_segmenter": self.SCALES["infant"].abstract_segmenter,
                "semantic_mapper": self.SCALES["infant"].semantic_mapper,
                "slime_explorer": self.SCALES["infant"].slime_explorer,
                "myelination": self.SCALES["infant"].myelination,
                "superbrain": self.SCALES["infant"].superbrain,
                "symbiosis": self.SCALES["infant"].symbiosis,
            },
            "cluster": {
                "params": self.SCALES["cluster"].params,
                "abstract_segmenter": self.SCALES["cluster"].abstract_segmenter,
                "semantic_mapper": self.SCALES["cluster"].semantic_mapper,
                "slime_explorer": self.SCALES["cluster"].slime_explorer,
                "myelination": self.SCALES["cluster"].myelination,
                "superbrain": self.SCALES["cluster"].superbrain,
                "symbiosis": self.SCALES["cluster"].symbiosis,
            },
            "global": {
                "params": self.SCALES["global"].params,
                "abstract_segmenter": self.SCALES["global"].abstract_segmenter,
                "semantic_mapper": self.SCALES["global"].semantic_mapper,
                "slime_explorer": self.SCALES["global"].slime_explorer,
                "myelination": self.SCALES["global"].myelination,
                "superbrain": self.SCALES["global"].superbrain,
                "symbiosis": self.SCALES["global"].symbiosis,
            },
        }
