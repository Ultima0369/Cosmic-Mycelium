"""
Distributed Tracing — OpenTelemetry Instrumentation
Traces requests and events across infant nodes and cluster layers.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


@dataclass
class TraceContext:
    """Context for a single trace across nodes."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    node_id: str | None = None
    start_time: float = field(default_factory=time.time)


class DistributedTracer:
    """
    Distributed tracing for cross-node operations.

    Instruments:
    - Breath cycles
    - Packet routing
    - Cluster consensus
    - SuperBrain global workspace updates
    """

    def __init__(self, service_name: str = "cosmic-infant"):
        if not OPENTELEMETRY_AVAILABLE:
            return

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        # Console exporter for local debugging
        console = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(console))

        # OTLP exporter for production (configured via OTEL_EXPORTER_OTLP_ENDPOINT)
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            otlp = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp))

        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(service_name)
        self._active_spans: dict[str, trace.Span] = {}

    def start_span(
        self,
        name: str,
        parent_id: str | None = None,
        attributes: dict | None = None,
    ) -> str:
        """Start a new trace span. Returns span_id."""
        if not OPENTELEMETRY_AVAILABLE:
            return str(uuid.uuid4())[:16]

        # Parent context propagation: attach parent_id as span attribute
        span_attrs: dict = dict(attributes) if attributes else {}
        if parent_id:
            span_attrs["parent_span_id"] = parent_id

        span = self._tracer.start_span(name, attributes=span_attrs)
        span_id = str(uuid.uuid4())[:16]
        self._active_spans[span_id] = span
        return span_id

    def end_span(
        self, span_id: str, status: str = "ok", error: Exception | None = None
    ) -> None:
        """End a trace span."""
        if not OPENTELEMETRY_AVAILABLE:
            return
        span = self._active_spans.pop(span_id, None)
        if span:
            if error:
                span.record_exception(error)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(error)))
            else:
                span.set_status(trace.Status(trace.StatusCode.OK))
            span.end()

    @contextmanager
    def trace_operation(
        self, name: str, attributes: dict | None = None
    ) -> Iterator[str]:
        """Context manager for tracing an operation."""
        span_id = self.start_span(name, attributes=attributes)
        start = time.time()
        try:
            yield span_id
            self.end_span(span_id, status="ok")
        except Exception as e:
            self.end_span(span_id, status="error", error=e)
            raise
        finally:
            _duration = time.time() - start  # Reserved for future metric recording

    def inject_context(self, span_id: str) -> dict[str, str]:
        """Extract trace context for propagation via packet."""
        return {
            "trace.span_id": span_id,
            "trace.trace_id": str(uuid.uuid4())[:16],  # Would come from actual trace
        }

    def extract_context(self, headers: dict[str, str]) -> str | None:
        """Extract span_id from packet headers."""
        return headers.get("trace.span_id")
