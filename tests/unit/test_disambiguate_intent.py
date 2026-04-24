"""
Intent Disambiguation Test Suite — Phase 1.3
Tests the clarification question generation when prediction confidence is low.
"""

from __future__ import annotations

import pytest

from cosmic_mycelium.infant.main import SiliconInfant


class TestIntentDisambiguation:
    """disambiguate_intent() must generate context-aware clarification questions."""

    def make_infant(self):
        """Helper: minimal infant for disambiguation tests."""
        return SiliconInfant(infant_id="test-intent")

    def make_perception(self, vibration=0.0, temperature=22.0, spectrum_power=1.0):
        """Helper: build perception dict with sensor values."""
        return {
            "timestamp": 1234567890.0,
            "physical": {"q": 0.5, "p": 0.1},
            "sensors": {
                "vibration": vibration,
                "temperature": temperature,
                "spectrum_power": spectrum_power,
            },
            "semantic_embedding": None,
            "external": {},
        }

    def test_high_confidence_returns_none(self):
        """Confidence ≥ 0.5 → no question (confident prediction)."""
        infant = self.make_infant()
        perception = self.make_perception()
        question = infant.disambiguate_intent(perception, confidence=0.6)
        assert question is None

    def test_vibration_question_high_vibration(self):
        """Vibration > 0.2 → machinery vs environment question."""
        infant = self.make_infant()
        perception = self.make_perception(vibration=0.3)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert question == "Is that vibration from machinery or environmental movement?"

    def test_vibration_question_boundary(self):
        """At exactly 0.2 vibration → not high enough."""
        infant = self.make_infant()
        perception = self.make_perception(vibration=0.2)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert question != "Is that vibration from machinery or environmental movement?"

    def test_temperature_high_question(self):
        """Temperature > 28°C → temperature confirmation."""
        infant = self.make_infant()
        perception = self.make_perception(temperature=30.5)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert "30.5°C" in question
        assert "expected" in question.lower()

    def test_temperature_low_question(self):
        """Temperature < 16°C → temperature confirmation."""
        infant = self.make_infant()
        perception = self.make_perception(temperature=12.0)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert "12.0°C" in question

    def test_low_spectrum_question(self):
        """spectrum_power < 0.2 → illumination question."""
        infant = self.make_infant()
        perception = self.make_perception(spectrum_power=0.1)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert "light level" in question.lower() or "illumination" in question.lower()

    def test_high_spectrum_question(self):
        """spectrum_power > 2.0 → adaptation question."""
        infant = self.make_infant()
        perception = self.make_perception(spectrum_power=2.5)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert "bright" in question.lower() or "adaptation" in question.lower()

    def test_generic_fallback(self):
        """No specific pattern → generic clarification question."""
        infant = self.make_infant()
        perception = self.make_perception(vibration=0.05, temperature=22.0, spectrum_power=0.5)
        question = infant.disambiguate_intent(perception, confidence=0.2)
        assert question == "Perception unclear — what should I focus on?"

    def test_confidence_boundary(self):
        """At exactly confidence=0.5 → should return None."""
        infant = self.make_infant()
        perception = self.make_perception(vibration=0.3)
        assert infant.disambiguate_intent(perception, confidence=0.5) is None

    def test_missing_sensor_keys_defaults(self):
        """Missing sensor keys should use defaults without error."""
        infant = self.make_infant()
        perception = {"sensors": {}}  # No vibration/temperature/spectrum
        question = infant.disambiguate_intent(perception, confidence=0.2)
        # Should hit generic fallback
        assert question == "Perception unclear — what should I focus on?"

    def test_extreme_temperature_formatting(self):
        """Very high/low temperatures should still format correctly."""
        infant = self.make_infant()
        perception_high = self.make_perception(temperature=999.9)
        q_high = infant.disambiguate_intent(perception_high, confidence=0.2)
        assert "999.9" in q_high

        perception_low = self.make_perception(temperature=-50.0)
        q_low = infant.disambiguate_intent(perception_low, confidence=0.2)
        assert "-50.0" in q_low
