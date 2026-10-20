import os
import shutil
import subprocess
import zipfile
from pathlib import Path

test_dir = Path("scratch/test_unzip")
if test_dir.exists():
    shutil.rmtree(test_dir)
test_dir.mkdir(parents=True)

print("1. Extracting compass_project_for_chatgpt.zip into scratch/test_unzip...")
with zipfile.ZipFile("compass_project_for_chatgpt.zip", "r") as zf:
    zf.extractall(test_dir)

print(f"2. Extracted {len(list(test_dir.rglob('*')))} items successfully.")

print("3. Running verification script inside extracted project...")
res = subprocess.run(
    ["python", "-c", "import chatgpt_run_all_tests as c; c.test_database_integrity(); c.test_core_imports(); c.test_dag_workflow_engine(); c.test_risk_classifier()"],
    cwd=str(test_dir),
    capture_output=True,
    text=True
)
print("Output:\n", res.stdout)
if res.stderr:
    print("Stderr:\n", res.stderr)
print(f"Exit code: {res.returncode}")

# Clean up test_unzip
shutil.rmtree(test_dir)
print("4. Test extracted sandbox cleaned up.")
