"""
COMPASS Release Gate Self-Tests (COMPASS-AUDIT-011, COMPASS-AUDIT-012, COMPASS-AUDIT-024)
Proves that the release gate fails closed on missing, malformed, stale, or failing evidence.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from assurance.tools.release_gate import (
    MANDATORY_GATES,
    PERFORMANCE_SLOS,
    evaluate_gate,
)


def test_missing_mandatory_gates_fail_closed(tmp_path):
    """If mandatory evidence files do not exist, gate must be FAIL with unverified blocking gates."""
    with patch("assurance.tools.release_gate.ROOT_DIR", tmp_path), patch(
        "assurance.tools.release_gate.REPORT_DIR", tmp_path
    ), patch(
        "assurance.tools.release_gate.FINDINGS_FILE", tmp_path / "nonexistent.json"
    ):
        result = evaluate_gate(run_id="test-run-1")

    assert result["overall_readiness"] == "FAIL"
    assert len(result["blocking_gates"]) > 0
    # Every missing mandatory gate should be in blocking_gates
    for g in MANDATORY_GATES:
        assert g in result["blocking_gates"]


def test_open_critical_security_finding_blocks_gate(tmp_path):
    """An open CRITICAL or HIGH finding in finding_register.json must block release."""
    findings_file = tmp_path / "finding_register.json"
    findings_file.write_text(
        json.dumps(
            [
                {
                    "finding_id": "F-TEST-1",
                    "severity": "CRITICAL",
                    "status": "OPEN",
                    "title": "Unauthenticated RCE",
                }
            ]
        )
    )

    with patch("assurance.tools.release_gate.FINDINGS_FILE", findings_file), patch(
        "assurance.tools.release_gate.REPORT_DIR", tmp_path
    ):
        result = evaluate_gate(run_id="test-run-2")

    assert result["overall_readiness"] == "FAIL"
    assert "security" in result["blocking_gates"]
    assert result["gates"]["security"]["status"] == "FAIL"


def test_npm_high_vulnerability_blocks_dependency_gate(tmp_path):
    """COMPASS-AUDIT-012: High/critical npm vulnerability must block dependency gate."""
    dep_report = tmp_path / "dependency_report.json"
    dep_report.write_text(
        json.dumps(
            {
                "tools": {
                    "pip_audit": {"vulnerable_packages": 0},
                    "npm_audit": {
                        "vulnerabilities_summary": {
                            "critical": 0,
                            "high": 1,
                            "moderate": 0,
                            "low": 0,
                        }
                    },
                }
            }
        )
    )

    with patch("assurance.tools.release_gate.REPORT_DIR", tmp_path):
        result = evaluate_gate(run_id="test-run-3")

    assert "dependency" in result["blocking_gates"]
    assert result["gates"]["dependency"]["status"] == "FAIL"
    assert result["gates"]["dependency"]["npm_high"] == 1


def test_performance_slo_violation_blocks_performance_gate(tmp_path):
    """COMPASS-AUDIT-024: Benchmark metric exceeding justified SLO must block performance gate."""
    bench_file = tmp_path / "benchmark_comparison.json"
    # planning latency 2500ms > threshold 2000ms
    bench_file.write_text(
        json.dumps(
            {
                "comparison": [
                    {
                        "metric": "planning_latency_ms",
                        "baseline": 500.0,
                        "optimized": 2500.0,
                    },
                    {
                        "metric": "stop_latency_ms",
                        "baseline": 50.0,
                        "optimized": 100.0,
                    },
                ]
            }
        )
    )

    with patch(
        "assurance.tools.release_gate.ROOT_DIR", tmp_path
    ), patch(
        "assurance.tools.release_gate.REPORT_DIR", tmp_path
    ):
        # Create artifacts/phase14 directory
        p14_dir = tmp_path / "artifacts" / "phase14"
        p14_dir.mkdir(parents=True, exist_ok=True)
        (p14_dir / "benchmark_comparison.json").write_text(bench_file.read_text())

        result = evaluate_gate(run_id="test-run-4")

    assert "performance" in result["blocking_gates"]
    assert result["gates"]["performance"]["status"] == "FAIL"
    assert len(result["gates"]["performance"]["violations"]) > 0


def test_fully_passing_mandatory_gates_achieves_pass(tmp_path):
    """When all mandatory gates provide valid PASS evidence, release gate passes."""
    # Setup all passing reports in tmp_path
    p14_dir = tmp_path / "artifacts" / "phase14"
    p14_dir.mkdir(parents=True, exist_ok=True)
    (p14_dir / "phase14_master_report.json").write_text(
        json.dumps({"overall_status": "PASS", "stages": [{"success": True}]})
    )
    (p14_dir / "benchmark_comparison.json").write_text(
        json.dumps(
            {
                "comparison": [
                    {"metric": "planning_latency_ms", "optimized": 150.0},
                    {"metric": "stop_latency_ms", "optimized": 45.0},
                    {"metric": "database_op_latency_ms", "optimized": 12.0},
                    {"metric": "action_latency_ms", "optimized": 65.0},
                    {"metric": "e2e_single_step_latency_ms", "optimized": 80.0},
                ]
            }
        )
    )

    findings_file = tmp_path / "finding_register.json"
    findings_file.write_text(
        json.dumps(
            [{"finding_id": "F-1", "severity": "LOW", "status": "CLOSED"}]
        )
    )

    (tmp_path / "sast_report.json").write_text(
        json.dumps({"tools": {"bandit": {"status": "EXECUTED", "total_findings": 0}}})
    )
    (tmp_path / "dependency_report.json").write_text(
        json.dumps(
            {
                "tools": {
                    "pip_audit": {"vulnerable_packages": 0},
                    "npm_audit": {
                        "vulnerabilities_summary": {
                            "critical": 0,
                            "high": 0,
                            "moderate": 0,
                            "low": 0,
                        }
                    },
                }
            }
        )
    )
    (tmp_path / "secret_scan_report.json").write_text(
        json.dumps({"total_findings": 0})
    )
    (tmp_path / "api_security_report.json").write_text(
        json.dumps({"summary": {"passed": 10, "failed": 0}})
    )
    (tmp_path / "real_product_test_report.json").write_text(
        json.dumps({"suites": {"s1": [{"passed": True}]}})
    )

    with patch("assurance.tools.release_gate.ROOT_DIR", tmp_path), patch(
        "assurance.tools.release_gate.REPORT_DIR", tmp_path
    ), patch("assurance.tools.release_gate.FINDINGS_FILE", findings_file):
        result = evaluate_gate(run_id="test-run-5")

    assert result["overall_readiness"] == "PASS"
    assert result["blocking_gates"] == []
