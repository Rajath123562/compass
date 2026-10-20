"""
Unit tests for COMPASS TerminalManager (Phase 7: Terminal & Execution Supervision).
"""

import sys
import pytest

from automation.terminal_manager import TerminalManager


class TestTerminalManagerExecution:
    """Test process execution, output capture, and timeout supervisor."""

    def test_successful_command_execution(self):
        tm = TerminalManager()
        cmd = f'"{sys.executable}" -c "print(\'HELLO_COMPASS\')"'
        res = tm.execute(cmd, timeout_sec=5.0)

        assert res.returncode == 0
        assert "HELLO_COMPASS" in res.stdout
        assert res.has_error is False
        assert res.timed_out is False
        assert res.execution_time_sec >= 0.0

    def test_timeout_auto_kill(self):
        tm = TerminalManager()
        # Sleep for 5 seconds with a 0.2s timeout
        cmd = f'"{sys.executable}" -c "import time; time.sleep(5)"'
        res = tm.execute(cmd, timeout_sec=0.2)

        assert res.timed_out is True
        assert res.has_error is True
        assert res.detected_error_category == "timeout"

    def test_security_violation_block(self):
        tm = TerminalManager()
        dangerous_cmd = "rm -rf /"
        res = tm.execute(dangerous_cmd)

        assert res.has_error is True
        assert res.detected_error_category == "security_violation"
        assert res.returncode == -1


class TestTerminalManagerErrorClassification:
    """Test classification of programming errors from command output."""

    def test_python_traceback_and_name_error(self):
        tm = TerminalManager()
        cmd = f'"{sys.executable}" -c "print(undefined_variable_xyz)"'
        res = tm.execute(cmd, timeout_sec=5.0)

        assert res.returncode != 0
        assert res.has_error is True
        assert res.detected_error_category in ("python_traceback", "name_error")

    def test_module_not_found_error(self):
        tm = TerminalManager()
        cmd = f'"{sys.executable}" -c "import completely_non_existent_package_12345"'
        res = tm.execute(cmd, timeout_sec=5.0)

        assert res.returncode != 0
        assert res.has_error is True
        assert res.detected_error_category in ("python_traceback", "module_not_found")
