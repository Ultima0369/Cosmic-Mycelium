"""
Layer 1 — Timescale Segmenter Tests
Tests temporal segmentation and windowing logic.
"""

from __future__ import annotations

from cosmic_mycelium.infant.core.layer_1_timescale_segmenter import (
    Scale,
    Segment,
    TimescaleSegmenter,
)


class TestTimescaleSegmenterInitialization:
    """Tests for segmenter construction."""

    def test_default_window_sizes(self):
        """Default window sizes per scale are reasonable."""
        s = TimescaleSegmenter()
        assert s.millisecond_window.maxlen == 1000
        assert s.second_window.maxlen == 100
        assert s.minute_window.maxlen == 60

    def test_custom_window_sizes(self):
        """Custom window sizes are respected."""
        s = TimescaleSegmenter(
            ms_window=500,
            sec_window=50,
            min_window=30,
        )
        assert s.millisecond_window.maxlen == 500
        assert s.second_window.maxlen == 50
        assert s.minute_window.maxlen == 30


class TestBufferAccumulation:
    """Tests for timestamp buffering."""

    def test_buffer_accumulates_timestamps(self):
        """Timestamps accumulate in correct windows."""
        s = TimescaleSegmenter()
        s.accumulate({"t": 1000.0})
        s.accumulate({"t": 1001.0})
        assert len(s.millisecond_window) == 2

    def test_buffer_respects_maxlen(self):
        """Buffer FIFO evicts oldest when full."""
        s = TimescaleSegmenter(ms_window=3)
        s.accumulate({"t": 1.0})
        s.accumulate({"t": 2.0})
        s.accumulate({"t": 3.0})
        s.accumulate({"t": 4.0})  # Should evict 1.0
        assert len(s.millisecond_window) == 3
        assert s.millisecond_window[0] == {"t": 2.0}


class TestSegmentCreation:
    """Tests for segment extraction."""

    def test_create_segment_returns_valid_segment(self):
        """create_segment returns a Segment with proper fields."""
        s = TimescaleSegmenter()
        s.accumulate({"v": 1.0})
        s.accumulate({"v": 2.0})
        segment = s.create_segment()

        assert isinstance(segment, Segment)
        assert hasattr(segment, "start_time")
        assert hasattr(segment, "end_time")
        assert hasattr(segment, "features")
        assert hasattr(segment, "scale")

    def test_segment_scale_assignment(self):
        """Segment scale matches current scale context."""
        s = TimescaleSegmenter()
        s.current_scale = Scale.MILLISECOND
        s.accumulate({"x": 1.0})
        seg = s.create_segment()
        assert seg.scale == Scale.MILLISECOND

    def test_segment_feature_extraction(self):
        """Segment features include basic statistics."""
        s = TimescaleSegmenter()
        for i in range(10):
            s.accumulate({"value": float(i)})
        seg = s.create_segment()

        assert "count" in seg.features
        assert "mean_value" in seg.features
        assert seg.features["count"] == 10


class TestScaleEscalation:
    """Tests for millisecond → second → minute escalation."""

    def test_escalate_millisecond_to_second(self):
        """When ms window is full, scale escalates to SECOND."""
        s = TimescaleSegmenter(ms_window=3, sec_window=100)
        s.current_scale = Scale.MILLISECOND
        for _ in range(4):
            s.accumulate({"v": 1.0})  # 4 > 3, triggers escalate

        assert s.current_scale == Scale.SECOND

    def test_escalate_second_to_minute(self):
        """When second window is full, scale escalates to MINUTE."""
        s = TimescaleSegmenter(ms_window=10, sec_window=3, min_window=100)
        s.current_scale = Scale.SECOND
        for _ in range(4):
            s.accumulate({"v": 1.0})

        assert s.current_scale == Scale.MINUTE

    def test_no_escalation_when_not_full(self):
        """Scale stays at MILLISECOND when window not full."""
        s = TimescaleSegmenter(ms_window=10)
        s.current_scale = Scale.MILLISECOND
        for _ in range(5):
            s.accumulate({"v": 1.0})

        assert s.current_scale == Scale.MILLISECOND


class TestReset:
    """Tests for reset functionality."""

    def test_reset_clears_buffers(self):
        """reset() clears all time windows."""
        s = TimescaleSegmenter()
        for _ in range(10):
            s.accumulate({"v": 1.0})

        s.reset()
        assert len(s.millisecond_window) == 0
        assert len(s.second_window) == 0
        assert len(s.minute_window) == 0

    def test_reset_returns_to_millisecond_scale(self):
        """After reset, current_scale is MILLISECOND."""
        s = TimescaleSegmenter()
        s.current_scale = Scale.MINUTE
        s.reset()
        assert s.current_scale == Scale.MILLISECOND


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_segment_has_no_features(self):
        """Creating segment with no data yields empty features."""
        s = TimescaleSegmenter()
        seg = s.create_segment()
        assert seg.features == {}

    def test_single_element_segment(self):
        """Single element segment works."""
        s = TimescaleSegmenter()
        s.accumulate({"v": 42.0})
        seg = s.create_segment()
        assert seg.features["count"] == 1
