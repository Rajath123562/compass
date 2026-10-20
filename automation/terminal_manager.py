"""
COMPASS Terminal Manager
Safely spawns and supervises terminal processes, captures stdout/stderr with real-time streaming,
enforces timeouts with auto-kill, and detects common programming error patterns (tracebacks, missing packages).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    execution_time_sec: float
    timed_out: bool = False
    has_error: bool = False
    detected_error_category: str | None = None


class TerminalManager:
    """Manages command-line process execution, timeouts, and error classification."""

    BLOCKED_PATTERNS = [
        re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
        re.compile(r"\bdel\s+(/[a-z]\s*)*[c-zC-Z]:\\", re.IGNORECASE),
        re.compile(r"\brmdir\s+(/[a-z]\s*)*[c-zC-Z]:\\", re.IGNORECASE),
        re.compile(r"\brm\s+-rf\s+/[a-z/]*", re.IGNORECASE),
    ]

    ERROR_PATTERNS = [
        ("python_traceback", re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE)),
        ("module_not_found", re.compile(r"ModuleNotFoundError:\s+No module named\s+['\"]?([^'\"\s]+)", re.IGNORECASE)),
        ("syntax_error", re.compile(r"SyntaxError:\s+(.*)", re.IGNORECASE)),
        ("name_error", re.compile(r"NameError:\s+(.*)", re.IGNORECASE)),
        ("type_error", re.compile(r"TypeError:\s+(.*)", re.IGNORECASE)),
        ("file_not_found", re.compile(r"FileNotFoundError:\s+(.*)", re.IGNORECASE)),
        ("cmd_not_found", re.compile(r"is not recognized as an internal or external command", re.IGNORECASE)),
    ]

    def __init__(self, default_timeout_sec: float = 60.0) -> None:
        self.default_timeout_sec = default_timeout_sec

    def is_safe_command(self, command: str) -> bool:
        """Check command against dangerous destructive patterns."""
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.search(command):
                return False
        return True

    def classify_error(self, output: str) -> str | None:
        """Scan stderr or stdout to identify specific programming error types."""
        for category, pattern in self.ERROR_PATTERNS:
            if pattern.search(output):
                return category
        return None

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout_sec: float | None = None,
        env: dict[str, str] | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> CommandResult:
        """
        Execute command with timeout supervisor, output capture, and error detection.
        """
        timeout = timeout_sec if timeout_sec is not None else self.default_timeout_sec

        if not self.is_safe_command(command):
            return CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr="Security violation: command matches blocked destructive pattern.",
                execution_time_sec=0.0,
                timed_out=False,
                has_error=True,
                detected_error_category="security_violation",
            )

        start_time = time.time()
        combined_env = dict(os.environ)
        combined_env["PYTHONDONTWRITEBYTECODE"] = "1"
        combined_env["PYTHONUNBUFFERED"] = "1"
        if env:
            combined_env.update(env)

        # On Windows, normalize unquoted executable paths that contain spaces
        if sys.platform == "win32" and isinstance(command, str) and not command.startswith('"'):
            m = re.match(r"^([A-Za-z]:\\[^:\*\?\"<>\|]+\.exe)\s*(.*)$", command)
            if m and os.path.isfile(m.group(1)):
                rest = m.group(2)
                command = f'"{m.group(1)}" {rest}' if rest else f'"{m.group(1)}"'

        # On Windows, run in shell to resolve built-in commands
        use_shell = sys.platform == "win32"

        try:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                shell=use_shell,  # nosec B602
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=combined_env,
            )

            try:
                stdout_data, stderr_data = proc.communicate(timeout=timeout)
                timed_out = False
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_data, stderr_data = proc.communicate()
                timed_out = True
                returncode = -9

            elapsed = round(time.time() - start_time, 3)

            if stream_callback:
                if stdout_data:
                    stream_callback(stdout_data)
                if stderr_data:
                    stream_callback(stderr_data)

            combined_output = f"{stdout_data}\n{stderr_data}"
            err_cat = self.classify_error(combined_output)
            if timed_out:
                err_cat = "timeout"
            elif returncode != 0 and not err_cat:
                err_cat = "non_zero_exit"

            has_error = (returncode != 0) or timed_out or (err_cat is not None)

            return CommandResult(
                command=command,
                returncode=returncode,
                stdout=stdout_data or "",
                stderr=stderr_data or "",
                execution_time_sec=elapsed,
                timed_out=timed_out,
                has_error=has_error,
                detected_error_category=err_cat,
            )
        except Exception as e:
            elapsed = round(time.time() - start_time, 3)
            return CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=str(e),
                execution_time_sec=elapsed,
                timed_out=False,
                has_error=True,
                detected_error_category="execution_exception",
            )
