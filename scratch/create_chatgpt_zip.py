import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(".").resolve()
OUTPUT_ZIP = ROOT / "compass_project_for_chatgpt.zip"

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
    ".agents",
    "scratch",
}

EXCLUDE_FILES = {
    "compass.log",
    "compass.log.3",
    "compass.db-journal",
    "compass.db-wal",
    "project_complete_codebase.zip",
    "compass-source-clean.zip",
    "compass_project_for_chatgpt.zip",
    "test_db_zip.zip",
    "vacuum_test.db",
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

# Special handling for artifacts/checkpoints and artifacts/traces:
# We don't want 1,400 old temporary test files, but we DO want the directories to exist.

print(f"Building clean project zip: {OUTPUT_ZIP.name}...")

packed_files = []
total_uncompressed = 0

with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for root, dirs, files in os.walk(ROOT):
        # Prune excluded dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        rel_root = Path(root).relative_to(ROOT)
        parts = rel_root.parts
        
        # Check if under excluded dir
        if any(p in EXCLUDE_DIRS for p in parts):
            continue
            
        # Check if inside artifacts/checkpoints or artifacts/traces
        if len(parts) >= 2 and parts[0] == "artifacts" and parts[1] in ("checkpoints", "traces"):
            # Skip old checkpoint files, only place a .gitkeep if empty
            continue
        
        for f in files:
            if f in EXCLUDE_FILES or any(f.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                continue
            
            file_path = Path(root) / f
            arcname = file_path.relative_to(ROOT).as_posix()
            
            try:
                sz = file_path.stat().st_size
                zf.write(file_path, arcname)
                packed_files.append((arcname, sz))
                total_uncompressed += sz
            except Exception as e:
                print(f"Error packing {arcname}: {e}")

    # Ensure empty checkpoint & trace directories exist via .gitkeep
    zf.writestr("artifacts/checkpoints/.gitkeep", "")
    zf.writestr("artifacts/traces/.gitkeep", "")

zip_size = OUTPUT_ZIP.stat().st_size
print("\n" + "=" * 60)
print(f"SUCCESS: {OUTPUT_ZIP.name} created successfully!")
print(f"Total packed files:     {len(packed_files)}")
print(f"Uncompressed size:      {total_uncompressed / (1024*1024):.2f} MB")
print(f"Compressed zip size:    {zip_size / (1024*1024):.2f} MB ({zip_size:,} bytes)")
print("=" * 60)

# Summary of top-level folders packed
folder_summary = {}
for arcname, sz in packed_files:
    top = arcname.split("/")[0] if "/" in arcname else "<root>"
    folder_summary[top] = folder_summary.get(top, [0, 0])
    folder_summary[top][0] += 1
    folder_summary[top][1] += sz

print("\nPackaged Subsystems Breakdown:")
for k, (cnt, sz) in sorted(folder_summary.items(), key=lambda x: x[1][1], reverse=True):
    print(f"  {k:<20}: {cnt:>4} files, {sz/(1024*1024):>6.2f} MB")
