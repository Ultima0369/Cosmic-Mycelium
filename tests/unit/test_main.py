"""
Unit Tests — infant/main.py — SiliconInfant Core Logic
Tests the perceive→predict→verify→adapt→act pipeline in isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))

from cosmic_mycelium.infant.main import SiliconInfant
from cosmic_mycelium.common.data_packet import CosmicPacket
from cosmic_mycelium.infant.hic import BreathState, HIC


class TestSiliconInfantInitialization:
    """Test SiliconInfant constructor and initial state."""

    def test_default_initialization(self):
        """Infant initializes with default config."""
        infant = SiliconInfant("test-001")
        assert infant.infant_id == "test-001"
        assert infant.config == {}
        assert infant.hic is not None
        assert infant.sympnet is not None
        assert infant.explorer is not None
        assert infant.memory is not None
        assert infant.brain is not None
        assert infant.interface is not None
        assert infant.state == {"q": 1.0, "p": 0.0}
        assert infant.inbox == []
        assert infant.outbox == []
        # Log gets one entry from __init__
        assert len(infant.log) >= 1

    def test_custom_config_applied(self):
        """Custom config values override defaults."""
        config = {"energy_max": 200.0, "contract_duration": 0.1}
        infant = SiliconInfant("custom-001", config=config)
        assert infant.hic.config.energy_max == 200.0
        assert infant.hic.config.contract_duration == 0.1

    def test_subsystems_initialized(self):
        """All six layers are properly instantiated."""
        infant = SiliconInfant("full-stack")
        assert infant.hic is not None
        assert infant.explorer is not None
        assert infant.memory is not None
        assert infant.brain is not None
        assert infant.interface is not None


class TestPerceive:
    """Test the perceive() method."""

    def test_perceive_returns_expected_keys(self):
        """Perception dict contains timestamp and physical state."""
        infant = SiliconInfant("p")
        result = infant.perceive()
        assert "timestamp" in result
        assert "physical" in result
        assert "external" in result

    def test_perceive_physical_has_q_and_p(self):
        """Physical state has q and p."""
        infant = SiliconInfant("p")
        result = infant.perceive()
        assert "q" in result["physical"]
        assert "p" in result["physical"]

    def test_perceive_mutates_state(self):
        """Perceive updates internal state with small fluctuations."""
        infant = SiliconInfant("p")
        q_before = infant.state["q"]
        p_before = infant.state["p"]
        infant.perceive()
        assert abs(infant.state["q"] - q_before) <= 0.01
        assert abs(infant.state["p"] - p_before) <= 0.01


class TestPredict:
    """Test the predict() method."""

    def test_predict_returns_prediction_and_confidence(self):
        infant = SiliconInfant("pred")
        perception = {"physical": {"q": 1.0, "p": 0.0}}
        predicted, confidence = infant.predict(perception)
        assert isinstance(predicted, dict)
        assert "q" in predicted and "p" in predicted
        assert 0.0 <= confidence <= 1.0


class TestVerify:
    """Test the verify() method."""

    def test_verify_mean_absolute_error(self):
        infant = SiliconInfant("v")
        predicted = {"q": 1.0, "p": 0.5}
        actual = {"physical": {"q": 1.2, "p": 0.3}}
        error = infant.verify(predicted, actual)
        assert error == pytest.approx(0.2)

    def test_verify_zero_on_perfect_match(self):
        infant = SiliconInfant("v")
        predicted = {"q": 1.0, "p": 0.5}
        actual = {"physical": {"q": 1.0, "p": 0.5}}
        assert infant.verify(predicted, actual) == 0.0


class TestAdapt:
    """Test the adapt() method."""

    def test_adapt_called_when_error_above_threshold(self):
        infant = SiliconInfant("a")
        infant.config["adaptation_threshold"] = 0.001
        with patch.object(infant.sympnet, 'adapt') as ma, \
             patch.object(infant.hic, 'adapt_value_vector') as mh, \
             patch.object(infant.memory, 'reinforce') as mm:
            infant.adapt(error=0.01)
            ma.assert_called_once()
            mh.assert_called_once()
            mm.assert_called_once_with(["predict", "error"], success=False)

    def test_adapt_skipped_below_threshold(self):
        infant = SiliconInfant("a")
        infant.config["adaptation_threshold"] = 0.001
        with patch.object(infant.sympnet, 'adapt') as ma, \
             patch.object(infant.hic, 'adapt_value_vector') as mh, \
             patch.object(infant.memory, 'reinforce') as mm:
            infant.adapt(error=0.0001)
            ma.assert_not_called()
            mh.assert_not_called()
            mm.assert_not_called()


class TestAct:
    """Test the act() method."""

    def test_act_suspend_on_low_confidence(self):
        infant = SiliconInfant("act")
        with patch.object(infant.hic, 'get_suspend_packet') as m:
            m.return_value = CosmicPacket(
                timestamp=time.time(), source_id=infant.infant_id,
                value_payload={"action": "suspend"}
            )
            packet = infant.act({"physical": {"q": 1, "p": 0}}, {"q": 1.1, "p": 0.1}, 0.2)
            m.assert_called_once_with(infant.infant_id)
            assert packet.value_payload["action"] == "suspend"

    def test_act_suspend_on_low_energy(self):
        infant = SiliconInfant("act")
        # Mock energy property to return low value
        with patch.object(HIC, 'energy', new_callable=lambda: property(lambda self: 15.0)):
            with patch.object(infant.hic, 'get_suspend_packet') as m:
                m.return_value = CosmicPacket(
                    timestamp=time.time(), source_id=infant.infant_id,
                    value_payload={"action": "suspend"}
                )
                packet = infant.act({"physical": {"q": 1, "p": 0}}, {"q": 1.1, "p": 0.1}, 0.8)
                m.assert_called_once_with(infant.infant_id)

    def test_act_returns_action_packet_when_conditions_good(self):
        infant = SiliconInfant("act")
        # Use actual explorer.plan but mock energy check
        with patch.object(infant, 'explorer') as mock_explorer:
            mock_explorer.plan.return_value = (
                {"path": ["action_0"], "quality": 0.9, "energy": 1.0, "steps": 1},
                0.9
            )
            packet = infant.act({"physical": {"q": 1, "p": 0}}, {"q": 1.1, "p": 0.1}, 0.8)
            assert packet is not None
            assert packet.info_payload["action"] == "execute"

    def test_act_reinforces_successful_path(self):
        infant = SiliconInfant("act")
        with patch.object(infant, 'explorer') as mock_explorer, \
             patch.object(infant.memory, 'reinforce') as mock_reinforce:
            mock_explorer.plan.return_value = (
                {"path": ["a", "b"], "quality": 0.9, "energy": 1.0, "steps": 2}, 0.9
            )
            infant.act({"physical": {"q": 1, "p": 0}}, {"q": 1.1, "p": 0.1}, 0.8)
            mock_reinforce.assert_called_once_with(["a", "b"], success=True)

    def test_act_suspend_when_no_plan(self):
        infant = SiliconInfant("act")
        with patch.object(infant, 'explorer') as mock_explorer:
            mock_explorer.plan.return_value = (None, 0.0)
            with patch.object(infant.hic, 'get_suspend_packet') as m:
                m.return_value = CosmicPacket(
                    timestamp=time.time(), source_id=infant.infant_id,
                    value_payload={"action": "suspend"}
                )
                packet = infant.act({"physical": {"q": 1, "p": 0}}, {"q": 1.1, "p": 0.1}, 0.8)
                m.assert_called_once()


class TestProcessInbox:
    """Test the process_inbox() method."""

    def test_process_inbox_suspend_action(self):
        infant = SiliconInfant("pib")
        packet = CosmicPacket(
            timestamp=time.time(), source_id="partner-1",
            value_payload={"action": "suspend"}  # Correct: value_payload not info_payload
        )
        infant.inbox = [packet]
        with patch.object(infant.hic, 'adapt_value_vector') as mock_adapt:
            infant.process_inbox()
            mock_adapt.assert_called_once_with({"caution": 0.005})

    def test_process_inbox_consensus_action(self):
        infant = SiliconInfant("pib")
        packet = CosmicPacket(
            timestamp=time.time(), source_id="partner-1",
            value_payload={"action": "consensus_proposal"}
        )
        infant.inbox = [packet]
        with patch.object(infant.hic, 'adapt_value_vector') as mock_adapt:
            infant.process_inbox()
            mock_adapt.assert_called_once_with({"mutual_benefit": 0.01})

    def test_process_inbox_empty(self):
        infant = SiliconInfant("pib")
        infant.inbox = []
        infant.process_inbox()  # Should not raise


class TestBreathCycle:
    """Test the breath_cycle() method."""

    def test_breath_cycle_suspend_returns_suspend_packet(self):
        infant = SiliconInfant("bc")
        with patch.object(infant.hic, 'get_suspend_packet') as m, \
             patch('time.sleep'), \
             patch.object(type(infant.hic), 'state', new_callable=PropertyMock) as mock_state:
            mock_state.return_value = BreathState.SUSPEND
            m.return_value = CosmicPacket(
                timestamp=time.time(), source_id=infant.infant_id,
                value_payload={"action": "suspend"}
            )
            packet = infant.breath_cycle()
            m.assert_called_once_with(infant.infant_id)
            assert packet.value_payload["action"] == "suspend"

    def test_breath_cycle_contract_runs_full_pipeline(self):
        infant = SiliconInfant("bc")
        with patch.object(type(infant.hic), 'state', new_callable=PropertyMock) as mock_state, \
             patch.object(infant, 'perceive') as m_perceive, \
             patch.object(infant, 'predict') as m_predict, \
             patch.object(infant, 'verify') as m_verify, \
             patch.object(infant, 'adapt') as m_adapt, \
             patch.object(infant, 'act') as m_act:
            mock_state.return_value = BreathState.CONTRACT
            m_perceive.return_value = {"physical": {"q": 1.0, "p": 0.0}}
            m_predict.return_value = ({"q": 1.1, "p": 0.1}, 0.8)
            m_verify.return_value = 0.05
            m_act.return_value = CosmicPacket(
                timestamp=time.time(), source_id=infant.infant_id,
                info_payload={"action": "execute"}
            )
            packet = infant.breath_cycle()
            m_perceive.assert_called_once()
            m_predict.assert_called_once_with(m_perceive.return_value)
            m_verify.assert_called_once_with(m_predict.return_value[0], m_perceive.return_value)
            m_adapt.assert_called_once_with(0.05)
            m_act.assert_called_once_with(m_perceive.return_value, m_predict.return_value[0], 0.8)
            assert packet.info_payload["action"] == "execute"

    def test_breath_cycle_diffuse_calls_cleanup(self):
        infant = SiliconInfant("bc")
        with patch.object(type(infant.hic), 'state', new_callable=PropertyMock) as mock_state, \
             patch.object(infant, 'process_inbox') as m_proc, \
             patch.object(infant.memory, 'forget') as m_forget, \
             patch.object(infant.brain, 'decay_activations') as m_decay, \
             patch('time.sleep'):
            mock_state.return_value = BreathState.DIFFUSE
            infant.breath_cycle()
            m_proc.assert_called_once()
            m_forget.assert_called_once()
            m_decay.assert_called_once()

    def test_breath_cycle_updates_hic(self):
        infant = SiliconInfant("bc")
        with patch.object(infant.hic, 'update_breath') as m_update:
            infant.breath_cycle()
            m_update.assert_called_once_with(confidence=0.7, work_done=False)


class TestRun:
    """Test the run() method."""

    def test_run_stops_at_max_cycles(self):
        infant = SiliconInfant("run")
        infant.hic._energy = 100.0
        with patch.object(infant, 'breath_cycle', return_value=None) as m_cycle:
            infant.run(max_cycles=3)
            assert m_cycle.call_count == 3

    def test_run_stops_when_energy_zero(self):
        infant = SiliconInfant("run")
        infant.hic._energy = 0.0
        with patch.object(infant, 'breath_cycle') as m_cycle:
            infant.run(max_cycles=None)
            m_cycle.assert_not_called()

    def test_run_appends_action_packets(self):
        infant = SiliconInfant("run")
        infant.hic._energy = 50.0
        pkt = CosmicPacket(
            timestamp=time.time(), source_id=infant.infant_id,
            info_payload={"action": "execute"}
        )
        # Pattern: action, action, None, None, None (for max_cycles=5)
        with patch.object(infant, 'breath_cycle', side_effect=[pkt, pkt, None, None, None]):
            infant.run(max_cycles=5)
            assert len(infant.outbox) == 2

    def test_run_logs_lifecycle(self):
        infant = SiliconInfant("run")
        infant.hic._energy = 1.0
        with patch.object(infant, 'breath_cycle', return_value=None):
            infant.run(max_cycles=1)
        # Find stop log
        stop_logs = [e for e in infant.log if "Stopped after" in e.get("msg", "")]
        assert len(stop_logs) >= 1


class TestGetStatus:
    """Test the get_status() method."""

    def test_status_has_all_keys(self):
        infant = SiliconInfant("s")
        infant.run(max_cycles=3)
        status = infant.get_status()
        required = {"infant_id", "uptime", "hic", "sympnet", "memory", "brain", "interface", "log_tail"}
        assert required.issubset(status.keys())

    def test_status_infant_id(self):
        infant = SiliconInfant("s-001")
        assert infant.get_status()["infant_id"] == "s-001"

    def test_status_uptime_positive(self):
        infant = SiliconInfant("s")
        assert infant.get_status()["uptime"] >= 0

    def test_status_hic_fields(self):
        infant = SiliconInfant("s")
        infant.run(max_cycles=1)
        hic = infant.get_status()["hic"]
        assert "energy" in hic and "state" in hic

    def test_status_memory_coverage(self):
        infant = SiliconInfant("s")
        infant.run(max_cycles=10)
        cov = infant.get_status()["memory"]["coverage"]
        assert 0.0 <= cov <= 1.0

    def test_status_brain_has_regions(self):
        infant = SiliconInfant("s")
        infant.run(max_cycles=3)
        assert "regions" in infant.get_status()["brain"]

    def test_status_interface_has_partner_count(self):
        infant = SiliconInfant("s")
        infant.run(max_cycles=3)
        assert "partner_count" in infant.get_status()["interface"]

    def test_status_log_tail_is_list(self):
        infant = SiliconInfant("s")
        infant.run(max_cycles=2)
        assert isinstance(infant.get_status()["log_tail"], list)


class TestLogging:
    """Test the _log() internal method."""

    def test_log_appends_entry(self):
        infant = SiliconInfant("log")
        initial = len(infant.log)
        infant._log("Test msg", "INFO")
        assert len(infant.log) == initial + 1
        entry = infant.log[-1]
        assert entry["msg"] == "Test msg"
        assert entry["level"] == "INFO"

    def test_log_respects_maxlen(self):
        infant = SiliconInfant("log")
        for i in range(1100):
            infant._log(f"msg {i}", "INFO")
        assert len(infant.log) == 1000

    def test_log_default_level(self):
        infant = SiliconInfant("log")
        infant._log("No level specified")
        assert infant.log[-1]["level"] == "INFO"
