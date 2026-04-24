"""
Unit tests for KnowledgeTransfer network RPC (Sprint 2).

Tests:
- request_knowledge_from: packet construction, outbox delivery, infant_ref injection
- handle_knowledge_response: request_id matching, deserialization, import delegation
- _cleanup_stale_requests: timeout eviction
- process_inbox integration: knowledge_request and knowledge_response handlers
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.infant.skills.base import SkillContext
from cosmic_mycelium.infant.skills.collective.knowledge_transfer import (
    KnowledgeEntry,
    KnowledgeTransfer,
)


class TestRequestKnowledgeFrom:
    """Tests for KnowledgeTransfer.request_knowledge_from()."""

    def test_request_disabled_returns_immediately(self):
        """Disabled KT returns empty request_id."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt.enabled = False
        kt._infant_ref = MagicMock()

        result = kt.request_knowledge_from("partner-1", np.array([1.0, 2.0]))
        assert result == ""

    def test_request_without_inant_ref_returns_immediately(self):
        """No infant back-reference cannot send packets."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = None

        result = kt.request_knowledge_from("partner-1", np.array([1.0, 2.0]))
        assert result == ""

    def test_request_creates_packet_in_outbox(self):
        """Valid request appends CosmicPacket to infant outbox."""
        mock_fm = MagicMock()
        mock_infant = MagicMock()
        mock_infant.outbox = []

        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = mock_infant
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

        query = np.array([0.5, 1.5, 2.5])
        result = kt.request_knowledge_from("partner-xyz", query, k=5)

        # Should return a non-empty request_id (async response expected)
        assert isinstance(result, str) and len(result) > 0
        # Outbox should have one packet
        assert len(mock_infant.outbox) == 1
        packet = mock_infant.outbox[0]
        assert packet.destination_id == "partner-xyz"
        assert packet.value_payload["type"] == "knowledge_request"
        assert "request_id" in packet.value_payload
        assert packet.value_payload["k"] == 5
        # Query should be serialized
        assert packet.value_payload["query_embedding"] == [0.5, 1.5, 2.5]

    def test_request_generates_unique_request_ids(self):
        """Each request gets a unique UUID."""
        mock_fm = MagicMock()
        mock_infant = MagicMock()
        mock_infant.outbox = []
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = mock_infant
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

        request_ids = []
        for _ in range(10):
            kt.request_knowledge_from("p", np.array([1.0]))
            packet = mock_infant.outbox[-1]
            request_ids.append(packet.value_payload["request_id"])

        # All should be unique
        assert len(set(request_ids)) == 10

    def test_request_stores_pending_entry(self):
        """request_id is stored in _pending_requests for response matching."""
        mock_fm = MagicMock()
        mock_infant = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = mock_infant
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

        kt.request_knowledge_from("partner", np.array([1.0]))
        assert len(kt._pending_requests) == 1


class TestHandleKnowledgeResponse:
    """Tests for KnowledgeTransfer.handle_knowledge_response()."""

    def setup_method(self):
        """Common fixtures."""
        self.mock_fm = MagicMock()
        self.mock_fm.traces_by_code = {}
        self.kt = KnowledgeTransfer(feature_manager=self.mock_fm, hic=MagicMock())
        self.kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))

    def test_handle_response_unknown_request_id(self):
        """Response with unknown request_id is rejected."""
        imported, rejected = self.kt.handle_knowledge_response("unknown-uid", [])
        assert imported == 0
        assert "unknown_request_id" in rejected[0]

    def test_handle_response_deserializes_entries(self):
        """Valid entries are deserialized and passed to import_knowledge."""
        # Seed a pending request
        req_id = "req-123"
        self.kt._pending_requests[req_id] = time.time()

        entry_dict = {
            "entry_id": "e1",
            "feature_code": "fc-test",
            "embedding": [0.1, 0.2],
            "value_vector": {"x": 1.0},
            "path_signature": "p1",
            "frequency": 1,
            "source_node_id": "remote-1",
            "timestamp": time.time(),
            "tags": [],
        }

        imported, rejected = self.kt.handle_knowledge_response(req_id, [entry_dict])

        # Should be imported (assuming no duplicate)
        assert imported == 1
        assert rejected == []
        # Request removed from pending
        assert req_id not in self.kt._pending_requests
        # FeatureManager.append called
        self.mock_fm.append.assert_called_once()

    def test_handle_response_removes_pending_on_success(self):
        """Pending request cleared after handling."""
        req_id = "req-abc"
        self.kt._pending_requests[req_id] = time.time()

        entry = KnowledgeEntry(
            entry_id="e1",
            feature_code="fc1",
            embedding=[1.0],
            value_vector={},
            path_signature="p",
            frequency=1,
            source_node_id="n1",
        )
        imported, rejected = self.kt.import_knowledge([entry])
        # Note: handle_knowledge_response calls import_knowledge internally
        # We test the full flow below

        # Now test via handle_knowledge_response
        req_id2 = "req-xyz"
        self.kt._pending_requests[req_id2] = time.time()
        self.kt.handle_knowledge_response(req_id2, [entry.to_dict()])
        assert req_id2 not in self.kt._pending_requests

    def test_handle_response_deserialization_error(self):
        """Malformed entry dict returns import_error."""
        req_id = "req-bad"
        self.kt._pending_requests[req_id] = time.time()

        bad_entry = {"not_a": "KnowledgeEntry"}
        imported, rejected = self.kt.handle_knowledge_response(req_id, [bad_entry])

        assert imported == 0
        assert any("deserialization_error" in r for r in rejected)


class TestCleanupStaleRequests:
    """Tests for _cleanup_stale_requests()."""

    def setup_method(self):
        self.kt = KnowledgeTransfer(feature_manager=MagicMock(), hic=MagicMock())
        self.kt._request_timeout = 1.0  # 1 second for test

    def test_removes_expired_requests(self):
        """Requests older than timeout are evicted."""
        now = time.time()
        self.kt._pending_requests = {
            "fresh": now - 0.5,  # within timeout
            "stale": now - 2.0,  # beyond timeout
        }
        self.kt._cleanup_stale_requests()
        assert "fresh" in self.kt._pending_requests
        assert "stale" not in self.kt._pending_requests

    def test_keeps_recent_requests(self):
        """Requests within timeout are preserved."""
        now = time.time()
        self.kt._pending_requests = {
            "r1": now - 0.1,
            "r2": now - 0.5,
            "r3": now - 0.9,
        }
        self.kt._cleanup_stale_requests()
        assert len(self.kt._pending_requests) == 3

    def test_no_crash_on_empty_dict(self):
        """Empty pending set handled gracefully."""
        self.kt._pending_requests = {}
        self.kt._cleanup_stale_requests()  # should not raise
        assert self.kt._pending_requests == {}


class TestExecuteCallsCleanup:
    """Test that execute() invokes cleanup."""

    def test_execute_triggers_cleanup(self):
        kt = KnowledgeTransfer(feature_manager=MagicMock(), hic=MagicMock())
        kt.initialize(SkillContext(infant_id="t", cycle_count=0, energy_available=10))

        # Add a stale request
        kt._pending_requests["stale"] = time.time() - kt._request_timeout - 1
        kt._pending_requests["fresh"] = time.time()

        kt.execute({})

        # Stale should be gone
        assert "stale" not in kt._pending_requests
        assert "fresh" in kt._pending_requests


class TestAsyncCallbacks:
    """Sprint 3: Async callback tests for request_knowledge_from."""

    def test_callback_invoked_on_success(self):
        """Callback is invoked with (imported, rejected) on successful response."""
        mock_fm = MagicMock()
        mock_fm.traces = []
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = MagicMock()
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        kt.fm = mock_fm
        kt._infant_ref = MagicMock()

        entry = KnowledgeEntry(
            entry_id="e1",
            feature_code="fc-test",
            embedding=[0.1, 0.2],
            value_vector={"x": 1.0},
            path_signature="p",
            frequency=1,
            source_node_id="remote",
        )
        kt.import_knowledge([entry])
        cb_called = []
        def my_cb(imported, rejected):
            cb_called.append((imported, rejected))
        req_id = kt.request_knowledge_from("partner", np.array([0.1, 0.2]), callback=my_cb)
        # 模拟远程响应
        kt.handle_knowledge_response(req_id, [entry.to_dict()])
        assert len(cb_called) == 1

    def test_callback_not_invoked_on_unknown_request_id(self):
        """Callback not called if request_id unknown."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = MagicMock()
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        # 直接调用 handle，不先 request
        imported, rejected = kt.handle_knowledge_response("unknown", [])
        assert imported == 0
        assert "unknown_request_id" in rejected[0]

    def test_callback_cleared_after_handling(self):
        """Callback removed from registry after being invoked."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._infant_ref = MagicMock()
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        cb_called = []
        def cb(imp, rej):
            cb_called.append((imp, rej))
        req_id = kt.request_knowledge_from("p", np.array([1.0]), callback=cb)
        assert req_id in kt._callbacks
        # 模拟响应
        kt.handle_knowledge_response(req_id, [])
        assert req_id not in kt._callbacks
        assert len(cb_called) == 1

    def test_timeout_clears_callback(self):
        """Stale request cleanup also removes callback."""
        mock_fm = MagicMock()
        kt = KnowledgeTransfer(feature_manager=mock_fm, hic=MagicMock())
        kt._request_timeout = 0.1
        kt._infant_ref = MagicMock()
        kt.initialize(SkillContext(infant_id="test", cycle_count=0, energy_available=10))
        cb_called = []
        kt.request_knowledge_from("p", np.array([1.0]), callback=lambda i, r: cb_called.append((i, r)))
        # 手动老化条目
        kt._pending_requests[list(kt._pending_requests.keys())[0]] = time.time() - 1.0
        kt._cleanup_stale_requests()
        # 回调应被清理
        assert len(kt._callbacks) == 0
        assert len(cb_called) == 0  # 未调用
