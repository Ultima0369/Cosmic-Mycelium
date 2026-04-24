# API Reference — Cosmic Mycelium

Complete reference for the six-layer infant core API.

---

## Table of Contents

- [Layer 2 — SemanticMapper](#layer-2---semanticmapper)
- [Layer 3 — SlimeExplorer](#layer-3---slimeexplorer)
- [Layer 4 — MyelinationMemory](#layer-4---myelinationmemory)
- [Utilities — SemanticVectorIndex](#utilities---semanticvectorindex)
- [Common — FeatureManager](#common---featuremanager)
- [Layer 5 — SuperBrain](#layer-5---superbrain)
- [Layer 6 — SymbiosisInterface](#layer-6---symbiosisinterface)
- **Epic 5 — Embodied Cognition**
  - [SensorimotorContingencyLearner](#sensorimotorcontingencylearner)
  - [ActivePerceptionGate](#activeperceptiongate)
- [Core — SiliconInfant](#core---siliconinfant)
- [Common — ConfigManager](#common---configmanager)
- [Skills — Plugin System](#skills---plugin-system)
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

##### `consolidate_semantic_paths(similarity_threshold: float = 0.9) -> int`

Epic 3 — Semantic consolidation of paths with similar end-state embeddings.

**Process**:
1. Collect all traces with non-None `state_embedding`.
2. Compute pairwise cosine similarity matrix.
3. Greedy merge: for each pair with similarity ≥ threshold, merge the weaker trace into the stronger (strength += 0.3 × weaker, access_count absorbed).
4. Delete merged traces.

**Parameters**:
- `similarity_threshold` — Cosine similarity ∈ [0, 1] to consider two end states "semantically similar". Default 0.9 (high precision).

**Returns**: Number of traces merged (absorbed).

**Note**: Requires `semantic_mapper` to be set (otherwise returns 0). End-state embeddings are computed automatically during `reinforce(end_state=...)`.

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
    state_embedding: np.ndarray | None = None  # Epic 3: end-state semantic vector for consolidation
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

## Utilities — SemanticVectorIndex

**Module**: `cosmic_mycelium.infant.core.semantic_vector_index`

FAISS-based vector similarity search with numpy fallback.

### Class: `SemanticVectorIndex`

```python
SemanticVectorIndex(dim: int, index_path: Path | None = None)
```

**Parameters**:
- `dim` — Embedding dimensionality (must match all query/insert vectors).
- `index_path` — Optional directory to load persisted index from (`index.faiss`, `id_map.pkl`).

**Attributes**:
- `index: faiss.IndexFlatIP | None` — FAISS inner-product index (cosine on normalized vectors).
- `id_map: List[str]` — Row index → feature code ID mapping.
- `_fallback_vectors: List[Tuple[str, np.ndarray]]` — Numpy fallback storage when FAISS unavailable.

---

#### Methods

##### `add(feature_code_id: str, vector: np.ndarray) -> None`

Add a vector to the index.

**Process**:
1. Cast to `float32`, reshape to `(1, dim)`.
2. L2-normalize (for cosine similarity).
3. If FAISS available: `index.add()`; else append to `_fallback_vectors`.
4. Append `feature_code_id` to `id_map`.

---

##### `search(query_vector: np.ndarray, k: int = 5) -> List[Tuple[str, float]]`

Nearest-neighbor search.

**Process**:
1. Normalize query vector to unit length.
2. If FAISS: `index.search()` returns (distances, indices).
3. Else fallback: linear dot product over `_fallback_vectors`.
4. Map row indices back to `feature_code_id` via `id_map`.

**Returns**: List of `(feature_code_id, similarity_score)` sorted descending by score. Score range [−1, 1] for cosine.

---

##### `save(path: Path) -> None`

Persist index to disk.

**Files written**:
- `{path}/index.faiss` — FAISS binary index (if FAISS enabled).
- `{path}/id_map.pkl` — Pickled ID mapping.

---

##### `load(path: Path) -> None`

Load index from disk.

**Behavior**: Reads `index.faiss` via `faiss.read_index()` and `id_map.pkl` via pickle. If files missing, index starts empty.

---

##### `clear() -> None`

Remove all vectors, resetting index to empty state.

---

## Common — FeatureManager

**Module**: `cosmic_mycelium.infant.feature_manager`

Persistent "myelinated memory" manager inspired by Hermes Skill Manager. Features (called "特征码" / feature codes) are physical-anchor-verified successful experiences.

### Class: `FeatureManager`

```python
FeatureManager(
    infant_id: str,
    storage_path: Path | None = None,
    semantic_mapper: Any | None = None
)
```

**Parameters**:
- `infant_id` — Unique infant node identifier.
- `storage_path` — Directory for JSON feature files (default: `~/.cosmic_mycelium/{infant_id}/features/`).
- `semantic_mapper` — Optional SemanticMapper for computing embeddings (enables Epic 3 features).

**Attributes**:
- `features: Dict[str, FeatureCode]` — In-memory feature code registry.
- `pattern_index: Dict[str, List[str]]` — Trigger pattern → feature code IDs inverted index.
- `vector_index: SemanticVectorIndex` — Epic 3: FAISS vector index for semantic search.
- `storage_path: Path` — Disk directory for feature JSON files.
- `index_path: Path` — Directory for FAISS index files (`index.faiss`, `id_map.pkl`).

---

#### Methods

##### `create_or_update(name, description, trigger_patterns, action_sequence, validation_fingerprint=None) -> FeatureCode`

Create a new feature code or update an existing one (same name + trigger patterns → same ID).

**Behavior**:
- ID generation: `SHA256(name + sorted(trigger_patterns))[:12]`
- If existing: merge action sequences (new prepended, keep last 10), update description, optionally update fingerprint.
- If new: create `FeatureCode`, insert into `pattern_index`.
- Persist to disk and (if semantic_mapper present) compute embedding → add to vector index.

**Returns**: The created or updated `FeatureCode`.

---

##### `match(perceived_patterns: List[str], min_efficacy: float = 0.3) -> List[FeatureCode]`

Pattern-based feature lookup (pre-Epic 3 legacy method).

**Process**:
1. Collect all feature IDs whose `trigger_patterns` intersect with `perceived_patterns`.
2. Filter by `efficacy() >= min_efficacy`.
3. Sort by `efficacy × time_decay`, where `time_decay = 0.9^((now − last_used)/86400)` (daily 0.9 decay).

**Returns**: Sorted list of matching `FeatureCode` objects.

---

##### `recall_semantic(query: str, k: int = 5) -> List[FeatureCode]` *(Epic 3)*

Semantic similarity search over feature codes.

**Process**:
1. Convert `query` text to embedding via `text_to_embedding(query, dim=vector_index.dim)`.
2. Normalize to unit length.
3. FAISS (or numpy fallback) nearest-neighbor search for top-`k`.
4. Record `knowledge_recall_hits` or `knowledge_recall_misses` Prometheus metric.

**Returns**: List of up to `k` most semantically similar `FeatureCode` objects.

---

##### `recall_by_embedding(vector: np.ndarray, k: int = 5) -> List[FeatureCode]` *(Epic 3)*

Direct vector-based similarity search (no query text).

**Parameters**:
- `vector` — Raw embedding vector (will be normalized internally).
- `k` — Number of nearest neighbors.

**Returns**: List of most similar feature codes by cosine similarity.

---

##### `cluster_active_features(min_samples: int = 3, eps: float = 0.3) -> Dict[int, List[FeatureCode]]` *(Epic 3)*

DBSCAN-style density-based clustering of features by embedding similarity.

**Process**:
1. Collect all features with non-None `embedding`.
2. If fewer than `min_samples`, return empty dict.
3. Compute pairwise cosine distance matrix (`1 - cosine_similarity`).
4. Run density-based clustering: core point = ≥ `min_samples` neighbors within `eps`.
5. Assign `cluster_id` attribute on each clustered feature.
6. Persist cluster assignments to `clusters.json`.

**Parameters**:
- `min_samples` — Minimum points to form a cluster (default 3).
- `eps` — Maximum cosine distance (not similarity!) to be considered a neighbor (default 0.3 → similarity ≥ 0.7).

**Returns**: Dict mapping `cluster_id` (0, 1, ...) → list of features in that cluster. Noise points (unclustered) omitted.

---

##### `get_cluster_label(cluster_id: int) -> str` *(Epic 3)*

Generate a human-readable label for a cluster by extracting most common non-stopwords from member feature names/descriptions.

**Algorithm**:
1. Gather all words from `name` and `description` of cluster members.
2. Filter stopwords (the, and, or, for, in, on, with, to, a, an, of, is, are) and short words (≤2 chars).
3. Return top 3 most common words joined by spaces.

**Returns**: Label like `"vibration energy response"` or `"cluster_{id}"` if no words found.

---

##### `get(code_id: str) -> FeatureCode | None`

Get a single feature by ID.

---

##### `reinforce(code_id: str, success: bool, saliency: float = 1.0) -> None`

Reinforce or weaken a feature's efficacy, with optional saliency weighting.

**Behavior**:
- Increment `success_count` or `failure_count` by `1.0 × saliency`.
- Update `last_used = now`.
- Auto-forget if `efficacy() < 0.1` and total uses > 10.
- Guarded by `pause_adaptation` meta-cognitive suspend (IMP-04).

---

##### `list_all() -> List[FeatureCode]`

All features sorted by efficacy descending.

---

##### `get_stats() -> Dict`

Summary metrics for monitoring.

---

### Data Structure: `FeatureCode`

```python
@dataclass
class FeatureCode:
    code_id: str                        # SHA256(name+sorted(patterns))[:12]
    name: str                           # Human-readable name
    description: str                    # When this feature is useful
    trigger_patterns: List[str]         # Perception pattern keywords
    action_sequence: List[Dict]         # Recommended action parameters
    success_count: float = 0            # Hebbian successes (may be fractional due to saliency)
    failure_count: float = 0            # Hebbian failures
    last_used: float = time.time()      # Last reinforcement timestamp
    created_at: float = time.time()     # Creation timestamp
    validation_fingerprint: str | None  # Physical fingerprint verifying successful deployment
    embedding: np.ndarray | None = None # Epic 3: normalized embedding vector for semantic search
    cluster_id: int | None = None       # Epic 3: assigned cluster ID from cluster_active_features()
```

**Methods**:
- `efficacy() → float` — Returns `success / (success + failure)` or 0.5 if unused.
- `reinforce(success: bool, saliency: float = 1.0) → None` — Update counts and `last_used`.
- `compute_embedding(semantic_mapper, dim=None) → np.ndarray` — Compute normalized embedding from name/description/triggers.
- `to_dict() / from_dict()` — JSON serialization (embedding converted to/from list).

---

## Utilities — SemanticVectorIndex

**Module**: `cosmic_mycelium.infant.core.semantic_vector_index`

FAISS-based vector similarity search with numpy fallback.

### Class: `SemanticVectorIndex`

```python
SemanticVectorIndex(dim: int, index_path: Path | None = None)
```

**Parameters**:
- `dim` — Embedding dimensionality (must match all query/insert vectors).
- `index_path` — Optional directory to load persisted index from (`index.faiss`, `id_map.pkl`).

**Attributes**:
- `index: faiss.IndexFlatIP | None` — FAISS inner-product index (cosine on normalized vectors).
- `id_map: List[str]` — Row index → feature code ID mapping.
- `_fallback_vectors: List[Tuple[str, np.ndarray]]` — Numpy fallback storage when FAISS unavailable.

---

#### Methods

##### `add(feature_code_id: str, vector: np.ndarray) -> None`

Add a vector to the index.

**Process**:
1. Cast to `float32`, reshape to `(1, dim)`.
2. L2-normalize (for cosine similarity).
3. If FAISS available: `index.add()`; else append to `_fallback_vectors`.
4. Append `feature_code_id` to `id_map`.

---

##### `search(query_vector: np.ndarray, k: int = 5) -> List[Tuple[str, float]]`

Nearest-neighbor search.

**Process**:
1. Normalize query vector to unit length.
2. If FAISS: `index.search()` returns (distances, indices).
3. Else fallback: linear dot product over `_fallback_vectors`.
4. Map row indices back to `feature_code_id` via `id_map`.

**Returns**: List of `(feature_code_id, similarity_score)` sorted descending by score. Score range [−1, 1] for cosine.

---

##### `save(path: Path) -> None`

Persist index to disk.

**Files written**:
- `{path}/index.faiss` — FAISS binary index (if FAISS enabled).
- `{path}/id_map.pkl` — Pickled ID mapping.

---

##### `load(path: Path) -> None`

Load index from disk.

**Behavior**: Reads `index.faiss` via `faiss.read_index()` and `id_map.pkl` via pickle. If files missing, index starts empty.

---

##### `clear() -> None`

Remove all vectors, resetting index to empty state.


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

## Epic 5 — Embodied Cognition

### SensorimotorContingencyLearner

**Module**: `cosmic_mycelium.infant.core.embodied_loop`

Learns action → sensor delta mappings through experience.

#### Class: `SensorimotorContingencyLearner`

```python
SensorimotorContingencyLearner(max_history_per_action: int = 100)
```

**Parameters**:
- `max_history_per_action` — Maximum number of Δ observations to keep per action (sliding window, default 100).

#### Methods

##### `record(action_signature: str, prev_sensors: Dict[str, float], post_sensors: Dict[str, float]) -> None`

Record one (action, before, after) sensor triplet.

Computes `delta = post - prev` for all sensors and updates the moving average for that action.

##### `predict(action_signature: str, current_sensors: Dict[str, float]) -> Dict[str, float] | None`

Predict post-action sensor values given current sensors.

Returns `None` if action is unknown.

##### `get_contingency(action_signature: str) -> Dict[str, float] | None`

Return the average Δ vector for an action (or `None` if unseen).

##### `known_actions() -> List[str]`

List all learned action signatures.

##### `get_confidence(action_signature: str) -> float`

Confidence in [0, 1] based on observation count: `n / (n + 5.0)`.

##### `get_status() -> Dict`

Summary: `{"known_actions": int, "total_observations": int, "actions": List[str]}`.

##### `infer_action(prev_sensors: Dict[str, float], post_sensors: Dict[str, float], k: int = 3) -> List[Tuple[str, float]]`

**Phase 5.3 — Inverse Model.** Given a sensor transition `(prev → post)`, infer which action most likely caused it.

Returns a ranked list of `(action_signature, confidence)` tuples, confidence summing to 1.0. Uses negative MSE + observation-count prior (`log(n)`) before softmax. Unknown transitions yield `[]`.

##### `train_test_split(test_ratio: float = 0.3) -> Tuple[List[Observation], List[Observation]]`

**Phase 5.3 — Cross-validation.** Split all accumulated raw `(prev, post)` observations into train/test lists.

Each list element is an `Observation(prev, post)` dataclass. Split is shuffled with a fixed RNG seed for reproducibility. Total observations = `len(train) + len(test)`.

**Data Class**: `Observation(prev: Dict[str, float], post: Dict[str, float])`

Simple immutable container for a single sensor transition pair, used as the return type of `train_test_split`.

---

### ActivePerceptionGate

**Module**: `cosmic_mycelium.infant.core.active_perception`

Attention gate that selects which sensors to sample based on prediction error history.

#### Class: `ActivePerceptionGate`

```python
ActivePerceptionGate(
    initial_interest: float = 0.1,
    decay_rate: float = 0.9,
    boost: float = 2.0
)
```

**Parameters**:
- `initial_interest` — Starting score for a brand-new sensor (default 0.1).
- `decay_rate` — Per-update multiplier for existing scores (default 0.9).
- `boost` — Error multiplier that boosts interest (default 2.0).

#### Methods

##### `update(prediction_error: Dict[str, float]) -> None`

Update interest scores from a dict of per-sensor prediction errors.

- New sensors: `score = error × boost`
- Existing sensors: `score = old × decay_rate + error × boost`

##### `decay() -> None`

Multiply all current scores by `decay_rate` (global time-based decay).

##### `get_attention_mask(k: int) -> Set[str]`

Return the set of the `k` highest-scoring sensor names.

##### `should_sample(sensor: str, threshold: float) -> bool`

Return `True` if sensor's score ≥ `threshold`.

##### `reset() -> None`

Clear all interest scores.

---

### SkillAbstractor

**Module**: `cosmic_mycelium.infant.core.skill_abstractor`

Discovers frequent action sequences (n-grams) in the infant's action-delta history and defines them as reusable macro-actions.

#### Class: `SkillAbstractor`

```python
SkillAbstractor(
    min_support: int = 5,
    max_ngram: int = 3,
    window_size: int = 100,
)
```

**Parameters**:
- `min_support` — Minimum number of occurrences for a pattern to be promoted to a macro (default 5).
- `max_ngram` — Maximum length of action sequences to consider (default 3).
- `window_size` — Sliding window size (keeps only recent observations, default 100).

#### Data Class: `MacroDefinition`

```python
@dataclass(frozen=True)
class MacroDefinition:
    signature: str                    # e.g. "macro_A_B"
    sequence: Tuple[str, ...]         # (action1, action2, ...)
    avg_delta: Dict[str, float]       # combined average sensor change
    support: int                      # times this pattern was observed
```

#### Methods

##### `record(action_sig: str, delta: Dict[str, float]) -> None`

Record one `(action, sensor_delta)` observation.

##### `mine() -> List[MacroDefinition]`

Mine the current history window for new patterns meeting `min_support`. Returns only **newly discovered** macros (idempotent).

##### `get_all_macros() -> List[MacroDefinition]`

Return all macros discovered so far.

##### `get_macro(signature: str) -> MacroDefinition | None`

Look up a macro by its signature.

---

### EmbodiedMetacognition

**Module**: `cosmic_mycelium.infant.core.embodied_metacognition`

Monitors sensorimotor learning progress and toggles the infant between exploration and exploitation modes using hysteresis thresholds.

#### Enum: `MetacognitiveMode`

```python
class MetacognitiveMode(Enum):
    EXPLORE = "explore"   # Try new actions, build model
    EXPLOIT = "exploit"   # Use known high-confidence actions
```

#### Class: `EmbodiedMetacognition`

```python
EmbodiedMetacognition(
    switch_threshold: float = 0.6,
    revert_threshold: float = 0.4,
    window_size: int = 5,
)
```

**Parameters**:
- `switch_threshold` — Rolling average confidence above which mode switches from EXPLORE → EXPLOIT (default 0.6).
- `revert_threshold` — Rolling average confidence below which mode switches from EXPLOIT → EXPLORE (default 0.4). Must be lower than `switch_threshold` to create hysteresis dead-band.
- `window_size` — Number of recent cycles to average over (default 5). Mode does not switch until at least this many updates have been received.

#### Methods

##### `update(confidence_dict: Dict[str, float]) -> None`

Process a dictionary of action confidences for the current cycle (typically from `SensorimotorContingencyLearner.infer_action()`). The rolling average is updated and mode may switch if threshold is crossed.

##### `get_mode() -> MetacognitiveMode`

Return the current mode (`EXPLORE` or `EXPLOIT`).

##### `get_exploration_factor() -> float`

Return the exploration factor for `SlimeExplorer`:
- `EXPLORE` → `0.6` (high randomness, broad search)
- `EXPLOIT` → `0.1` (low randomness, follow known pheromone paths)

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
  - `research_enabled` (bool, default **True**) — Enable autonomous research loop (Epic 1). When enabled, initializes `KnowledgeStore`, `QuestionGenerator`, `ExperimentDesigner` and integrates `ResearchSkill`.
  - `embedding_dim` (int, default 16) — Semantic embedding dimensionality.

**Initialized subsystems** (all public attributes):
- `hic: HIC` — Breath-cycle energy manager.
- `sympnet: SympNetEngine` — Physics anchor (Hamiltonian integrator).
- `explorer: SlimeExplorer` — Layer 3 exploration.
- `memory: MyelinationMemory` — Layer 4 consolidation.
- `brain: SuperBrain` — Layer 5 global workspace.
- `interface: SymbiosisInterface` — Layer 6 partnership manager.

**Conditional attributes** (available when `research_enabled=True`):
- `knowledge_store: KnowledgeStore` — Vector semantic memory for research entries.
- `question_generator: QuestionGenerator` — Generates research questions from history.
- `experiment_designer: ExperimentDesigner` — Designs executable experiment plans.

**Other attributes**:
- `state: Dict[str, float]` — Physical state `{"q": ..., "p": ...}` for sympnet.
- `inbox: List[CosmicPacket]` — Incoming message queue.
- `outbox: List[CosmicPacket]` — Outgoing message queue.
- `log: deque` — Rolling log of structured events (maxlen=1000).
- `start_time: float` — Unix timestamp of initialization.

**Phase 5.1 — Embodied Cognition attributes** (when integrated):
- `_sensorimotor_learner: SensorimotorContingencyLearner` — Learns action→Δsensor mappings.
- `_active_perception_gate: ActivePerceptionGate` — Tracks sensor interest based on prediction error.
- `_prev_sensors: Dict | None` — Cached sensor snapshot from previous cycle (1-cycle lag for recording).
- `_pending_action_signature: str | None` — Action signature awaiting next-cycle outcome recording.

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

##### `get_active_sensors(k: int = 3) -> Set[str]`

**Phase 5.1 — Active Perception query**.

Return the top-`k` most interesting sensors according to the active perception gate.
Useful for selective sensing in the next cycle.

**Parameters**:
- `k` — Number of top sensors to return (default 3).

**Returns**: Set of sensor names (e.g., `{"vibration", "temperature"}`).

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

## Skills — Plugin System

**Modules**:
- `cosmic_mycelium.infant.skills.base` — Protocol and base types
- `cosmic_mycelium.infant.skills.registry` — Global singleton registry
- `cosmic_mycelium.infant.skills.loader` — Discovery and loading (entry points + built-in)
- `cosmic_mycelium.infant.skills.lifecycle` — Per-cycle scheduler and resource budgeting
- `cosmic_mycelium.infant.skills.research` — Example built-in skill (autonomous research loop)

---

### Protocol: `InfantSkill`

```python
class InfantSkill(Protocol):
    name: str
    version: str
    description: str
    dependencies: list[str]
    parallelism_policy: ParallelismPolicy  # Sprint 2: threading policy (default SEQUENTIAL)
    def initialize(self, context: SkillContext) -> None: ...
    def can_activate(self, context: SkillContext) -> bool: ...
    def execute(self, params: dict[str, Any]) -> Any: ...
    def get_resource_usage(self) -> dict[str, float]: ...
    def shutdown(self) -> None: ...
    def get_status(self) -> dict[str, Any]: ...

    # Sprint 1 — Async I/O extension (optional)
    def can_execute_async(self) -> bool: ...      # Default: False
    async def execute_async(self, params: dict[str, Any]) -> Any: ...  # Optional
```

**ParallelismPolicy** (Sprint 2):
```python
from enum import Enum
class ParallelismPolicy(Enum):
    SEQUENTIAL = "sequential"   # Must run on main thread (dependency ordering)
    ISOLATED = "isolated"       # No shared state access; thread-safe
    READONLY = "readonly"       # Read-only shared access; thread-safe
    SHARED_WRITE = "shared_write"  # Writes shared state; internal locking required
```

To enable thread-pool execution, set `parallelism_policy = ParallelismPolicy.ISOLATED` (or READONLY) at class level. The lifecycle manager automatically dispatches such skills to a `ThreadPoolExecutor`.

**Async vs Thread-Pool**: These are orthogonal dimensions:
- `can_execute_async()=True` → runs via `asyncio` (I/O-bound, network)
- `parallelism_policy=ISOLATED/READONLY` → runs via `ThreadPoolExecutor` (CPU-bound)
Skills can be both async AND isolated, but typically async skills are I/O-bound and don't need a separate thread pool.

---

### Data Structure: `SkillContext`

```python
@dataclass
class SkillContext:
    infant_id: str
    cycle_count: int
    energy_available: float
    hic_suspended: bool = False
    timestamp: float = field(default_factory=time.time)
```

Passed to `initialize()` once and `tick()` each cycle. Skills use this to decide activation and track state.

---

### Exceptions

- `SkillInitializationError` — Raised during registration or initialization failures.
- `SkillExecutionError` — Raised when a skill's `execute()` encounters an error.

---

### Class: `SkillRegistry`

Global singleton registry managing all skills.

```python
registry = SkillRegistry()  # always returns the same instance
```

**Methods**:

| Method | Description |
|--------|-------------|
| `register(skill)` | Register a skill instance; raises if name already exists |
| `unregister(name)` | Remove a skill |
| `get(name)` | Return skill instance or `None` |
| `list_all()` | All registered skill instances |
| `list_enabled(context)` | Skills where `can_activate(context)` is `True` |
| `topological_sort()` | Dependency-ordered load list; raises `ValueError` on cycles |
| `validate_dependencies()` | Verify all dependencies are registered; raises if missing |
| `initialize_all(context)` | Call `initialize()` on each skill in topological order; rolls back on failure |
| `shutdown_all()` | Call `shutdown()` on all skills in reverse load order |
| `on(event, callback)` / `off(event, sub_id)` | Subscribe/unsubscribe to lifecycle events |

**Events**: `skill_loaded`, `skill_unloaded`, `skill_executed`.

---

### Class: `SkillLoader`

Discovers and registers skills from entry points (third-party plugins) and built-in packages.

```python
loader = SkillLoader(registry)  # registry optional; creates new if omitted
loader.load_all()               # discover built-in + entry points
```

**Discovery order**:
1. Built-in: recursively scans `cosmic_mycelium.infant.skills` package.
2. Entry points: scans `cosmic_mycelium.skills` group (setuptools).

Third-party plugin example (`setup.py`):
```python
setup(
    name="infant-skill-math",
    entry_points={"cosmic_mycelium.skills": ["math = math_skill:MathSkill"]},
)
```

---

### Class: `SkillLifecycleManager`

Schedules skill execution each cycle, enforces energy budgets, and responds to HIC meta-cognitive suspend.

```python
mgr = SkillLifecycleManager(registry, max_executions_per_cycle=5, energy_budget_ratio=0.1)
```

**Parameters**:
- `max_executions_per_cycle` — Hard cap on skill executions per tick (prevent runaway).
- `energy_budget_ratio` — Maximum fraction of current energy that can be spent in one cycle (default 0.1 → 10%).
- `thread_pool_size` — Maximum worker threads for CPU-bound skills (default 2, Sprint 2).

**Key methods**:
- `tick(context) -> list[SkillExecutionRecord]` — Run enabled skills (respecting budget, manual disables). Returns per-skill records.
  - **Execution phases**:
    1. `SEQUENTIAL` skills (preserve dependency order)
    2. `SHARED_WRITE` skills (sequential, internal locks)
    3. `ISOLATED` + `READONLY` skills (thread pool batch)
    4. `ASYNC` skills (`asyncio.gather()`)
  - **Async timeout**: `ASYNCIO_TIMEOUT = 5.0` seconds; hanging tasks cancelled.
  - **Thread pool timeout**: `THREADPOOL_TIMEOUT = 5.0` seconds.
  - **Energy accounting**: Atomic reservation before dispatch (`_reserve_energy`), deduct on success (`_deduct_energy`), refund on failure (`_refund_energy`). Guarantees budget never exceeded even under parallel dispatch.
- `disable(name)` / `enable(name)` — Manual skill override.
- `is_enabled(name)` — Check if skill will run.
- `on_hic_suspend()` — Disable all non-core skills (`energy_monitor`, `physical_anchor` remain).
- `on_hic_resume()` — Re-enable all skills.
- `get_stats()` — Monitoring: total executions, error rate, disabled list, `thread_pool_size`, `budget_remaining`, `spent_energy`.
- `shutdown()` — Cleanup: shuts down thread pool executor.

**Energy budgeting**: Before executing each skill, the manager fetches `skill.get_resource_usage()["energy_cost"]`. Using atomic `_reserve_energy()`, it checks prospective cost against `budget_remaining`. Skills are skipped if reservation fails. This pre-allocation pattern prevents overspending when multiple skills dispatch in parallel.

**Async support** (Sprint 1, 2026-04-23): Skills implementing `can_execute_async() → True` and `execute_async()` are automatically detected and run in a concurrent batch via `asyncio.gather()`. This is opt-in: existing skills without these methods run unchanged.

**Thread pool** (Sprint 2, 2026-04-24): Skills with `parallelism_policy` set to `ISOLATED` or `READONLY` are dispatched to a shared `ThreadPoolExecutor`. Energy is reserved before submission; successful completion deducts cost, failures refund. Timeouts (5s) cancel hanging tasks.

---

### Resource Lock Manager

**Module**: `cosmic_mycelium.infant.skills.resource_lock_manager`

Provides fine-grained reentrant locks for shared infant state to enable safe parallel execution.

```python
from cosmic_mycelium.infant.skills.resource_lock_manager import ResourceLockManager

# Acquire a single resource
with ResourceLockManager.lock("feature_manager"):
    fm.append(...)  # protected

# Acquire multiple resources in global order (deadlock-free)
with ResourceLockManager.lock_multiple(["memory", "feature_manager"]):
    # Locks acquired in order: feature_manager → memory (alphabetical)
    ...
```

**Global lock order** (for deadlock prevention):
1. `"brain"`
2. `"feature_manager"`
3. `"hic"`
4. `"memory"`

Any call to `lock_multiple()` sorts requested resources by this order before acquiring. Skills that need multiple locks should always request them together via `lock_multiple()` to guarantee safe ordering.

**Resources**: `"feature_manager"`, `"memory"`, `"brain"`, `"hic"`.

**Methods**:
- `get_lock(name) -> threading.RLock` — get the lock object directly.
- `lock(name) -> contextmanager` — acquire single resource.
- `lock_multiple(names) -> contextmanager` — acquire multiple in global order.
- `is_locked(name) -> bool` — check if resource currently held.

**Usage pattern in skills** (Sprint 2):
```python
class SomeSharedWriteSkill(InfantSkill):
    parallelism_policy = ParallelismPolicy.SHARED_WRITE
    def execute(self, params):
        # Acquire only the resources needed for this mutation
        with ResourceLockManager.lock("feature_manager"):
            self.feature_manager.append(...)
```

---

### Data Structure: `SkillExecutionRecord`

```python
@dataclass
class SkillExecutionRecord:
    skill_name: str
    params: dict
    start_time: float
    end_time: float = 0.0
    success: bool = False
    error: str | None = None
    energy_cost: float = 0.0
    result: Any = None
```

Populated by `SkillLifecycleManager` for every execution; stored in `execution_history` (LRU, last 1000).

---

### Built-in Skill: `ResearchSkill`

**Module**: `cosmic_mycelium.infant.skills.research`

Wraps Epic 1 components (QuestionGenerator, ExperimentDesigner, KnowledgeStore) as a pluggable skill.

```python
ResearchSkill(knowledge_store: KnowledgeStore | None = None)
```

**Activation conditions** (`can_activate`):
- Skill initialized and `knowledge_store` injected
- Current energy ≥ 50
- At least 10 cycles since last execution (cooldown)
- HIC not suspended (handled by lifecycle manager)

**Execute parameters**:
- `num_questions` (int, default 1) — How many questions to generate.
- `recency_days` (float, default 30.0) — Knowledge window.
- `force_bootstrap` (bool, default False) — Run self-test even if knowledge base populated.

**Behavior**:
- If knowledge store empty or `force_bootstrap=True`: runs a fixed bootstrap experiment ("调整呼吸节律对能量恢复有何影响？").
- Otherwise: generates a question, designs an experiment, executes via `knowledge_store.execute_experiment`, records result.

**Resource usage**:
- Energy cost: `5.0`
- Duration: `0.1s`
- Memory: `10MB`

**Status fields**: `name`, `version`, `initialized`, `execution_count`, `last_execution`, `knowledge_entries`.

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
