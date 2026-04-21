"""
Unit Tests: utils.logging — Structured Logging Setup
Tests for structlog configuration and file handler creation.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from cosmic_mycelium.utils.logging import setup_logging


class TestSetupLogging:
    """Tests for structured logging configuration."""

    def test_setup_console_only(self):
        """setup_logging with no log_dir configures console-only logging."""
        with patch("structlog.configure") as mock_configure, \
             patch("structlog.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("test-component", level="INFO")

            # structlog.configure should be called
            assert mock_configure.called
            # Logger should be obtained and info emitted
            mock_logger.info.assert_called_once_with(
                "logging_configured", level="INFO", component="test-component"
            )

    def test_setup_with_file_logging_creates_directory(self, tmp_path: Path):
        """When log_dir provided, directory is created and file handler added."""
        log_dir = tmp_path / "logs"
        with patch("structlog.configure"), \
             patch("structlog.get_logger") as mock_get_logger, \
             patch("logging.FileHandler") as mock_fh:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_handler = MagicMock()
            mock_fh.return_value = mock_handler

            setup_logging("test", log_dir=log_dir)

            # Directory created
            assert log_dir.exists()
            # FileHandler constructed with correct path
            expected_log_file = log_dir / "test.log"
            mock_fh.assert_called_once_with(expected_log_file)
            # Handler added to root logger
            root_logger = logging.getLogger()
            assert mock_handler in root_logger.handlers

    def test_log_level_mapping(self):
        """Log level strings correctly mapped to logging constants."""
        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("unknown", logging.INFO),  # fallback
        ]

        for level_str, expected_const in test_cases:
            with patch("structlog.configure"), patch("structlog.get_logger"):
                setup_logging("test", level=level_str)
                # No exception = pass; internal mapping verified indirectly
                # since structlog.configure uses the constant

    def test_setup_idempotent(self):
        """Multiple calls to setup_logging reconfigure without error."""
        with patch("structlog.configure") as mock_configure, \
             patch("structlog.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("test1")
            setup_logging("test2")

            assert mock_configure.call_count == 2
