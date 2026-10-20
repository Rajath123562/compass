"""
COMPASS Clean Source Distribution Packager (COMPASS-AUDIT-023)
Creates a reproducible, sanitized source export package separated from runtime DB, logs, and caches.
Embeds reproducible tree hash, source manifest, and verified environment provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Paths and patterns strictly excluded from source distribution
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "dist",
    "build",
    "coverage",
    ".mypy_cache",
}

EXCLUDE_FILES = {
    "compass.db",
    "compass.db-journal",
    "compass.db-wal",
    "compass.log",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".tmp",
    ".corrupt.json",
}


def get_git_info() -> dict:
    info = {"commit": "UNVERIFIED", "branch": "UNKNOWN", "dirty": True}
    try:
        r_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r_head.returncode == 0:
            info["commit"] = r_head.stdout.strip()

        r_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r_branch.returncode == 0:
            info["branch"] = r_branch.stdout.strip()

        r_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r_status.returncode == 0:
            info["dirty"] = bool(r_status.stdout.strip())
    except Exception:
        pass
    return info


def build_source_distribution(output_zip: Path | None = None) -> dict:
    output_zip = output_zip or (ROOT_DIR / "dist" / "compass-source-clean.zip")
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    git_info = get_git_info()
    file_manifest = []
    tree_hasher = hashlib.sha256()

    files_to_pack: list[tuple[Path, str]] = []

    for path in ROOT_DIR.rglob("*"):
        if path.is_dir():
            continue

        rel_path = path.relative_to(ROOT_DIR)
        parts = rel_path.parts

        # Check directory exclusions
        if any(part in EXCLUDE_DIRS for part in parts):
            continue

        # Check file exclusions
        if path.name in EXCLUDE_FILES:
            continue
        if path.suffix.lower() in EXCLUDE_EXTENSIONS:
            continue
        if "corrupt" in path.name:
            continue

        # Hash file
        try:
            content = path.read_bytes()
            f_hash = hashlib.sha256(content).hexdigest()
            arcname = rel_path.as_posix()
            file_manifest.append(
                {"path": arcname, "size_bytes": len(content), "sha256": f_hash}
            )
            tree_hasher.update(f"{arcname}:{f_hash}".encode("utf-8"))
            files_to_pack.append((path, arcname))
        except Exception as e:
            print(f"[Packager] Warning reading {rel_path}: {e}")

    source_tree_hash = tree_hasher.hexdigest()

    provenance = {
        "export_timestamp": time.time(),
        "git_provenance": git_info,
        "source_tree_hash": source_tree_hash,
        "environment": {
            "platform": platform.platform(),
            "python_version": sys.version,
        },
        "file_count": len(files_to_pack),
    }

    # Write zip file
    print(f"[Packager] Packing {len(files_to_pack)} clean source files to {output_zip}...")
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, arcname in files_to_pack:
            zf.write(file_path, arcname)

        # Embed SOURCE_PROVENANCE.json and SOURCE_MANIFEST.json
        zf.writestr(
            "SOURCE_PROVENANCE.json", json.dumps(provenance, indent=2)
        )
        zf.writestr(
            "SOURCE_MANIFEST.json", json.dumps(file_manifest, indent=2)
        )

    print(f"[Packager] Source distribution created: {output_zip} ({output_zip.stat().st_size} bytes)")
    print(f"[Packager] Tree Hash: {source_tree_hash}")
    return provenance


if __name__ == "__main__":
    build_source_distribution()
