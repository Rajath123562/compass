import os
from pathlib import Path

ROOT = Path(".")

# Directories to exclude
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".git",
    "dist",
    "build",
    "coverage",
    ".kilo",
    ".agents",  # contains IDE agent metadata, not part of source app
}

# Files to exclude
EXCLUDE_FILES = {
    "compass.log",
    "compass.log.3",
    "compass.db-journal",
    "compass.db-wal",
    "project_complete_codebase.zip",
    "test_db_zip.zip",
    "$null",
    "0]",
    "6}",
    "{p.name()}",
    "{",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".tmp",
    ".corrupt.json",
}

included_files = []
total_bytes = 0

for root, dirs, files in os.walk("."):
    # Filter dirs in-place
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    
    for f in files:
        if f in EXCLUDE_FILES or any(f.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
            continue
        # Also skip stray checkpoints if they are excessive, let's see how many files they are
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, ".")
        parts = Path(rel).parts
        if any(p in EXCLUDE_DIRS for p in parts):
            continue
        try:
            sz = os.path.getsize(fp)
            included_files.append((rel, sz))
            total_bytes += sz
        except Exception:
            pass

print(f"Total included files: {len(included_files)}")
print(f"Total uncompressed size: {total_bytes / (1024*1024):.2f} MB")

# Breakdown by top-level folder
folders = {}
for rel, sz in included_files:
    top = rel.split(os.sep)[0] if os.sep in rel else "<root>"
    folders[top] = folders.get(top, [0, 0])
    folders[top][0] += 1
    folders[top][1] += sz

print("\nBreakdown by top-level folder:")
for k, (cnt, sz) in sorted(folders.items(), key=lambda x: x[1][1], reverse=True):
    print(f"  {k:<20}: {cnt:>5} files, {sz/(1024*1024):>6.2f} MB")
