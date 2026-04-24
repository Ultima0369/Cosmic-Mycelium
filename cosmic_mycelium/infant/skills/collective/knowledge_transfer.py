"""
Knowledge Transfer — Cross-Infant Learning & Memory Sharing

Enables infants to request and receive semantic knowledge from aligned partners.
Transfers FeatureManager entries (feature codes with embeddings) to accelerate learning.

Phase: Epic 4 (主动集群协同)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.infant.skills.base import InfantSkill, ParallelismPolicy, SkillContext

if TYPE_CHECKING:
    from cosmic_mycelium.cluster.node_manager import NodeManager
    from cosmic_mycelium.infant.feature_manager import FeatureManager
    from cosmic_mycelium.infant.hic import HIC


@dataclass
class KnowledgeEntry:
    """
    A transferable unit of learned knowledge.

    Contains the feature code, semantic embedding, and metadata
    sufficient for another infant to incorporate into its own memory.
    """

    entry_id: str
    feature_code: str
    embedding: list[float]  # Serialized numpy array
    value_vector: dict[str, float]
    path_signature: str
    frequency: int
    source_node_id: str
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "feature_code": self.feature_code,
            "embedding": self.embedding,
            "value_vector": self.value_vector,
            "path_signature": self.path_signature,
            "frequency": self.frequency,
            "source_node_id": self.source_node_id,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeEntry":
        return cls(**data)


class KnowledgeTransfer(InfantSkill):
    """
    Cross-infant knowledge sharing via cluster network.

    Workflow:
    1. Request: ask partner node for knowledge similar to my embedding
    2. Partner: searches local FeatureManager, returns top-K matching entries
    3. Import: validate and incorporate received entries into local memory

    Security: Only nodes with mutual_benefit > threshold are eligible as donors.
    """

    name = "knowledge_transfer"
    version = "1.0.0"
    description = "跨婴儿知识迁移 — 通过集群网络共享语义记忆"
    dependencies = []  # no hard deps; feature_manager injected at runtime
    parallelism_policy = ParallelismPolicy.SEQUENTIAL  # Sprint 2: async via event loop, not thread pool

    # Class constants for magic numbers
    REQUEST_PRIORITY = 0.7
    REQUEST_TTL = 10
    REQUEST_TIMEOUT = 30.0
    MAX_ENTRIES_DEFAULT = 50

    # Sprint 1: Async execution flag
    ASYNC_EXECUTION = True

    def __init__(
        self,
        feature_manager: FeatureManager | None = None,
        node_manager: NodeManager | None = None,
        hic: HIC | None = None,
        trust_threshold: float = 0.6,
        max_entries_per_transfer: int = MAX_ENTRIES_DEFAULT,
    ):
        self.fm = feature_manager
        self.node_manager = node_manager
        self.hic = hic
        self.trust_threshold = trust_threshold
        self.max_entries = max_entries_per_transfer
        self.enabled = True
        self._initialized = False
        self._last_execution: float = 0.0
        self._execution_count: int = 0
        self._pending_requests: dict[str, float] = {}  # request_id → timestamp
        self._request_timeout: float = self.REQUEST_TIMEOUT
        self._infant_ref: Any | None = None  # back-reference to SiliconInfant (outbox)
        self._embedding_dim: int | None = None  # from fm.embedding_dim (init)
        # Sprint 3: async callbacks: request_id → (imported, rejected) → None
        self._callbacks: dict[str, Callable[[int, list[str]], None]] = {}
        # LRU cache: key = (embedding_tuple, k) → list[KnowledgeEntry]
        self._similarity_cache: OrderedDict[
            tuple[tuple[float, ...], int], list[KnowledgeEntry]
        ] = OrderedDict()
        self._cache_max_size: int = 100

    # -------------------------------------------------------------------------
    # InfantSkill Protocol
    # -------------------------------------------------------------------------

    def initialize(self, context: SkillContext) -> None:
        """Initialize skill (dependencies injected separately)."""
        # Capture embedding_dim from FeatureManager for query validation
        if self.fm:
            dim = getattr(self.fm, 'embedding_dim', None)
            if isinstance(dim, int) and dim > 0:
                self._embedding_dim = dim
        self._initialized = True

    def can_activate(self, context: SkillContext) -> bool:
        """
        Activation conditions:
        - Enabled & initialized
        - FeatureManager available
        - Energy budget >= 3.0
        """
        if not self.enabled or not self._initialized:
            return False
        if self.fm is None:
            return False
        if context.energy_available < 3.0:
            return False
        return True

    def execute(self, params: dict[str, object]) -> dict[str, object]:
        """
        Execute one knowledge-transfer cycle.

        Currently handles:
        - Periodic cleanup of stale pending requests
        - Future: active pull from aligned partners

        Args:
            params: ignored

        Returns:
            {"imported": int, "energy_cost": float}
        """
        if not self._initialized:
            raise RuntimeError("KnowledgeTransfer not initialized")

        # Sprint 2: periodic cleanup of expired requests
        self._cleanup_stale_requests()

        self._last_execution = time.time()
        return {"imported": 0, "energy_cost": 3.0}

    def get_resource_usage(self) -> dict[str, float]:
        """Resource cost per execute() call."""
        return {"energy_cost": 3.0, "duration_s": 0.05, "memory_mb": 5.0}

    def shutdown(self) -> None:
        """Cleanup."""
        self.enabled = False
        self.fm = None
        self.node_manager = None

    def get_status(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "initialized": self._initialized,
            "execution_count": self._execution_count,
            "last_execution": self._last_execution,
        }

    # -------------------------------------------------------------------------
    # Async Execution (Sprint 1: Multi-Agent Parallelism)
    # -------------------------------------------------------------------------

    def can_execute_async(self) -> bool:
        """KnowledgeTransfer performs network RPC — benefits from async."""
        return True  # Sprint 1: enable parallel I/O

    async def execute_async(self, params: dict[str, object]) -> dict[str, object]:
        """
        Async execution: perform knowledge request/response cycle.

        Simulates network latency with asyncio.sleep to avoid blocking.
        Real implementation would await network RPC response.
        """
        if not self._initialized:
            raise RuntimeError("KnowledgeTransfer not initialized")

        # Periodically cleanup stale requests (quick, non-blocking)
        self._cleanup_stale_requests()

        # Sprint 1 demo: simulate network I/O for knowledge sync
        # In production, this would be: await self._sync_with_partners()
        await asyncio.sleep(0.05)  # Simulate 50ms network round-trip

        self._last_execution = time.time()
        return {"imported": 0, "energy_cost": 3.0, "async": True}


    # -------------------------------------------------------------------------
    # Internal Logic
    # -------------------------------------------------------------------------

    def is_eligible_donor(self, node_id: str) -> bool:
        """
        Check if a node is trustworthy to receive knowledge from.

        Policy: mutual_benefit > trust_threshold (reciprocity guarantee).
        """
        if self.hic is None:
            return False
        mb = self.hic.value_vector.get("mutual_benefit", 0.0)
        return mb >= self.trust_threshold

    def export_knowledge(
        self, query_embedding: np.ndarray, k: int = 10
    ) -> list[KnowledgeEntry]:
        """
        Export top-K locally stored knowledge entries most similar to query.

        Args:
            query_embedding: Vector to search for similar entries
            k: Maximum entries to return

        Returns:
            List of KnowledgeEntry objects (serializable)
        """
        if self.fm is None or not self.fm.traces:
            return []

        # MEDIUM: Validate query embedding dimension matches local configuration
        expected_dim = self._embedding_dim
        if expected_dim is not None and len(query_embedding) != expected_dim:
            return []

        # Compute similarities to all local traces
        # Sprint 3: LRU cache lookup
        cache_key = (tuple(query_embedding.tolist()), k)
        if cache_key in self._similarity_cache:
            self._similarity_cache.move_to_end(cache_key)
            return self._similarity_cache[cache_key]

        similarities = []
        for trace in self.fm.traces:
            if trace.embedding is None:
                continue
            sim = self._cosine_similarity(query_embedding, trace.embedding)
            similarities.append((sim, trace))

        # Sort by similarity desc, take top-k
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_k = similarities[: min(k, self.max_entries)]

        # Convert to KnowledgeEntry
        entries = []
        for sim, trace in top_k:
            entry = KnowledgeEntry(
                entry_id=str(uuid.uuid4()),
                feature_code=trace.feature_code,
                embedding=trace.embedding.tolist()
                if hasattr(trace.embedding, "tolist")
                else list(trace.embedding),
                value_vector=getattr(trace, "value_vector", {}),
                path_signature=getattr(trace, "path_signature", ""),
                frequency=getattr(trace, "frequency", 1),
                source_node_id=self._node_id_if_available(),
                tags=getattr(trace, "tags", []),
            )
            entries.append(entry)

        # Sprint 3: Store in LRU cache
        self._similarity_cache[cache_key] = entries
        if len(self._similarity_cache) > self._cache_max_size:
            self._similarity_cache.popitem(last=False)

        return entries

    def import_knowledge(self, entries: list[KnowledgeEntry]) -> tuple[int, list[str]]:
        """
        Incorporate received knowledge entries into local FeatureManager.

        Args:
            entries: List of KnowledgeEntry from remote node

        Returns:
            (imported_count, rejected_reasons)
        """
        # Sprint 3: Invalidate similarity cache on any import (knowledge base changed)
        self._similarity_cache.clear()

        if self.fm is None:
            return 0, ["feature_manager_unavailable"]

        imported = 0
        rejected = []

        for entry in entries:
            # Deduplication: skip if feature_code already exists locally
            if entry.feature_code in self.fm.traces_by_code:
                rejected.append(f"duplicate: {entry.feature_code}")
                continue

            # Validate value_vector sanity
            if not self._validate_value_vector(entry.value_vector):
                rejected.append(f"invalid_value_vector: {entry.feature_code}")
                continue

            # Reconstruct MemoryTrace and append
            try:
                embedding = np.array(entry.embedding, dtype=float)
                self.fm.append(
                    feature_code=entry.feature_code,
                    value_vector=entry.value_vector,
                    embedding=embedding,
                    path_signature=entry.path_signature,
                    frequency=entry.frequency,
                    tags=entry.tags,
                )
                imported += 1
            except Exception as e:
                rejected.append(f"import_error({e}): {entry.feature_code}")

        return imported, rejected

    def request_knowledge_from(
        self,
        partner_node_id: str,
        query_embedding: np.ndarray,
        k: int = 10,
        callback: Callable[[int, list[str]], None] | None = None,
    ) -> str:
        """
        Request knowledge from a specific partner node via cluster network.

        Args:
            partner_node_id: Target node ID
            query_embedding: Embedding to search with
            k: Number of entries to request
            callback: Optional async callback(imported: int, rejected: list[str])

        Returns:
            request_id: Unique ID for matching this request/response pair
        """
        if not self.enabled:
            return ""

        # Eligibility pre-check (optional — partner decides, but we can filter locally)
        if self.hic is None:
            return ""

        # Generate unique request ID for matching request/response
        request_id = str(uuid.uuid4())

        # Store pending request (will be fulfilled when response arrives)
        self._pending_requests[request_id] = time.time()

        # Store optional callback for async response
        if callback is not None:
            self._callbacks[request_id] = callback

        # Build request packet
        request_packet = CosmicPacket(
            timestamp=time.time(),
            source_id=self._node_id_if_available(),
            destination_id=partner_node_id,
            value_payload={
                "type": "knowledge_request",
                "request_id": request_id,
                "query_embedding": query_embedding.tolist(),
                "k": k,
                "requester_trust": self.hic.value_vector.get("mutual_benefit", 0.5),
            },
            priority=self.REQUEST_PRIORITY,
            ttl=self.REQUEST_TTL,
        )

        # Send via infant's outbox (injected reference set at runtime)
        if hasattr(self, "_infant_ref") and self._infant_ref:
            self._infant_ref.outbox.append(request_packet)
        else:
            # No infant reference — cannot send
            self._pending_requests.pop(request_id, None)
            self._callbacks.pop(request_id, None)
            return ""

        # Async: response will be handled via handle_knowledge_response()
        return request_id

    def handle_knowledge_response(
        self, request_id: str, entries: list[dict]
    ) -> tuple[int, list[str]]:
        """
        Handle incoming knowledge response packet.

        Args:
            request_id: Matches the original request
            entries: Serialized KnowledgeEntry dicts

        Returns:
            (imported_count, rejected_reasons)
        """
        # Check if we're still waiting for this response
        if request_id not in self._pending_requests:
            return 0, ["unknown_request_id"]

        # Remove from pending
        self._pending_requests.pop(request_id, None)

        # Deserialize entries
        knowledge_entries = []
        for entry_dict in entries:
            try:
                entry = KnowledgeEntry.from_dict(entry_dict)
                knowledge_entries.append(entry)
            except Exception as e:
                return 0, [f"deserialization_error: {e}"]

        # Import using existing logic
        imported, rejected = self.import_knowledge(knowledge_entries)

        # Sprint 3: Trigger async callback if registered
        callback = self._callbacks.pop(request_id, None)
        if callback is not None:
            try:
                callback(imported, rejected)
            except Exception:
                # Callback errors should not crash the handler
                pass

        return imported, rejected

    def _cleanup_stale_requests(self) -> None:
        """Remove pending requests older than timeout."""
        now = time.time()
        stale = [
            rid
            for rid, ts in self._pending_requests.items()
            if now - ts > self._request_timeout
        ]
        for rid in stale:
            self._pending_requests.pop(rid, None)
            self._callbacks.pop(rid, None)  # also cleanup orphaned callbacks

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            a = a[: min(len(a), len(b))]
            b = b[: min(len(a), len(b))]
        norm_prod = float(np.linalg.norm(a) * np.linalg.norm(b))
        if norm_prod < 1e-10:
            return 0.0
        return float(np.dot(a, b) / norm_prod)

    def _validate_value_vector(self, vv: dict) -> bool:
        """Basic sanity check for value vector."""
        if not isinstance(vv, dict):
            return False
        for k, v in vv.items():
            if not isinstance(k, str):
                return False
            if not isinstance(v, (int, float)):
                return False
            if v < -10.0 or v > 10.0:
                return False
        return True

    def _node_id_if_available(self) -> str:
        """Get local node ID from _infant_ref or node_manager.

        Priority: _infant_ref.infant_id > node_manager attribute > 'local' fallback.
        """
        # Check infant back-reference first (most direct)
        if self._infant_ref is not None:
            infant_id = getattr(self._infant_ref, "infant_id", None)
            if infant_id:
                return str(infant_id)
        # Fall back to node_manager
        if self.node_manager is not None:
            node_id = getattr(self.node_manager, "local_node_id", None)
            if node_id:
                return str(node_id)
        return "local"
