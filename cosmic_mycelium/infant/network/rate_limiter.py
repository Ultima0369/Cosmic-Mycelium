"""
Rate Limiter — Token Bucket 实现

用于防止消息洪泛攻击 (SEC-004)。
每个 source_id 独立限速: 默认 10 msg/s 突发允许 20。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket rate limiter."""

    rate: float = 10.0  # tokens per second
    capacity: float = 20.0  # max tokens (burst)
    tokens: float = field(default=capacity)
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Consume tokens from bucket.

        Returns:
            True if enough tokens, False if rate limit exceeded.
        """
        now = time.time()
        # Refill: linear growth
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def is_allowed(self) -> bool:
        """Convenience wrapper for single-token consumption."""
        return self.consume(1.0)


class RateLimiter:
    """
    Per-source rate limiter registry.

    Maintains a TokenBucket for each source_id, with automatic cleanup
    of idle buckets to prevent memory leaks.
    """

    def __init__(self, default_rate: float = 10.0, default_capacity: float = 20.0):
        self._buckets: dict[str, TokenBucket] = {}
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._idle_timeout = 3600.0  # 1 hour idle → evict
        self._last_access: dict[str, float] = {}

    def check(self, source_id: str) -> bool:
        """
        Check if a message from source_id is allowed under rate limit.

        Returns:
            True if allowed, False if rate limit exceeded.
        """
        now = time.time()

        # Evict idle buckets
        idle_sources = [
            src for src, last in self._last_access.items() if now - last > self._idle_timeout
        ]
        for src in idle_sources:
            del self._buckets[src]
            del self._last_access[src]

        # Get or create bucket for this source
        if source_id not in self._buckets:
            self._buckets[source_id] = TokenBucket(
                rate=self.default_rate,
                capacity=self.default_capacity,
            )
        self._last_access[source_id] = now

        bucket = self._buckets[source_id]
        allowed = bucket.is_allowed()
        if not allowed:
            # Could log or metric here
            pass
        return allowed

    def get_stats(self) -> dict[str, int]:
        """Return current bucket counts (for monitoring)."""
        return {
            "active_sources": len(self._buckets),
            "total_denied": sum(1 for b in self._buckets.values() if not b.is_allowed()),
        }
