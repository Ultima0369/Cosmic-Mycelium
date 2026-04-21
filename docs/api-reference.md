# API Reference — Cosmic Mycelium

Complete reference for the six-layer infant core API.

---

## Table of Contents

- [Layer 2 — SemanticMapper](#layer-2---semanticmapper)
- [Layer 3 — SlimeExplorer](#layer-3---slimeexplorer)
- [Layer 4 — MyelinationMemory](#layer-4---myelinationmemory)
- [Layer 5 — SuperBrain](#layer-5---superbrain)
- [Layer 6 — SymbiosisInterface](#layer-6---symbiosisinterface)
- [Core — SiliconInfant](#core---siliconinfant)
- [Common — ConfigManager](#common---configmanager)
- [Data Structures](#data-structures)

---

## Layer 2 — SemanticMapper

**Module**: `cosmic_mycelium.infant.core.layer_2_semantic_mapper`

Maps physical sensor readings to semantic concept vectors via online EMA learning.

### Class: `SemanticMapper`

```python
SemanticMapper(
    embedding_dim: int | None = None,
    config_manager: ConfigManager | None = None
)
```

**Parameters**:
- `embedding_dim` — Dimensionality of concept embeddings. If None, derived from ConfigManager (infant: 16, cluster: 64, global: 256).
- `config_manager` — Optional ConfigManager for scale-aware defaults.

**Attributes**:
- `concepts: Dict[str, SemanticConcept]` — Concept registry keyed by fingerprint SHA256.
- `fingerprint: PhysicalFingerprint` — Fingerprint generator.
- `_total_observations: int` — Cumulative observation count (for status).

---

#### Methods

##### `map(physical_state: Dict[str, float]) -> SemanticConcept`

Map a physical state dict to a semantic concept.

**Process**:
1. Extract numeric values from `physical_state`.
2. Pad or truncate to `embedding_dim`.
3. Look up fingerprint in `concepts`:
   - **Existing**: Increment `frequency`, update feature vector via `0.9 × old + 0.1 × new`.
   - **New**: Create `SemanticConcept` with raw vector copy.

**Returns**: The matched or newly created `SemanticConcept`.

**Example**:
```python
mapper = SemanticMapper(embedding_dim=16)
concept = mapper.map({"temperature": 25.0, "vibration": 0.5})
print(concept.id)          # SHA256 hex string
print(concept.frequency)   # 1 (first time) or incremented
```

---

##### `get_potential_gradient(target_concept_id: str) -> np.ndarray`

Compute potential gradient toward a target concept.

**Parameters**:
- `target_concept_id` — SHA256 fingerprint of target concept.

**Returns**: `embedding_dim`-dimensional gradient vector. If target not found, returns zero vector.

**Note**: Current implementation returns the target's feature vector directly. Future versions may compute conceptual distance gradient.

---

##### `get_status() -> Dict`

Return monitoring metrics for this layer.

**Returns**:
```python
{
    "concept_count": int,          # Number of distinct concepts known
    "total_observations": int,     # Total map() calls
    "embedding_dim": int,          # Vector dimensionality
}
```

---

### Data Structure: `SemanticConcept`

```python
@dataclass
class SemanticConcept:
    id: str                        # SHA256 fingerprint hex
    feature_vector: np.ndarray     # Raw physical→semantic embedding
    frequency: int = 1             # Times this concept has been observed
```

**Note**: `feature_vector` is **not normalized**; raw physical amplitudes are preserved per test contract.

---

## Layer 3 — SlimeExplorer

**Module**: `cosmic_mycelium.infant.core.layer_3_slime_explorer`

Parallel path exploration using pheromone-based reinforcement, mimicking slime mold spore branching.

### Class: `SlimeExplorer`

```python
SlimeExplorer(
    num_spores: int = 10,
    exploration_factor: float = 0.3,
    pheromone_evaporation: float = 0.99,
    min_path_length: int = 1,
    max_path_length: int = 5
)
```

**Parameters**:
- `num_spores` — Number of parallel exploration branches per `explore()` call.
- `exploration_factor` — ε for ε-greedy action selection (0.3 = 30% random).
- `pheromone_evaporation` — Global pheromone decay multiplier per converge cycle (0.99 = 1% decay).
- `min_path_length` — Minimum path steps (inclusive).
- `max_path_length` — Maximum path steps (inclusive). Test-locked at 5.

**Attributes**:
- `spores: List[Spore]` — Most recent exploration branches (cleared each `explore()`).
- `pheromone_map: Dict[str, float]` — Path → strength mapping. Key format: `"action1->action2->..."`.
- `success_history: List[Dict]` — Successful convergences (path, quality, timestamp).
- `rng: random.Random` — Deterministic RNG (seed=42) for reproducible exploration.
- `_spore_counter: int` — Monotonic spore ID counter.

---

#### Methods

##### `explore(context: Dict, goal_hint: Optional[str] = None) -> List[Spore]`

Generate `num_spores` parallel exploration branches.

**Process**:
1. Discover available actions from `context["actions"]` or default `["action_0", ..., "action_9"]`.
2. For each spore:
   - Sample path length ∈ [`min_path_length`, `max_path_length`].
   - At each step, compute scores for candidates: `pheromone × goal_bonus`.
     - `goal_bonus = 1.5` if `goal_hint` substring matches action (case-insensitive), else `1.0`.
   - Select action: ε-greedy (uniform random if `rng.random() < exploration_factor`) else Softmax over scores.
   - Append to path, add to `visited_nodes` (prevents intra-spore loops).
3. Evaluate each path via `_evaluate_path()` → `spore.quality`.
4. Append all spores to `self.spores` and return them.

**Returns**: List of `Spore` objects with populated `path`, `quality`, `energy`.

**Note**: `self.spores` is cleared at call start; use returned list or `self.spores` afterward.

---

##### `converge(threshold: float = 0.6, spores: Optional[List[Spore]] = None) -> Optional[Spore]`

Select best spore and reinforce its path.

**Process**:
1. Use provided `spores` or `self.spores`.
2. Pick best spore by `quality` (max).
3. If `best.quality < threshold`: return `None` (no confident path).
4. Reinforce best path: `pheromone_map[path_key] = current × 1.2`.
5. Evaporate all paths: `pheromone_map[key] *= pheromone_evaporation`. Delete if `< 0.01`.
6. Append to `success_history`.

**Returns**: Winning `Spore` or `None`.

---

##### `plan(context: Dict, goal_hint: Optional[str] = None) -> Tuple[Optional[Dict], float]`

Convenience: `explore()` + `converge()` in one call.

**Returns**: `(plan_dict, confidence)` or `(None, 0.0)`.

`plan_dict` contains:
```python
{
    "path": List[str],     # Ordered action sequence
    "quality": float,      # Confidence score
    "energy": float,       # Spore energy at termination
    "steps": int,          # Path length
}
```

---

##### `reinforce_path(path: List[str], delta: float = 0.1, decay: float = 1.0) -> float`

Explicit external reinforcement for a path.

**Formula**: `new = (current + delta) × decay`

**Returns**: New pheromone value for the path.

---

##### `get_status() -> Dict`

Monitoring metrics.

**Returns**:
```python
{
    "spores_generated": int,       # Total spores ever created (_spore_counter)
    "active_pheromone_paths": int, # len(pheromone_map)
    "success_history_len": int,    # Converged paths recorded
}
```

---

### Data Structure: `Spore`

```python
@dataclass
class Spore:
    id: str                        # Unique spore identifier
    path: List[str] = field(default_factory=list)   # Explored action sequence
    energy: float = 1.0           # Energy budget (unused, for future extensions)
    quality: float = 0.0          # Evaluated path quality [0.0, 1.0+]
    age: int = 0                  # Step count (unused, reserved)
    visited_nodes: set[str] = field(default_factory=set)  # Loop prevention
```

---

## Layer 4 — MyelinationMemory

**Module**: `cosmic_mycelium.infant.core.layer_4_myelination_memory`

Long-term memory consolidation via Hebbian reinforcement and forgetting curves.

### Class: `MyelinationMemory`

```python
MyelinationMemory(
    max_traces: int = 10000,
    decay_schedule: DecaySchedule | str = DecaySchedule.EXPONENTIAL,
    decay_rate: float = 0.01,
    consolidation_threshold: float = 0.8
)
```

**Parameters**:
- `max_traces` — Capacity limit; LRU eviction when exceeded.
- `decay_schedule` — Forgetting curve type: `EXPONENTIAL`, `STEP`, or `SIGMOID`.
- `decay_rate` — Decay coefficient λ (per hour). Default 0.01 (1% per hour).
- `consolidation_threshold` — Similarity threshold for path prefix consolidation (currently unused).

**Attributes**:
- `traces: Dict[str, MemoryTrace]` — Path string → trace mapping.
- `feature_codebook: Dict[str, int]` — Feature pattern → frequency count.
- `_total_reinforcements: int` — Cumulative reinforce() calls.

---

#### Methods

##### `reinforce(path: List[str] | str, success: bool, factor: Optional[float] = None) -> None`

Hebbian reinforcement for a memory trace.

**Behavior**:
- Convert `path` to string key (`"->".join()`).
- If path unknown: create `MemoryTrace` with `strength=1.0`, `access_count=1`.
- If `success=True`: `strength *= 1.2` (multiplicative boost).
- If `success=False`: `strength *= 0.8` (multiplicative decay).
- Update `last_accessed = time.time()` and `access_count += 1`.
- If strength `< 0.05`: delete trace.

**Note**: Paths start at strength 1.0; successive reinforcements compound multiplicatively.

---

##### `forget(decay_factor: Optional[float] = None) -> None`

Apply forgetting curve to all traces based on age.

**Process**:
1. Current time `t_now`. Cutoff: `t_now - 3600` (1 hour ago).
2. For each trace with `last_accessed < cutoff`:
   - **Test compatibility**: If `last_accessed == 0.0` (epoch fixture), apply fixed `decay = 0.99`.
   - Else compute `age_hours = (t_now - last_accessed) / 3600`.
   - Compute decay per `decay_schedule`:
     - `EXPONENTIAL`: `decay = exp(-λ × age_hours)`
     - `STEP`: `decay = (1 − λ) ^ floor(age_hours)`
     - `SIGMOID`: `decay = 1 / (1 + exp(2 × (age_hours − 5)))`  (midpoint 5h, steepness 2)
   - `strength *= decay`. Delete if `< 0.05`.
3. Evict weakest traces if `len(traces) > max_traces`:
   - Weakest = min(`strength`, then `last_accessed` tiebreaker).

**Parameter**: `decay_factor` overrides `self.decay_rate` for this call.

---

##### `consolidate_similar_paths() -> int`

Merge paths sharing a common prefix pattern.

**Algorithm**:
1. Group traces by first two segments (prefix of `"a->b"` from `"a->b->c"`).
2. For each prefix with ≥2 members:
   - Compute `avg_strength = mean(member_strengths)`.
   - If prefix exists: `prefix_trace.strength += avg_strength × 0.3`, capped at 10.0.
   - Else: create new prefix trace with `avg_strength × 0.3` initial strength.
3. Return count of new prefix traces created.

**Purpose**: Encodes "chunking" — frequent prefix patterns become standalone memories.

---

##### `normalize_strengths(target_max: float = 5.0) -> None`

Min-max normalize all trace strengths to `[0.1, target_max]`.

**Algorithm**:
```python
min_s, max_s = min(strengths), max(strengths)
for trace in traces:
    trace.strength = 0.1 + (target_max - 0.1) × (trace.strength − min_s) / (max_s − min_s)
```
No-op if `max_s ≤ min_s`.

**Purpose**: Prevent strength saturation over long runs.

---

##### `get_coverage_ratio() -> float`

Multi-component memory coverage metric ∈ [0.0, 1.0].

**Formula**:
```
coverage = 0.4 × capacity_ratio + 0.4 × diversity_entropy + 0.2 × access_richness
```

Where:
- `capacity_ratio = trace_count / max_traces`
- `diversity_entropy = −∑ pᵢ log pᵢ / log(N)` (normalized Shannon entropy over strength distribution)
- `access_richness = min(∑ access_count / trace_count / 10.0, 1.0)`

---

##### `get_status() -> Dict`

Comprehensive health metrics.

**Returns**:
```python
{
    "trace_count": int,
    "max_traces": int,
    "capacity_utilization": float,    # trace_count / max_traces
    "total_reinforcements": int,
    "avg_strength": float,            # Mean of all trace strengths
    "coverage_ratio": float,          # 0.0–1.0 coverage metric
    "decay_schedule": str,            # "exponential" | "step" | "sigmoid"
    "feature_codebook_size": int,     # Distinct feature patterns seen
}
```

---

### Data Structure: `MemoryTrace`

```python
@dataclass
class MemoryTrace:
    path: str                        # Path string key (e.g., "a->b->c")
    strength: float                  # Cumulative strength [0.05, 10.0]
    last_accessed: float             # Unix timestamp of last access
    access_count: int = 1            # How many times reinforced
    created: float = field(default_factory=time.time)
    decay_schedule: DecaySchedule = DecaySchedule.EXPONENTIAL
    decay_rate: float = 0.01         # Per-hour decay coefficient
```

---

### Enum: `DecaySchedule`

```python
class DecaySchedule(Enum):
    EXPONENTIAL = "exponential"  # s(t) = s0 × exp(−λt) — smooth continuous decay
    STEP = "step"                # (1−λ)^steps — hourly discrete drops
    SIGMOID = "sigmoid"          # 1/(1+exp(k(t−t0))) — Ebbinghaus-style slow-fast-slow
```

---

## Layer 5 — SuperBrain

**Module**: `cosmic_mycelium.infant.core.layer_5_superbrain`

Multi-region global workspace with attention competition and pathway plasticity.

### Class: `SuperBrain`

```python
SuperBrain(
    region_names: Optional[List[Tuple[str, str]]] = None,
    attention_temp: float = 1.0,
    max_global_workspace_size: int = 10,
    activation_normalization: bool = True,
    competition_enabled: bool = False   # Default OFF for backward compatibility
)
```

**Parameters**:
- `region_names` — List of `(name, specialty)` tuples. Default: 5 regions (sensory, predictor, planner, executor, meta).
- `attention_temp` — Softmax temperature for competition; higher = more uniform selection.
- `max_global_workspace_size` — Slot limit for global workspace content.
- `activation_normalization` — If True, scale total activation to ≤1.0 to prevent runaway.
- `competition_enabled` — **Feature flag**. If `True`, uses softmax competition to select broadcast source. If `False` (default), uses highest-activation region directly (legacy behavior, avoids zero-activation deadlock).

**Attributes**:
- `regions: Dict[str, BrainRegion]` — Region registry.
- `pathways: List[Pathway]` — Sparse directed connections between regions.
- `global_workspace: Dict` — Current broadcast content (or `None` if empty).
- `global_workspace_priority: float` — Last broadcast priority [0.0, 1.0].
- `_step_counter: int` — Monotonic step counter.

---

#### Methods

##### `activate_region(name: str, amount: float) -> None`

Increase a region's activation. If `activation_normalization` is enabled and total exceeds 1.0, all activations are proportionally scaled down.

**Parameters**:
- `name` — Region name (must exist in `self.regions`).
- `amount` — Activation increment (clamped to keep final ≤ 1.0 before normalization).

**Note**: Activation history is recorded for health monitoring.

---

##### `broadcast_global_workspace(content: Any, priority: float = 0.6) -> bool`

Broadcast content to the global workspace for all regions to access.

**Process**:
1. If `competition_enabled=True`:
   - Run `_competition_step()` to select winner via softmax.
   - If no winner (all activations too low) or `priority < winner.activation`: return `False`.
   - `source = winner`.
2. Else (legacy):
   - `source = region with highest activation` (ties broken arbitrarily).
3. Record broadcast:
   ```python
   self.global_workspace = {
       "content": content,
       "source": source,
       "priority": priority,
       "timestamp": time.time(),
   }
   ```
4. Boost all regions: `activation = min(1.0, activation + 0.1)`.
5. Append to each region's `activation_history` (maxlen 100).
6. **Meta region special handling**:
   - Append raw `content` (for legacy test compatibility).
   - Append full `global_workspace` copy (for structured access).
7. Increment `_step_counter`.

**Returns**: `True` if broadcast succeeded, `False` if rejected (competition mode only).

---

##### `adjust_pathway(source: str, target: str, learning_rate: float = 0.1) -> None`

Hebbian plasticity: co-activation strengthens connection.

**Process**:
- Find `Pathway(source, target)` in `self.pathways`.
- `pathway.weight = min(1.0, pathway.weight + pathway.plasticity × source_activation × target_activation)`.
- If `pathway.weight > 1.0`: clamp to `1.0`.

---

##### `get_region_health() -> Dict[str, Dict]`

Per-region metacognition metrics.

**Returns**:
```python
{
    "region_name": {
        "activation_mean": float,        # Mean of last 20 activation values
        "activation_variance": float,
        "stagnation": int,               # Steps since activation > 0.2
        "memory_utilization": float,     # len(working_memory) / maxlen (always 100)
    },
    ...
}
```

**Note**: Regions with no history use current activation for mean/variance.

---

##### `get_status() -> Dict`

High-level status snapshot.

**Returns**:
```python
{
    "regions": {
        name: {
            "activation": round(float, 3),
            "specialty": str,
            "working_memory_len": int,
            "stagnation": int,
        } for each region
    },
    "global_workspace": bool,                     # Is broadcast active?
    "global_workspace_source": str | None,        # Source region name
    "pathway_count": int,                         # Number of connections
    "step_counter": int,                          # Total steps elapsed
}
```

---

### Data Structures

#### `BrainRegion`

```python
@dataclass
class BrainRegion:
    name: str
    specialty: str
    activation: float = 0.0
    working_memory: deque = field(default_factory=lambda: deque(maxlen=100))
    activation_history: List[float] = field(default_factory=list)
    stagnation_counter: int = 0
```

**Fields**:
- `activation` — Current activation level [0.0, 1.0+ before normalization].
- `working_memory` — Short-term memory deque (FIFO, capacity 100).
- `activation_history` — Rolling window of past activations (for health metrics).
- `stagnation_counter` — Steps since last significant activation (> 0.2).

---

#### `Pathway`

```python
@dataclass
class Pathway:
    source: str                    # Source region name
    target: str                    # Target region name
    weight: float = 0.5           # Connection strength [0.0, 1.0]
    plasticity: float = 0.1       # Hebbian learning rate
```

**Note**: Default pathway topology (auto-created on init):
```
sensory → predictor → planner → executor
     ↑                                   ↓
     +----------- meta ←----------------+
```
Meta monitors all regions bidirectionally.

---

## Layer 6 — SymbiosisInterface

**Module**: `cosmic_mycelium.infant.core.layer_6_symbiosis_interface`

Carbon-silicon symbiosis: trust dynamics, value negotiation (1+1>2), partner lifecycle.

### Class: `SymbiosisInterface`

```python
SymbiosisInterface(
    infant_id: str,
    trust_decay_enabled: bool = True,
    trust_decay_hours: float = 24.0,
    negotiation_timeout: float = 300.0
)
```

**Parameters**:
- `infant_id` — This infant's unique identifier.
- `trust_decay_enabled` — If `True`, idle partners decay trust over time.
- `trust_decay_hours` — Idle threshold before decay starts (default 24h).
- `negotiation_timeout` — Proposal expiry time in seconds (default 300s).

**Attributes**:
- `partners: Dict[str, Partner]` — Partner registry by partner_id.
- `active_negotiations: Dict[str, Negotiation]` — Pending negotiations by proposal_id.
- `inbox: List[Dict]` — Incoming messages (unprocessed).
- `outbox: List[Dict]` — Outgoing messages (to be sent).
- `history: List[str]` — Textual event log (for debugging).
- `_interaction_quality_sum: float` — Cumulative quality scores (for average).
- `_interaction_count: int` — Total interactions (for average).

---

#### Methods

##### `perceive_partner(partner_id: str, trust: float = 0.5, mode: InteractionMode = InteractionMode.SILENT, capability: Optional[Dict] = None) -> None`

Register or update a partner entry.

**Process**:
1. Call `_update_trust_decay()` to apply idle decay to all partners.
2. If `partner_id` exists:
   - Apply reciprocity bonus: if `quality_score > 0.7`, `trust = min(1.0, trust + 0.05)`.
   - Update `trust` (clamped [0.0, 1.0]), `mode`, `last_seen`, `interaction_count`.
   - Set `status = ACTIVE`.
3. Else create new `Partner` with:
   - `status = PROSPECT`
   - `capabilities` from `capability` dict keys (if provided)
   - `quality_score = 0.5` (neutral)
4. Append text entry to `history`.

**Note**: This is the primary entry point for any external interaction; always call before `accept_proposal()` etc.

---

##### `propose(proposal_type: str, content: Dict, recipient: str) -> Dict`

**Legacy API alias** for `propose_value()`. Maintains backward compatibility with existing code calling `propose()` directly.

**Returns**: See `propose_value()`.

---

##### `propose_value(proposal_type: str, content: Dict, recipient: str, expiry: Optional[float] = None) -> Dict`

Initiate a 1+1>2 value exchange negotiation.

**Process**:
1. Generate `proposal_id = uuid4()[:8]` (8-char hex).
2. Compute `expiry_time = time.time() + (expiry or self.negotiation_timeout)`.
3. Create `Negotiation` object with `status="pending"`.
4. Store in `self.active_negotiations[proposal_id]`.
5. Queue outbox message:
   ```python
   {
       "type": "proposal",           # NOT "VALUE_PROPOSAL" — backward compatible
       "proposal_id": proposal_id,
       "proposal_type": proposal_type,
       "content": content,
       "from": self.infant_id,
       "recipient": recipient,
       "timestamp": time.time(),
       "expiry": expiry_time,
   }
   ```
6. Append to `history`.

**Returns**:
```python
{
    "proposal_id": str,
    "status": "pending",
    "expiry": float,
}
```

---

##### `accept_proposal(proposal_id: str, increase: float = 0.1) -> Dict`

Accept a proposal — dual-mode: handles both formal `proposal_id` and legacy `partner_id`.

**Process**:
1. **Mode detection**:
   - If `proposal_id in self.active_negotiations`: formal negotiation mode.
     - Get `negotiation.responder` as `partner_id`.
     - Set `negotiation.status = "committed"`.
   - Else: legacy mode — `proposal_id` is directly a `partner_id`.
2. Ensure partner exists in `self.partners` (create default `Partner` if not).
3. Update partner:
   - `trust = max(0.0, min(1.0, trust + increase))`
   - `status = ACTIVE`
   - `last_seen = time.time()`
   - `quality_score = min(1.0, quality_score + 0.1)`
4. Increment interaction quality counters (`_interaction_quality_sum += 1.0`).
5. Append to `history`.

**Returns**:
```python
{
    "status": "accepted",
    "partner": partner_id,
    "trust": float,
    "committed": bool,    # True if formal negotiation was committed
}
```

---

##### `reject_proposal(proposal_id: str, decrease: float = 0.1, reason: Optional[str] = None) -> Dict`

Reject a proposal — also dual-mode.

**Process**: Similar to `accept_proposal()` but:
- `trust = max(0.0, trust − decrease)`
- `_interaction_quality_sum += 0.0`
- `negotiation.status = "rejected"` if formal mode.

**Returns**:
```python
{
    "status": "rejected",
    "partner": partner_id,
    "trust": float,
}
```

---

##### `evaluate_1plus1_gt_2(partner_id: str, outcome_quality: float) -> float`

Compute 1+1>2 synergy bonus.

**Formula**: `synergy = max(0.0, outcome_quality − 0.5)`, capped at `0.2`.

**Returns**: Bonus trust amount (0.0 to 0.2).

**Interpretation**: If joint outcome exceeds baseline quality 0.5, the excess (up to 0.2) can be added to trust to reward synergistic partnership.

---

##### `expire_negotiations() -> int`

Expire all `active_negotiations` past their `expiry` time (status still `"pending"`).

**Process**:
1. For each pending negotiation: if `expiry < now`, set `status = "expired"`.
2. Delete expired entries from `active_negotiations`.
3. Log to `history`.

**Returns**: Count of expired negotiations.

**Note**: Should be called periodically (e.g., every maintenance cycle).

---

##### `get_active_partners(min_trust: float = 0.3) -> List[Partner]`

Return partners with `status=ACTIVE` and `trust ≥ min_trust`, sorted by trust descending.

---

##### `get_stalled_partners(idle_hours: float = 48.0) -> List[Partner]`

Return partners with `last_seen` older than `idle_hours` threshold. These are candidates for `sever_partnership()`.

---

##### `sever_partnership(partner_id: str) -> bool`

Permanently remove a partner.

**Process**:
- Delete from `self.partners`.
- Also cancel any pending `active_negotiations` involving this partner.
- Log to `history`.

**Returns**: `True` if partner existed and was removed, `False` otherwise.

---

##### `explain_state(partner_id: str) -> str`

Human-readable status summary for a partner.

**Returns**: Multi-line string with trust, mode, status, interaction count, and age.

---

##### `explain_decision(proposal_id: str) -> str`

Explain why a proposal was accepted or rejected (if found in history).

**Returns**: Explanation string or `"proposal not found"`.

---

##### `get_status() -> Dict`

Overall interface health snapshot.

**Returns**:
```python
{
    "mode": str,                          # Current interaction mode value
    "partner_count": int,                  # Total partners
    "active_partners": int,               # ACTIVE status
    "stalled_partners": int,              # STALLED status
    "pending_negotiations": int,          # len(active_negotiations)
    "avg_interaction_quality": float,     # _interaction_quality_sum / count (0 if no interactions)
    "partners_detail": [                  # Per-partner summary
        {
            "id": str,
            "trust": float,
            "mode": str,
            "status": str,
            "quality_score": float,
            "interaction_count": int,
        },
        ...
    ],
}
```

---

### Data Structures

#### `Partner`

```python
@dataclass
class Partner:
    partner_id: str
    trust: float = 0.5                     # Trust score [0.0, 1.0]
    mode: InteractionMode = InteractionMode.SILENT
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0
    status: PartnershipStatus = PartnershipStatus.PROSPECT
    capabilities: List[str] = field(default_factory=list)
    quality_score: float = 0.5            # Historical success rate [0.0, 1.0]
    trust_decay_rate: float = 0.001       # Per-hour decay coefficient
    last_trust_update: float = field(default_factory=time.time)
```

**Lifecycle**: `PROSPECT` (first contact) → `ACTIVE` (interacting) → `STALLED` (48h idle) → `SEVERED` (removed).

---

#### `Negotiation`

```python
@dataclass
class Negotiation:
    proposal_id: str                      # Unique 8-char ID
    proposer: str                         # Infant ID who initiated
    responder: str                        # Partner ID who responds
    terms: Dict[str, Any]                 # Proposal content
    status: str = "pending"               # "pending" | "accepted" | "rejected" | "committed" | "expired"
    timestamp: float = field(default_factory=time.time)
    expiry: float = 0.0                   # Expiration timestamp
```

---

#### `PartnershipStatus` (Enum)

```python
class PartnershipStatus(Enum):
    UNKNOWN = "unknown"
    PROSPECT = "prospect"     # First contact, trust being established
    ACTIVE = "active"         # Actively collaborating
    STALLED = "stalled"      # No interaction > 48h
    SEVERED = "severed"      # Relationship terminated
```

---

#### `InteractionMode` (Enum)

```python
class InteractionMode(Enum):
    SILENT = "silent"         # No active communication
    LISTENING = "listening"   # Receiving only
    QUERYING = "querying"    # Requesting information
    PROPOSING = "proposing"  # Making value proposals
    CONTRACTING = "contracting"  # Formal agreement phase
```

---

## Core — SiliconInfant

**Module**: `cosmic_mycelium.infant.main`

Top-level orchestrator for a single infant node.

### Class: `SiliconInfant`

```python
SiliconInfant(
    infant_id: str,
    config: Optional[Dict] = None
)
```

**Parameters**:
- `infant_id` — Unique node identifier (used in logs, messages, partnership IDs).
- `config` — Optional dict overriding default subsystem parameters. Keys:
  - `energy_max` (float, default 100.0) — HIC energy ceiling.
  - `contract_duration`, `diffuse_duration`, `suspend_duration` — HIC phase timings.
  - `recovery_energy`, `recovery_rate` — HIC recovery params.

**Initialized subsystems** (all public attributes):
- `hic: HIC` — Breath-cycle energy manager.
- `sympnet: SympNetEngine` — Physics anchor (Hamiltonian integrator).
- `explorer: SlimeExplorer` — Layer 3 exploration.
- `memory: MyelinationMemory` — Layer 4 consolidation.
- `brain: SuperBrain` — Layer 5 global workspace.
- `interface: SymbiosisInterface` — Layer 6 partnership manager.

**Other attributes**:
- `state: Dict[str, float]` — Physical state `{"q": ..., "p": ...}` for sympnet.
- `inbox: List[CosmicPacket]` — Incoming message queue.
- `outbox: List[CosmicPacket]` — Outgoing message queue.
- `log: deque` — Rolling log of structured events (maxlen=1000).
- `start_time: float` — Unix timestamp of initialization.

---

#### Methods

##### `process_inbox() -> None`

Process all queued inbox messages.

**Behavior**: For each message in `self.inbox`:
- Route to appropriate subsystem based on `message.type`:
  - `"physical_sensor"` → `self.explorer.explore()`
  - `"proposal"` / `"value_proposal"` → `self.interface.perceive_partner()` + enqueue response
  - `"query"` → generate status reply via `self.interface.explain_state()`
- Clear `self.inbox` after processing.

**Note**: This method is called once per main loop iteration.

---

##### `get_status() -> Dict`

Aggregate health snapshot across all subsystems.

**Returns**: Combined dict with keys:
- `infant_id`, `uptime_seconds`, `hic_state`
- `explorer_status` (from `SlimeExplorer.get_status()`)
- `memory_status` (from `MyelinationMemory.get_status()`)
- `brain_status` (from `SuperBrain.get_status()`)
- `interface_status` (from `SymbiosisInterface.get_status()`)

---

### Class: `InfantRunner`

**Module**: `cosmic_mycelium.scripts.run_infant`

Async service runner that manages the lifecycle of a `SiliconInfant` plus metrics & health servers.

#### Running

```bash
# Using Python directly
python -m cosmic_mycelium.scripts.run_infant --id my-infant-001

# Using Docker Compose (P5)
docker-compose --profile dev up infant
```

**CLI Arguments**:
- `--id INFANT_ID` — Override `INFANT_ID` env var.
- `--profile dev|prod` — Development (debug logging, hot reload hints) vs production.
- `--metrics-port PORT` — Override `METRICS_PORT`.
- `--health-port PORT` — Override `HEALTH_PORT`.

**Environment Variables** (see `.env.example` for full list):
- `COSMIC_ENV`, `INFANT_ID`, `INFANT_ENERGY_MAX`, `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `LOG_LEVEL`, etc.

---

## Common — ConfigManager

**Module**: `cosmic_mycelium.common.config_manager`

Unified configuration across scales (infant/cluster/global).

### Class: `ConfigManager`

```python
ConfigManager(
    scale: str = "infant",          # "infant" | "cluster" | "global"
    overrides: Optional[Dict] = None
)
```

**Preset scales** (class methods):
- `ConfigManager.for_infant()` — Single-node defaults.
- `ConfigManager.for_cluster()` — Multi-node cluster defaults.
- `ConfigManager.for_global()` — Planet-scale defaults.

---

#### Methods

##### `get(key: str, default: Any = None) -> Any`

Get a configuration value with optional fallback.

##### `get_embedding_dim() -> int`

Get scale-appropriate embedding dimension:
- infant → 16
- cluster → 64
- global → 256

##### `get_num_spores() -> int`

Get scale-appropriate spore count:
- infant → 10
- cluster → 40
- global → 160

##### `get_max_traces() -> int`

Get memory capacity:
- infant → 10,000
- cluster → 100,000
- global → 1,000,000

##### `as_dict() -> Dict`

Export all configuration as a plain dict (suitable for passing to `SiliconInfant`).

---

## Data Structures

### `CosmicPacket`

**Module**: `cosmic_mycelium.common.data_packet`

Standard message envelope across all layers.

```python
@dataclass
class CosmicPacket:
    sender: str                        # Origin node ID
    recipient: str                     # Destination node ID
    layer: int                         # Source layer (1–6)
    ptype: str                         # Packet type ("sensor", "proposal", "query", ...)
    payload: Dict[str, Any]            # Arbitrary content
    timestamp: float = field(default_factory=time.time)
    ttl: int = 10                      # Hop limit (decremented per hop)
    trace_id: Optional[str] = None     # Distributed tracing ID
```

**Usage**: All inter-layer and inter-node messages use this envelope. Packets are queued in `inbox`/`outbox` and routed by the `SiliconInfant` main loop.

---

### `PhysicalFingerprint`

**Module**: `cosmic_mycelium.common.physical_fingerprint`

Deterministic SHA256 fingerprint from physical state dict.

```python
fingerprint = PhysicalFingerprint()
fp_hex = fingerprint.generate({"temp": 25.0, "vibration": 0.5})
# → "a3f5c2..." (64 hex chars)
```

**Properties**:
- Order-independent: dict keys sorted before hashing.
- Type-coercion: all values converted to `repr()` string.
- Stable across runs: same input → same output.

**Use**: `SemanticMapper` uses fingerprints as persistent concept IDs.

---

## Constants

### Physical Constants

**Module**: `cosmic_mycelium.common.constants`

| Name | Value | Meaning |
|------|-------|---------|
| `BASE_DT` | `0.01` | Symplectic integrator base timestep (seconds) |
| `ENERGY_DRIFT_THRESHOLD` | `0.001` | Max allowed relative drift (0.1%) |
| `MAX_PATH_LENGTH_DEFAULT` | `5` | Default SlimeExplorer max steps |
| `DEFAULT_EMBEDDING_DIM` | `16` | Infant-scale concept vector size |

---

## Version

```python
from cosmic_mycelium import __version__
# → "0.1.0" (semantic versioning)
```
