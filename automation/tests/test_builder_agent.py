"""
Unit and integration tests for COMPASS BuilderAgent (Phase 7: Autonomous Builder Agent & Self-Healing Loop).
"""

import sys
from pathlib import Path
import pytest

from automation.builder_agent import BuilderAgent


class TestBuilderAgentSandbox:
    """Test safe file operations and path confinement."""

    def test_file_write_and_read(self, tmp_path: Path):
        agent = BuilderAgent(workspace_root=tmp_path)
        rel = "src/hello.py"
        res = agent.write_file(rel, "print('hello from builder')")
        assert res["status"] == "created"

        content = agent.read_file(rel)
        assert content == "print('hello from builder')"

    def test_file_edit(self, tmp_path: Path):
        agent = BuilderAgent(workspace_root=tmp_path)
        rel = "config.txt"
        agent.write_file(rel, "mode = debug\nport = 8000")

        res = agent.edit_file(rel, "mode = debug", "mode = production")
        assert res["status"] == "updated"
        assert res["replaced"] is True

        content = agent.read_file(rel)
        assert "mode = production" in content

    def test_sandbox_path_traversal_prevention(self, tmp_path: Path):
        agent = BuilderAgent(workspace_root=tmp_path)
        with pytest.raises(PermissionError):
            agent.write_file("../forbidden.txt", "exploit")

        with pytest.raises(PermissionError):
            agent.read_file("../../secret.env")


class TestBuilderAgentSelfHealingLoop:
    """Test self-healing loop: initial code failure -> error feedback -> automated repair -> success."""

    def test_self_healing_success_on_retry(self, tmp_path: Path):
        agent = BuilderAgent(workspace_root=tmp_path)

        # Simulation:
        # Attempt 1: generator produces faulty calculator (subtraction instead of addition)
        # Attempt 2: after receiving test failure feedback, generator fixes it to addition
        def mock_generator(goal: str, error_context: str):
            if "Attempt 1 test failure" in error_context:
                # Fixed version
                return [{
                    "action": "write_file",
                    "path": "calc.py",
                    "content": "def add(a, b):\n    return a + b\n",
                }]
            else:
                # Buggy initial version
                return [{
                    "action": "write_file",
                    "path": "calc.py",
                    "content": "def add(a, b):\n    return a - b\n",
                }]

        # Write test script that tests add(2, 3) == 5
        agent.write_file("test_calc.py", "import calc\nassert calc.add(2, 3) == 5\nprint('TESTS_PASSED')")

        test_cmd = f'"{sys.executable}" test_calc.py'
        report = agent.build_and_verify(
            goal="Implement an add function in calc.py",
            test_command=test_cmd,
            max_attempts=3,
            mock_generator_fn=mock_generator,
        )

        assert report["status"] == "success"
        assert report["attempts"] == 2
        assert "calc.py" in report["modified_files"]
        assert report["final_test_result"].returncode == 0
        assert "TESTS_PASSED" in report["final_test_result"].stdout

    def test_max_retries_exceeded_report(self, tmp_path: Path):
        agent = BuilderAgent(workspace_root=tmp_path)

        # Generator keeps producing a failing script
        def persistently_broken_generator(goal: str, error_context: str):
            return [{
                "action": "write_file",
                "path": "broken.py",
                "content": "raise RuntimeError('Never works')",
            }]

        report = agent.build_and_verify(
            goal="Build something",
            test_command=f'"{sys.executable}" broken.py',
            max_attempts=2,
            mock_generator_fn=persistently_broken_generator,
        )

        assert report["status"] == "max_retries_exceeded"
        assert report["attempts"] == 2
        assert len(report["error_history"]) == 2
        assert report["final_test_result"].returncode != 0
