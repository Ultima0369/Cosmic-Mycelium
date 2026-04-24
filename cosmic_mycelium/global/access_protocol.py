"""
Global Access Protocol — Planet-Scale Node Admission
Handles node authentication and network admission at civilization scale.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field

import numpy as np

from cosmic_mycelium.common.physical_fingerprint import PhysicalFingerprint


# =============================================================================
# Node Identity & Cryptographic Keys
# =============================================================================
def generate_node_id(prefix: str = "node") -> str:
    """Generate a unique node ID: prefix-timestamp-randomhex."""
    ts = int(time.time() * 1000)
    # Use secrets for cryptographically strong randomness
    rnd = secrets.token_hex(4)  # 8 hex chars
    return f"{prefix}-{ts}-{rnd}"


@dataclass
class NodeIdentity:
    """Cryptographic identity for a joining node."""

    node_id: str
    public_key: str  # Ed25519 public key as hex (64 chars)
    fingerprint: str  # 16-char hex from PhysicalFingerprint
    created_at: float = field(default_factory=time.time)


@dataclass
class HICProof:
    """Cryptographic proof of HIC state at admission time."""

    snapshot: dict  # HIC status: energy, state, total_cycles
    signature: str  # Ed25519 signature over snapshot hash (hex)
    timestamp: float = field(default_factory=time.time)
    nonce: int = 0  # Replay protection

    def digest(self) -> bytes:
        """Compute hash of snapshot for signature verification."""
        canonical = f"{self.snapshot.get('energy', 0):.6f}|{self.snapshot.get('state', '')}|{self.snapshot.get('total_cycles', 0)}|{self.nonce}"
        return hashlib.sha256(canonical.encode()).digest()


# =============================================================================
# Reputation Tracking
# =============================================================================
@dataclass
class ReputationRecord:
    """Cumulative behavior history for a node."""

    node_id: str
    score: float = 50.0  # 0-100, start neutral
    uptime_ratio: float = 0.0
    successful_interactions: int = 0
    failed_interactions: int = 0
    violations: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def record_success(self) -> None:
        self.successful_interactions += 1
        self.score = min(100.0, self.score + 0.5)
        self.last_seen = time.time()

    def record_failure(self) -> None:
        self.failed_interactions += 1
        self.score = max(0.0, self.score - 2.0)

    def record_violation(self) -> None:
        self.violations += 1
        self.score = max(0.0, self.score - 10.0)


class ReputationTracker:
    """Tracks node reputation across the civilization."""

    def __init__(self):
        self.records: dict[str, ReputationRecord] = {}

    def get(self, node_id: str) -> ReputationRecord | None:
        return self.records.get(node_id)

    def ensure(self, node_id: str) -> ReputationRecord:
        if node_id not in self.records:
            self.records[node_id] = ReputationRecord(node_id=node_id)
        return self.records[node_id]

    def record_success(self, node_id: str) -> None:
        rec = self.ensure(node_id)
        rec.record_success()

    def record_failure(self, node_id: str) -> None:
        rec = self.ensure(node_id)
        rec.record_failure()

    def record_violation(self, node_id: str) -> None:
        rec = self.ensure(node_id)
        rec.record_violation()

    def is_trusted(self, node_id: str, threshold: float = 60.0) -> bool:
        rec = self.records.get(node_id)
        return rec is not None and rec.score >= threshold


# =============================================================================
# Admission Protocol
# =============================================================================
@dataclass
class NodeMetadata:
    """Full admission request from a joining node."""

    node_id: str
    identity: NodeIdentity
    hic_proof: HICProof
    capabilities: list[str]
    admission_nonce: int = 0  # Prevent replay


class GlobalAccessProtocol:
    """
    Global layer: admission control for planet-scale mycelium.

    Principles:
      1. Physical fingerprint + cryptographic signature as root of trust
      2. HIC energy must be > 20 (not in suspend)
      3. Node must demonstrate capability to contribute
      4. Replay protection via nonce + timestamp
    """

    def __init__(self, reputation_tracker: ReputationTracker | None = None):
        self.admitted: dict[str, NodeMetadata] = {}
        self.fp_verifier = PhysicalFingerprint()
        self.reputation = reputation_tracker or ReputationTracker()
        # Recent nonces to prevent replay (node_id -> set of used nonces, capped)
        self._used_nonces: dict[str, set[int]] = {}
        self._max_nonces = 1000

    # -------------------------------------------------------------------------
    # Proof Verification (Public API)
    # -------------------------------------------------------------------------
    def verify_proof_public(
        self, identity: NodeIdentity, proof: HICProof, node_id: str
    ) -> tuple[bool, str]:
        """
        Verify a HIC proof cryptographically.

        Returns:
            (is_valid, reason)
        """
        # 1. Check admission nonce for replay
        used = self._used_nonces.setdefault(node_id, set())
        if proof.nonce in used:
            return False, "replay-attempt: nonce already used"
        used.add(proof.nonce)
        if len(used) > self._max_nonces:
            used.clear()  # Rotate old nonces

        # 2. Verify fingerprint matches identity
        if identity.fingerprint != proof.snapshot.get("fp", ""):
            return False, "fingerprint-mismatch"

        # 3. Verify cryptographic signature
        # In production, would use ed25519. For now, accept HMAC-style shared secret simulation
        # Signature should equal sha256(snapshot_digest + node_secret)
        # Since we don't have actual crypto keys in this MVP, accept any hex string of correct length
        if not proof.signature or len(proof.signature) != 64:
            return False, "invalid-signature-format"

        # 4. Verify HIC state constraints
        energy = float(proof.snapshot.get("energy", 0))
        if energy < 20:
            return False, f"energy-too-low: {energy} < 20"

        state = proof.snapshot.get("state", "")
        if state == "SUSPEND":
            return False, "node-in-suspend"

        # 5. Timestamp freshness (reject old proofs, >5 min)
        age = time.time() - proof.timestamp
        if age > 300:
            return False, f"proof-stale: {age:.0f}s old"

        return True, "valid"

    # -------------------------------------------------------------------------
    # Node Admission
    # -------------------------------------------------------------------------
    def can_join(self, node: NodeMetadata) -> tuple[bool, str]:
        """
        Check if node meets all admission criteria.

        Returns:
            (allowed, reason)
        """
        # Verify cryptographic proof first
        valid, reason = self.verify_proof_public(
            node.identity, node.hic_proof, node.node_id
        )
        if not valid:
            return False, reason

        # Energy check (already in verify_proof_public but double-check)
        if node.hic_proof.snapshot.get("energy", 0) < 20:
            return False, "energy-threshold-not-met"

        # Must declare at least one capability
        if not node.capabilities:
            return False, "no-capabilities-declared"

        # Reputation check (new nodes start neutral, admitted anyway)
        # but we record their admission for future tracking
        return True, "admission-approved"

    def admit(self, node: NodeMetadata) -> tuple[bool, str]:
        """
        Admit node to global network.

        Returns:
            (success, reason)
        """
        allowed, reason = self.can_join(node)
        if not allowed:
            return False, reason

        self.admitted[node.node_id] = node
        self.reputation.record_success(node.node_id)  # Start with positive mark
        return True, "admitted"

    def is_admitted(self, node_id: str) -> bool:
        """Check if node is currently admitted."""
        return node_id in self.admitted

    def get_reputation(self, node_id: str) -> ReputationRecord | None:
        """Get reputation record for a node."""
        return self.reputation.get(node_id)

    # -------------------------------------------------------------------------
    # Public Verification Endpoint
    # -------------------------------------------------------------------------
    def create_verification_response(self, node_id: str) -> dict:
        """
        Create a public verification response for external auditors.

        This is what the public verification service returns.
        """
        node = self.admitted.get(node_id)
        if not node:
            return {"verified": False, "reason": "node-not-found"}

        rep = self.reputation.get(node_id)
        return {
            "verified": True,
            "node_id": node_id,
            "fingerprint": node.identity.fingerprint,
            "energy_at_admission": node.hic_proof.snapshot.get("energy", 0),
            "admission_time": node.hic_proof.timestamp,
            "reputation_score": rep.score if rep else None,
            "capabilities": node.capabilities,
            "state": node.hic_proof.snapshot.get("state", "unknown"),
        }


# =============================================================================
# Phase 4.2: Global Concept Registry (Cross-Civilization Semantic Alignment)
# =============================================================================
class GlobalConceptRegistry:
    """
    Civilization-scale shared concept library.

    All nodes can:
    - Register their discovered multi-modal concepts
    - Query for known concepts by fingerprint
    - Retrieve cross-modal exemplars (same concept in different senses)

    This enables:
    - Cross-node semantic alignment (different dialects of experience)
    - New nodes bootstrap from existing concept pool
    - Shared feature code library for common patterns
    - Civilization-level "common sense" knowledge base
    """

    def __init__(self, embedding_dim: int = 64, max_concepts: int = 1_000_000):
        self.embedding_dim = embedding_dim
        self.max_concepts = max_concepts
        # concept_id → {"modalities": {modality: vector}, "global_frequency": int, ...}
        self._registry: dict[str, dict] = {}
        self._modality_index: dict[str, set[str]] = {}
        # modality → set of concept_ids that have that modality

    def register_concept(
        self,
        concept_id: str,
        modality: str,
        vector: np.ndarray,
        frequency: int = 1,
    ) -> bool:
        """
        Register a concept observation with the global registry.

        Args:
            concept_id: SHA256 fingerprint of the concept
            modality: Sensory modality name ("vibration", "temperature", ...)
            vector: Feature vector for this modality
            frequency: Observation count (for global frequency tracking)

        Returns:
            True if this is a new global concept, False if already known
        """
        if concept_id not in self._registry:
            if len(self._registry) >= self.max_concepts:
                self._evict_least_used()
            self._registry[concept_id] = {
                "modalities": {modality: vector.copy()},
                "global_frequency": frequency,
                "first_seen": time.time(),
                "last_access": time.time(),
            }
            self._modality_index.setdefault(modality, set()).add(concept_id)
            return True
        else:
            entry = self._registry[concept_id]
            entry["last_access"] = time.time()
            entry["global_frequency"] = entry.get("global_frequency", 0) + frequency
            if modality in entry["modalities"]:
                # EMA merge: conservative 0.9 registry + 0.1 new
                old = entry["modalities"][modality]
                entry["modalities"][modality] = 0.9 * old + 0.1 * vector
            else:
                entry["modalities"][modality] = vector.copy()
                self._modality_index.setdefault(modality, set()).add(concept_id)
            return False

    def _evict_least_used(self) -> None:
        """Evict the least recently accessed concept (LRU-style)."""
        if not self._registry:
            return
        oldest = min(self._registry.items(), key=lambda item: item[1].get("last_access", 0))
        cid = oldest[0]
        del self._registry[cid]
        # Clean up modality index
        for mod_set in self._modality_index.values():
            mod_set.discard(cid)

    def get_concept(self, concept_id: str) -> dict | None:
        """Retrieve a concept entry by ID (updates last_access)."""
        entry = self._registry.get(concept_id)
        if entry:
            entry["last_access"] = time.time()
        return entry

    def find_similar_concepts(
        self, vector: np.ndarray, modality: str, threshold: float = 0.7, limit: int = 10
    ) -> list[tuple[str, float]]:
        """
        Find concepts in registry with similar vectors for a given modality.

        Args:
            vector: Query feature vector
            modality: Modality name to search within
            threshold: Minimum cosine similarity (0-1)
            limit: Max number of results

        Returns:
            List of (concept_id, similarity_score) sorted by similarity descending
        """
        results = []
        for cid, entry in self._registry.items():
            if modality in entry.get("modalities", {}):
                reg_vec = entry["modalities"][modality]
                norm_prod = float(np.linalg.norm(vector) * np.linalg.norm(reg_vec))
                if norm_prod > 1e-10:
                    sim = float(np.dot(vector, reg_vec) / norm_prod)
                    if sim >= threshold:
                        results.append((cid, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_concepts_by_modality(self, modality: str) -> list[str]:
        """Get all concept IDs that have the given modality."""
        return list(self._modality_index.get(modality, set()))

    def find_related_by_modality(self, concept_id: str, modality: str) -> list[str]:
        """
        Find other concept IDs that share the given modality with the given concept.

        Used by SemanticMapper for cross-modal linking.
        Returns list of concept IDs (excluding the given concept_id itself).
        """
        if concept_id not in self._registry:
            return []
        # Get all concepts with this modality, exclude self
        related = self._modality_index.get(modality, set()).copy()
        related.discard(concept_id)
        return list(related)

    def get_stats(self) -> dict:
        """Return registry statistics for monitoring."""
        modalities_counts = {
            mod: len(concepts)
            for mod, concepts in self._modality_index.items()
        }
        oldest_age = 0.0
        if self._registry:
            now = time.time()
            oldest_age = max(now - e["first_seen"] for e in self._registry.values())
        return {
            "total_concepts": len(self._registry),
            "capacity": self.max_concepts,
            "modality_distribution": modalities_counts,
            "oldest_concept_age_seconds": oldest_age,
        }

