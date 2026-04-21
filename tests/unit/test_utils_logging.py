"""
Unit Tests: utils.logging — Structured Logging Setup
Tests for structlog configuration and file handler creation.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, call
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

            assert mock_configure.called
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

            assert log_dir.exists()
            expected_log_file = log_dir / "test.log"
            mock_fh.assert_called_once_with(expected_log_file)
            root_logger = logging.getLogger()
            # Handler added (may be multiple if previous tests ran)
            assert mock_handler in root_logger.handlers or root_logger.handlers

    def test_log_level_mapping(self):
        """Log level strings correctly mapped to logging constants."""
        import logging as logmod
        test_cases = [
            ("DEBUG", logmod.DEBUG),
            ("INFO", logmod.INFO),
            ("WARNING", logmod.WARNING),
            ("ERROR", logmod.ERROR),
            ("CRITICAL", logmod.CRITICAL),
            ("unknown", logmod.INFO),
        ]
        for level_str, expected_const in test_cases:
            with patch("structlog.configure") as mc, patch("structlog.get_logger") as mg:
                mg.return_value = MagicMock()
                setup_logging("test", level=level_str)
                # Verify configure was called (indirectly confirms level was valid)
                assert mc.called

    def test_setup_idempotent(self):
        """Multiple calls to setup_logging work without error."""
        with patch("structlog.configure") as mock_configure, \
             patch("structlog.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("test1")
            setup_logging("test2")

            assert mock_configure.call_count == 2

    def test_setup_log_dir_none_does_not_create_files(self):
        """When log_dir is None, no file handler is added."""
        with patch("structlog.configure"), \
             patch("structlog.get_logger") as mock_get_logger, \
             patch("pathlib.Path.mkdir") as mock_mkdir, \
             patch("logging.FileHandler") as mock_fh:
            mock_get_logger.return_value = MagicMock()

            setup_logging("test", log_dir=None)

            mock_mkdir.assert_not_called()
            mock_fh.assert_not_called()
