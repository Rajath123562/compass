#!/usr/bin/env python3
"""COMPASS Line-by-Line AST, Duplicate Module, Shadow Binary & Artifact Auditor."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}

DUPLICATE_PAIRS: List[Tuple[str, str]] = [
    ("planner/workflow_dag.py", "planner/workflow/dag.py"),
    ("planner/workflow_models.py", "planner/workflow/models.py"),
    ("planner/workflow_orchestrator.py", "planner/workflow/orchestrator.py"),
    ("planner/workflow_scheduler.py", "planner/workflow/scheduler.py"),
    ("planner/recovery_engine.py", "planner/workflow/recovery.py"),
    ("perception/capture.py", "perception/screen_capture.py"),
    ("perception/ocr.py", "perception/ocr_engine.py"),
    ("perception/mapping.py", "perception/coordinate_mapper.py"),
    ("perception/fusion.py", "perception/evidence_fusion.py"),
    ("perception/service.py", "perception/multimodal_service.py"),
    ("perception/security.py", "perception/perception_security.py"),
    ("perception/temporal.py", "perception/temporal_comparator.py"),
    ("perception/models.py", "perception/models_multimodal.py"),
]

FORBIDDEN_SHADOW_FILES = [
    "frontend/powershell.cmd",
    "assurance/notepad.exe",
    "windows.json",
]


def iter_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for dpath, dnames, fnames in os.walk(root):
        dnames[:] = [d for d in dnames if d not in EXCLUDED_DIRS]
        for f in sorted(fnames):
            out.append(Path(dpath) / f)
    return out


def scan_python_ast(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    rel = path.relative_to(ROOT).as_posix()
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": rel, "line": 1, "severity": "P0", "type": "READ_ERROR", "detail": str(e)}]

    for idx, line in enumerate(src.splitlines(), start=1):
        s = line.strip()
        if "shell=True" in s and not rel.endswith("deep_line_by_line_audit.py") and not rel.endswith("populate_findings.py"):
            issues.append({"file": rel, "line": idx, "severity": "P0", "type": "SHELL_TRUE", "detail": s[:120]})

        if ("pickle.load" in s or "pickle.loads" in s) and "test" not in rel and not rel.endswith("deep_line_by_line_audit.py"):
            issues.append({"file": rel, "line": idx, "severity": "P0", "type": "UNSAFE_PICKLE", "detail": s[:120]})

    try:
        tree = ast.parse(src, filename=rel)
    except SyntaxError as e:
        issues.append({"file": rel, "line": e.lineno or 1, "severity": "P0", "type": "SYNTAX_ERROR", "detail": str(e)})
        return issues

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append({"file": rel, "line": node.lineno, "severity": "P2", "type": "BARE_EXCEPT", "detail": "Bare except:"})
            elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                issues.append({"file": rel, "line": node.lineno, "severity": "P2", "type": "SILENT_EXCEPT_PASS", "detail": "except ...: pass"})
    return issues


def png_dims(path: Path) -> Tuple[int, int]:
    b = path.read_bytes()
    if len(b) >= 24 and b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR":
        return struct.unpack(">II", b[16:24])
    return -1, -1


def scan_repo() -> List[Dict[str, Any]]:
    files = iter_files(ROOT)
    issues: List[Dict[str, Any]] = []
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        if rel in FORBIDDEN_SHADOW_FILES:
            issues.append({"file": rel, "line": 1, "severity": "P0", "type": "FORBIDDEN_SHADOW_OR_EMPTY_FILE", "detail": rel})
        if f.suffix == ".py":
            issues.extend(scan_python_ast(f))
        elif f.suffix.lower() == ".png" and rel.startswith("artifacts/"):
            w, h = png_dims(f)
            if 0 <= w <= 2 or 0 <= h <= 2:
                issues.append({"file": rel, "line": 1, "severity": "P1", "type": "DUMMY_1X1_PNG", "detail": f"{w}x{h}"})
        elif f.suffix.lower() == ".json" and rel.startswith("artifacts/"):
            txt = f.read_text(encoding="utf-8", errors="replace").strip()
            if txt in ("{}", "[]", ""):
                issues.append({"file": rel, "line": 1, "severity": "P1", "type": "EMPTY_ARTIFACT_JSON", "detail": txt})
        elif f.suffix.lower() == ".md" and rel.startswith("docs/"):
            txt = f.read_text(encoding="utf-8", errors="replace").strip()
            if len(txt.splitlines()) <= 3 or len(txt) < 120:
                issues.append({"file": rel, "line": 1, "severity": "P2", "type": "STUB_DOC", "detail": f"{len(txt)} chars"})

    for left_rel, right_rel in DUPLICATE_PAIRS:
        lp, rp = ROOT / left_rel, ROOT / right_rel
        if lp.exists() and rp.exists():
            ls, rs = lp.read_text(encoding="utf-8", errors="replace"), rp.read_text(encoding="utf-8", errors="replace")
            if hashlib.sha256(ls.encode()).hexdigest() != hashlib.sha256(rs.encode()).hexdigest():
                if "import *" not in ls and "import *" not in rs:
                    issues.append({
                        "file": f"{left_rel} <-> {right_rel}", "line": 1, "severity": "P1",
                        "type": "UNCONSOLIDATED_DUPLICATE", "detail": f"{len(ls)}B vs {len(rs)}B"
                    })
    return issues


if __name__ == "__main__":
    all_issues = scan_repo()
    out_file = ROOT / "artifacts" / "deep_line_by_line_audit_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps({"count": len(all_issues), "issues": all_issues}, indent=2), encoding="utf-8")
    p0_p1 = [i for i in all_issues if i["severity"] in ("P0", "P1")]
    print(f"Total issues: {len(all_issues)} | P0/P1 issues: {len(p0_p1)}")
    for item in p0_p1[:30]:
        print(f"  [{item['severity']}] {item['file']}:{item['line']} {item['type']} ({item['detail']})")
    sys.exit(1 if p0_p1 else 0)
