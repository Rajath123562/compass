"""
COMPASS Finding Registry Tests (COMPASS-AUDIT-014)
Validates corruption defense, atomic writes, recurrence, thread safety, and closure verification.
"""

from __future__ import annotations

import concurrent.futures
import json
import threading
from pathlib import Path

import pytest

from assurance.finding_schema import (
    Finding,
    FindingRegistry,
    FindingRegistryCorruptedError,
)


def test_corrupt_registry_quarantines_and_raises(tmp_path):
    """Corrupt JSON in finding registry must raise FindingRegistryCorruptedError and quarantine."""
    bad_file = tmp_path / "finding_register.json"
    bad_file.write_text("{ this is not valid json : [", encoding="utf-8")

    with pytest.raises(FindingRegistryCorruptedError):
        FindingRegistry(findings_file=bad_file)

    # Check that quarantine file was created
    quarantines = list(tmp_path.glob("finding_register.corrupt.*.json"))
    assert len(quarantines) == 1
    assert quarantines[0].read_text(encoding="utf-8") == "{ this is not valid json : ["


def test_cannot_close_without_regression_test_and_verification(tmp_path):
    """Closing a finding without regression_test_id and VERIFIED status must be rejected."""
    reg_file = tmp_path / "finding_register.json"
    reg = FindingRegistry(findings_file=reg_file)

    f = reg.add(
        source_tool="bandit",
        affected_component="core",
        rule_id="B101",
        line_number=10,
        title="Assert used",
        severity="LOW",
        confidence="HIGH",
        category="SECURITY",
    )

    # Try closing without regression test ID
    with pytest.raises(ValueError, match="regression_test_id"):
        reg.update_status(f.finding_id, status="CLOSED", verification_status="UNVERIFIED")

    # Try closing with test ID but UNVERIFIED status
    with pytest.raises(ValueError, match="unverified status"):
        reg.update_status(
            f.finding_id,
            status="CLOSED",
            regression_test_id="test_no_asserts",
            verification_status="UNVERIFIED",
        )

    # Valid close with both
    updated = reg.update_status(
        f.finding_id,
        status="CLOSED",
        regression_test_id="test_no_asserts",
        verification_status="VERIFIED",
    )
    assert updated is not None
    assert updated.status == "CLOSED"


def test_recurrence_reopens_closed_finding(tmp_path):
    """Re-detecting a defect that was previously CLOSED reopens it with RECURRENCE_DETECTED."""
    reg_file = tmp_path / "finding_register.json"
    reg = FindingRegistry(findings_file=reg_file)

    f = reg.add(
        source_tool="bandit",
        affected_component="auth",
        rule_id="B105",
        line_number=25,
        title="Hardcoded password",
        severity="HIGH",
        confidence="HIGH",
        category="SECURITY",
    )
    reg.update_status(
        f.finding_id,
        status="CLOSED",
        regression_test_id="test_auth_creds",
        verification_status="VERIFIED",
    )
    assert reg.get_all()[0].status == "CLOSED"

    # Re-detect the same defect
    re_added = reg.add(
        source_tool="bandit",
        affected_component="auth",
        rule_id="B105",
        line_number=25,
        title="Hardcoded password",
        severity="HIGH",
        confidence="HIGH",
        category="SECURITY",
    )
    assert re_added.finding_id == f.finding_id
    assert re_added.status == "REOPENED"
    assert re_added.re_attack_status == "RECURRENCE_DETECTED"


def test_concurrent_writes_are_thread_safe(tmp_path):
    """Concurrent additions to FindingRegistry preserve all records without data loss."""
    reg_file = tmp_path / "finding_register.json"
    reg = FindingRegistry(findings_file=reg_file)

    def worker(idx: int):
        reg.add(
            source_tool=f"tool_{idx}",
            affected_component=f"comp_{idx}",
            rule_id=f"R{idx}",
            line_number=idx,
            title=f"Finding {idx}",
            severity="LOW",
            confidence="MEDIUM",
            category="RELIABILITY",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(30)]
        concurrent.futures.wait(futures)

    # Reload from disk to verify persistence
    reloaded = FindingRegistry(findings_file=reg_file)
    assert len(reloaded.get_all()) == 30
