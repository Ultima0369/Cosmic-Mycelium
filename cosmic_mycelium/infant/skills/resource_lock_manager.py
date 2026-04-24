"""
Resource Lock Manager — Fine-grained locks for shared infant state (Sprint 2).

Provides per-resource reentrant locks to protect concurrent access to
shared infant subsystems during parallel skill execution.

Lock acquisition order (global order for deadlock prevention):
  1. feature_manager
  2. memory
  3. brain
  4. hic

All skills MUST acquire multiple locks in this order if needed.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from enum import Enum
from typing import ClassVar


class _Resource(Enum):
    """Named shared resources requiring synchronization."""
    FEATURE_MANAGER = "feature_manager"
    MEMORY = "memory"
    BRAIN = "brain"
    HIC = "hic"
    KNOWLEDGE_STORE = "knowledge_store"
    COLLECTIVE_INTELLIGENCE = "collective_intelligence"


class ResourceLockManager:
    """
    Centralized lock manager for shared infant state.

    Usage:
        # Single lock
        with ResourceLockManager.lock("feature_manager"):
            fm.append(...)

        # Multiple locks (auto-ordered to prevent deadlock)
        with ResourceLockManager.lock_multiple(["memory", "feature_manager"]):
            # Both resources held; locks acquired in global order
            ...
    """

    # Global lock acquisition order (alphabetical by resource name)
    _LOCK_ORDER: ClassVar[list[str]] = [
        "brain",
        "collective_intelligence",
        "feature_manager",
        "hic",
        "knowledge_store",
        "memory",
    ]

    # Per-resource reentrant locks (one per resource)
    _locks: ClassVar[dict[str, threading.RLock]] = {
        "brain": threading.RLock(),
        "collective_intelligence": threading.RLock(),
        "feature_manager": threading.RLock(),
        "hic": threading.RLock(),
        "knowledge_store": threading.RLock(),
        "memory": threading.RLock(),
    }

    @classmethod
    def get_lock(cls, resource_name: str) -> threading.RLock:
        """
        Get the RLock for a named resource.

        Args:
            resource_name: One of "feature_manager", "memory", "brain", "hic"

        Returns:
            The reentrant lock for that resource.
        """
        if resource_name not in cls._locks:
            raise KeyError(f"Unknown resource: {resource_name}")
        return cls._locks[resource_name]

    @classmethod
    @contextmanager
    def lock(cls, resource_name: str):
        """
        Acquire a single resource lock (context manager).

        Example:
            with ResourceLockManager.lock("feature_manager"):
                fm.append(...)  # safe
        """
        lock = cls.get_lock(resource_name)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    @classmethod
    @contextmanager
    def lock_multiple(cls, resource_names: list[str]):
        """
        Acquire multiple resource locks in global order to prevent deadlock.

        Args:
            resource_names: List of resource names. Order is ignored; locks
                           are always acquired in the predefined global order.

        Example:
            with ResourceLockManager.lock_multiple(["memory", "feature_manager"]):
                # Both memory and feature_manager are locked
                ...
        """
        # Deduplicate and sort by global order
        unique_names = sorted(set(resource_names), key=lambda name: cls._LOCK_ORDER.index(name))

        # Acquire all locks in order
        locks = [cls._locks[name] for name in unique_names]
        for lock in locks:
            lock.acquire()
        try:
            yield
        finally:
            # Release in reverse order (good practice, though RLock doesn't require it)
            for lock in reversed(locks):
                lock.release()

    @classmethod
    def is_locked(cls, resource_name: str) -> bool:
        """Check if a resource lock is currently held (by any thread)."""
        lock = cls.get_lock(resource_name)
        return lock.locked()
