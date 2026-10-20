"""
COMPASS Continuous Production Assurance — Finding Schema & Registry
Defines unified vulnerability, bug, and regression finding models with thread-safe atomic persistence.
Fail-closed corruption defense, atomic writes, and lifecycle guarantees (COMPASS-AUDIT-014).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
FINDINGS_DIR = ROOT_DIR / "assurance" / "findings"
FINDINGS_FILE = FINDINGS_DIR / "finding_register.json"


class FindingRegistryCorruptedError(RuntimeError):
    """Raised when the persistent finding registry contains invalid or corrupted data."""


@dataclass
class Finding:
    """Unified schema for all findings across static, dynamic, fuzz, and regression testing."""

    finding_id: str
    source_tool: str  # e.g., 'bandit', 'semgrep', 'pip_audit', 'fuzzer', 'regression'
    title: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    category: str  # 'SECURITY', 'RELIABILITY', 'PERFORMANCE', 'DATA_LOSS', 'REGRESSION'
    affected_component: str
    affected_file: str = ""
    line_number: int = 0
    rule_id: str = ""
    description: str = ""
    reproduction_steps: str = ""
    evidence: dict = field(default_factory=dict)
    remediation: str = ""
    status: str = "OPEN"  # 'OPEN', 'IN_PROGRESS', 'FIXED', 'RETESTED', 'CLOSED', 'REOPENED'
    verification_status: str = "UNVERIFIED"  # 'UNVERIFIED', 'VERIFIED', 'ACCEPTED_RISK'
    regression_test_id: str = ""
    re_attack_status: str = ""
    timestamp: float = field(default_factory=time.time)
    commit_hash: str = ""


class FindingRegistry:
    """Thread-safe, atomic finding management with persistent JSON storage."""

    SCHEMA_VERSION = "2.0"

    def __init__(self, findings_file: Path = FINDINGS_FILE):
        self._file = Path(findings_file)
        self._lock = threading.RLock()
        self._findings: list[Finding] = []
        self._load()

    def _load(self):
        with self._lock:
            if not self._file.exists():
                self._findings = []
                return

            try:
                raw_text = self._file.read_text(encoding="utf-8")
                if not raw_text.strip():
                    self._findings = []
                    return
                data = json.loads(raw_text)
                if not isinstance(data, list):
                    raise ValueError(f"Expected list of findings, got {type(data).__name__}")
                self._findings = [Finding(**f) for f in data]
            except Exception as e:
                # Quarantine corrupt file to preserve forensics
                quarantine_path = self._file.with_suffix(f".corrupt.{int(time.time())}.json")
                try:
                    shutil.copy2(self._file, quarantine_path)
                except Exception:
                    pass
                raise FindingRegistryCorruptedError(
                    f"Finding registry at '{self._file}' is corrupt: {e}. Quarantined to '{quarantine_path}'."
                ) from e

    def _save(self):
        with self._lock:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps([asdict(f) for f in self._findings], indent=2)
            
            # Atomic save: write to temporary file in same directory, then atomic replace
            tmp_file = self._file.with_suffix(f".tmp.{os.getpid()}.{threading.get_ident()}")
            try:
                tmp_file.write_text(payload, encoding="utf-8")
                # On Windows, replace will overwrite destination atomically
                os.replace(tmp_file, self._file)
            except Exception:
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)
                raise

    def _gen_id(self, tool: str, component: str, rule: str, line: int) -> str:
        raw = f"{tool}:{component}:{rule}:{line}:{time.time()}"
        return f"F-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"

    def add(self, **kwargs) -> Finding:
        with self._lock:
            if "finding_id" not in kwargs or not kwargs["finding_id"]:
                kwargs["finding_id"] = self._gen_id(
                    kwargs.get("source_tool", ""),
                    kwargs.get("affected_component", ""),
                    kwargs.get("rule_id", ""),
                    kwargs.get("line_number", 0),
                )
            f = Finding(**kwargs)
            # Duplicate and recurrence detection
            for existing in self._findings:
                if (
                    existing.source_tool == f.source_tool
                    and existing.affected_component == f.affected_component
                    and existing.rule_id == f.rule_id
                    and existing.line_number == f.line_number
                ):
                    if existing.status in ("CLOSED", "FIXED"):
                        # Recurrence detected: reopen existing finding
                        existing.status = "REOPENED"
                        existing.re_attack_status = "RECURRENCE_DETECTED"
                        existing.timestamp = time.time()
                        existing.evidence = f.evidence
                        self._save()
                        return existing
                    return existing  # Skip duplicate if already OPEN
            self._findings.append(f)
            self._save()
            return f

    def update_status(self, finding_id: str, status: str, **kwargs) -> Finding | None:
        with self._lock:
            for f in self._findings:
                if f.finding_id == finding_id:
                    # Closing verification gate
                    if status == "CLOSED":
                        reg_id = kwargs.get("regression_test_id", f.regression_test_id)
                        verif_st = kwargs.get("verification_status", f.verification_status)
                        if not reg_id and verif_st != "ACCEPTED_RISK":
                            raise ValueError(
                                f"Cannot close finding '{finding_id}' without regression_test_id or ACCEPTED_RISK verification."
                            )
                        if verif_st not in ("VERIFIED", "ACCEPTED_RISK"):
                            raise ValueError(
                                f"Cannot close finding '{finding_id}' with unverified status '{verif_st}'."
                            )

                    f.status = status
                    for k, v in kwargs.items():
                        if hasattr(f, k):
                            setattr(f, k, v)
                    self._save()
                    return f
            return None

    def get_all(self) -> list[Finding]:
        with self._lock:
            return list(self._findings)

    def get_by_severity(self, severity: str) -> list[Finding]:
        with self._lock:
            return [f for f in self._findings if f.severity == severity]

    def get_open(self) -> list[Finding]:
        with self._lock:
            return [f for f in self._findings if f.status in ("OPEN", "IN_PROGRESS", "REOPENED")]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._findings)
            by_sev = {}
            by_status = {}
            by_confidence = {}
            for f in self._findings:
                by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
                by_status[f.status] = by_status.get(f.status, 0) + 1
                by_confidence[f.confidence] = by_confidence.get(f.confidence, 0) + 1
            return {
                "total": total,
                "by_severity": by_sev,
                "by_status": by_status,
                "by_confidence": by_confidence,
                "open_critical": len(
                    [
                        f
                        for f in self._findings
                        if f.severity == "CRITICAL" and f.status in ("OPEN", "REOPENED")
                    ]
                ),
                "open_high": len(
                    [
                        f
                        for f in self._findings
                        if f.severity == "HIGH" and f.status in ("OPEN", "REOPENED")
                    ]
                ),
            }
