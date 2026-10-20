import os
import zipfile
import hashlib
import tempfile
import sys

def create_backup():
    project_root = r"c:\Users\RAJATH U\Downloads\personal assitant"
    backup_zip = r"c:\Users\RAJATH U\Downloads\compass_backup_verified_20261018.zip"

    EXCLUDE_DIRS = {
        ".git", "node_modules", ".venv", "venv", "__pycache__", 
        ".pytest_cache", "scratch", "test-results", ".mypy_cache",
        "dist", ".cache"
    }
    EXCLUDE_EXTS = {".pyc", ".pyo", ".pyd"}

    print("Starting backup creation...")
    file_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(backup_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, project_root)
                # Skip backup if inside root somehow
                if os.path.abspath(full_path) == os.path.abspath(backup_zip):
                    continue
                zf.write(full_path, arcname=rel_path)
                file_count += 1
                total_uncompressed_bytes += os.path.getsize(full_path)

    zip_size = os.path.getsize(backup_zip)

    # Compute SHA-256
    sha256 = hashlib.sha256()
    with open(backup_zip, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256.update(chunk)
    digest = sha256.hexdigest()

    print("Backup created successfully!")
    print(f"Destination: {backup_zip}")
    print(f"Files archived: {file_count}")
    print(f"Uncompressed size: {total_uncompressed_bytes / (1024 * 1024):.2f} MB")
    print(f"Zip size: {zip_size / (1024 * 1024):.2f} MB")
    print(f"SHA-256: {digest}")

    # Test verification / extraction
    print("Verifying archive integrity and extraction in temporary directory...")
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(backup_zip, "r") as zf:
            test_res = zf.testzip()
            if test_res is not None:
                raise RuntimeError(f"Corrupt file detected in archive: {test_res}")
            zf.extractall(tmpdir)
        extracted_count = sum(len(files) for _, _, files in os.walk(tmpdir))
        print(f"Extracted {extracted_count} files successfully into temp directory without errors.")
        assert extracted_count == file_count, f"Extracted count {extracted_count} != archived count {file_count}"

    print("Backup integrity verification: PASSED (100% restorable)")
    return {
        "path": backup_zip,
        "files": file_count,
        "uncompressed_mb": total_uncompressed_bytes / (1024 * 1024),
        "zip_mb": zip_size / (1024 * 1024),
        "sha256": digest
    }

if __name__ == "__main__":
    create_backup()
