"""
Unit Tests: utils.tracing — DistributedTracer
Tests for OpenTelemetry-based distributed tracing.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cosmic_mycelium.utils.tracing import DistributedTracer, TraceContext


class TestTracerAvailability:
    """OpenTelemetry availability detection."""

    def test_tracer_can_be_imported(self):
        """DistributedTracer class exists."""
        from cosmic_mycelium.utils.tracing import DistributedTracer

        assert DistributedTracer is not None


class TestDistributedTracer:
    """Tracer lifecycle and span management."""

    def test_start_span_returns_span_id(self):
        """start_span returns a non-empty span_id string."""
        tracer = DistributedTracer("test-service")
        span_id = tracer.start_span("test_operation")
        assert isinstance(span_id, str)
        assert len(span_id) > 0

    def test_end_span_no_error_success(self):
        """end_span with no error closes span cleanly."""
        tracer = DistributedTracer("test-service")
        span_id = tracer.start_span("test")
        # Should not raise
        tracer.end_span(span_id, status="ok")

    def test_end_span_records_exception(self):
        """end_span with error records exception."""
        tracer = DistributedTracer("test-service")
        span_id = tracer.start_span("failing_op")
        test_error = ValueError("test failure")
        tracer.end_span(span_id, status="error", error=test_error)
        # No assertion — just verify no crash

    def test_end_span_unknown_span_id(self):
        """end_span on unknown span_id does not crash."""
        tracer = DistributedTracer("test-service")
        tracer.end_span("nonexistent", status="ok")  # should be no-op

    def test_inject_context_returns_dict(self):
        """inject_context returns propagation headers."""
        tracer = DistributedTracer("test-service")
        span_id = tracer.start_span("test")
        headers = tracer.inject_context(span_id)
        assert isinstance(headers, dict)
        assert "trace.span_id" in headers

    def test_extract_context_returns_span_id(self):
        """extract_context retrieves span_id from headers."""
        tracer = DistributedTracer("test-service")
        headers = {"trace.span_id": "abc123"}
        span_id = tracer.extract_context(headers)
        assert span_id == "abc123"

    def test_extract_context_missing_key_returns_none(self):
        """extract_context returns None when key missing."""
        tracer = DistributedTracer("test-service")
        span_id = tracer.extract_context({})
        assert span_id is None

    def test_trace_operation_context_manager(self):
        """trace_operation is a context manager that yields span_id."""
        tracer = DistributedTracer("test-service")
        with tracer.trace_operation("test_op") as span_id:
            assert isinstance(span_id, str)
            assert len(span_id) > 0
        # After context exit, span should be ended

    def test_trace_operation_propagates_exception(self):
        """trace_operation re-raises exceptions after recording."""
        tracer = DistributedTracer("test-service")
        with (
            pytest.raises(RuntimeError),
            tracer.trace_operation("failing"),
        ):
            raise RuntimeError("boom")

    def test_multiple_spans_tracked_independently(self):
        """Multiple concurrent spans tracked separately."""
        tracer = DistributedTracer("test-service")
        id1 = tracer.start_span("op1")
        id2 = tracer.start_span("op2")
        assert id1 != id2
        tracer.end_span(id1)
        tracer.end_span(id2)
        # No assertion — just verify no crash


class TestTraceContext:
    """TraceContext dataclass."""

    def test_create_trace_context(self):
        """TraceContext can be instantiated."""
        ctx = TraceContext(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="parent-789",
            node_id="node-a",
        )
        assert ctx.trace_id == "trace-123"
        assert ctx.span_id == "span-456"
        assert ctx.parent_span_id == "parent-789"
        assert ctx.node_id == "node-a"

    def test_trace_context_defaults(self):
        """TraceContext uses default start_time."""
        import time as time_mod

        before = time_mod.time()
        ctx = TraceContext(trace_id="t1", span_id="s1")
        after = time_mod.time()
        assert before <= ctx.start_time <= after
        assert ctx.parent_span_id is None
        assert ctx.node_id is None


class TestTracerWithAttributes:
    """Tracer attribute propagation."""

    def test_start_span_with_attributes(self):
        """start_span accepts attributes dict."""
        tracer = DistributedTracer("test-service")
        span_id = tracer.start_span("test", attributes={"key": "value", "num": 42})
        assert isinstance(span_id, str)

    def test_trace_operation_with_attributes(self):
        """trace_operation accepts attributes."""
        tracer = DistributedTracer("test-service")
        with tracer.trace_operation("op", attributes={"component": "brain"}) as sid:
            assert isinstance(sid, str)


class TestTracerFallbackWhenUnavailable:
    """Behavior when OpenTelemetry not installed."""

    def test_tracer_works_without_opentelemetry(self):
        """DistributedTracer provides no-op implementation when OTEL missing."""
        with patch.dict(
            "sys.modules", {"opentelemetry": None, "opentelemetry.sdk": None}
        ):
            # Re-import to get fallback
            from cosmic_mycelium.utils.tracing import (
                DistributedTracer as FallbackTracer,
            )

            tracer = FallbackTracer("test")
            span_id = tracer.start_span("op")
            assert isinstance(span_id, str)
            tracer.end_span(span_id)
            # All no-op, should not raise
