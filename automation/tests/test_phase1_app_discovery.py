"""
Unit tests for Phase 1: App Discovery and Dynamic Application Launching.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from automation.action_dispatcher import (
    dispatch_launch_app,
    dispatch_open_url,
    launch_application,
    open_url,
)
from automation.app_discovery import AppDiscovery, AppInfo, discover_app, get_app_discovery
from automation.models import ActionResult, ExecutionMethod
from planner.execution_engine import ExecutionEngine
from planner.models import PlannedAction, PlannerActionType
from planner.task_decomposer import TaskDecomposer


class TestAppDiscovery:
    """Test dynamic app and protocol discovery."""

    def test_singleton_discovery_instance(self):
        d1 = get_app_discovery()
        d2 = get_app_discovery()
        assert d1 is d2

    def test_discover_builtin_notepad(self):
        info = discover_app("notepad")
        assert info is not None
        assert info.key == "notepad"
        assert info.display_name == "Notepad"
        assert "notepad" in info.path.lower()

    def test_discover_builtin_calculator(self):
        info = discover_app("calculator")
        assert info is not None
        assert info.is_uri is True
        assert info.uri == "calculator:"

    def test_discover_uri_direct(self):
        info = discover_app("ms-settings:display")
        assert info is not None
        assert info.is_uri is True
        assert info.uri == "ms-settings:display"

    def test_discover_url_direct(self):
        info = discover_app("https://google.com")
        assert info is not None
        assert info.is_uri is True
        assert info.uri == "https://google.com"

    def test_discover_nonexistent_app(self):
        info = discover_app("nonexistent_random_xyz_app_99999")
        assert info is None

    def test_list_known_apps(self):
        d = get_app_discovery()
        apps = d.list_known_apps()
        assert len(apps) > 10
        assert "notepad" in apps
        assert "chrome" in apps
        assert "spotify" in apps


class TestActionDispatcherLaunch:
    """Test launch_application and open_url dispatching."""

    def test_launch_nonexistent_app_fails_gracefully(self):
        res = launch_application("fake_non_existent_app_404")
        assert res.success is False
        assert "not found" in (res.error or "").lower()

    @patch("subprocess.Popen")
    def test_launch_valid_executable_mock(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        res = launch_application("notepad")
        assert res.success is True
        assert res.action_type == "launch_app"
        assert res.execution_method in (ExecutionMethod.SUBPROCESS.value, ExecutionMethod.SHELL_EXECUTE.value)

    @patch("os.startfile", create=True)
    def test_launch_uri_protocol(self, mock_startfile):
        res = launch_application("calculator")
        assert res.success is True
        assert res.execution_method == ExecutionMethod.SHELL_EXECUTE.value

    @patch("os.startfile", create=True)
    def test_open_url_default_browser(self, mock_startfile):
        res = open_url("https://www.python.org")
        assert res.success is True
        assert res.action_type == "open_url"
        assert res.execution_method == ExecutionMethod.SHELL_EXECUTE.value

    @patch("subprocess.Popen")
    @patch("automation.app_discovery.AppDiscovery.discover_app")
    def test_open_url_specific_browser(self, mock_discover, mock_popen):
        mock_discover.return_value = AppInfo(
            key="chrome",
            display_name="Google Chrome",
            path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        )
        mock_popen.return_value = MagicMock(pid=5555)

        res = open_url("https://github.com", browser="chrome")
        assert res.success is True
        assert res.execution_method == ExecutionMethod.SUBPROCESS.value


class TestExecutionEnginePhase1:
    """Test that ExecutionEngine dispatches LAUNCH_APP and OPEN_URL without requiring a UI element."""

    @patch("automation.action_dispatcher.launch_application")
    def test_dispatch_single_action_launch_app(self, mock_launch):
        mock_launch.return_value = ActionResult(
            action_type="launch_app",
            success=True,
            execution_method=ExecutionMethod.SUBPROCESS.value,
        )
        engine = ExecutionEngine()
        action = PlannedAction(
            action_type=PlannerActionType.LAUNCH_APP,
            target_description="Spotify",
            expected_result="Spotify open",
            parameters={"app": "spotify"},
        )
        res = engine._dispatch_single_action(action, None, "test-task-1")
        assert res.get("success") is True
        assert res.get("action_type") == "launch_app"

    @patch("automation.action_dispatcher.open_url")
    def test_dispatch_single_action_open_url(self, mock_open_url):
        mock_open_url.return_value = ActionResult(
            action_type="open_url",
            success=True,
            execution_method=ExecutionMethod.SHELL_EXECUTE.value,
        )
        engine = ExecutionEngine()
        action = PlannedAction(
            action_type=PlannerActionType.OPEN_URL,
            target_description="Open YouTube",
            expected_result="YouTube open",
            parameters={"url": "https://youtube.com"},
        )
        res = engine._dispatch_single_action(action, None, "test-task-2")
        assert res.get("success") is True
        assert res.get("action_type") == "open_url"


class TestTaskDecomposerPhase1:
    """Test task decomposition for launch and url goals."""

    def test_decompose_open_spotify(self):
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("task_p1_1", "open spotify")
        assert len(plan.steps) >= 1
        first_step = plan.steps[0]
        assert first_step.candidate_actions[0].action_type == PlannerActionType.LAUNCH_APP
        assert "spotify" in first_step.candidate_actions[0].parameters.get("app", "").lower()

    def test_decompose_open_url(self):
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("task_p1_2", "go to https://wikipedia.org")
        assert len(plan.steps) >= 1
        first_step = plan.steps[0]
        assert first_step.candidate_actions[0].action_type == PlannerActionType.OPEN_URL
        assert "wikipedia.org" in first_step.candidate_actions[0].parameters.get("url", "")
