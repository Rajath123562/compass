"""
COMPASS Phase 11 — Dynamic Repository Inventory Generator
Dynamically scans and categorizes all source code, tests, scripts, frontend assets,
and documentation in the repository.
"""

import ast
import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "artifacts",
    "dist",
    "build",
}


def analyze_python_file(filepath: Path) -> dict[str, Any]:
    """Parse python file to count lines, functions, classes, and test cases."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    lines = len(text.splitlines())
    functions = 0
    classes = 0
    test_functions = 0

    try:
        tree = ast.parse(text, filename=str(filepath))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
                if node.name.startswith("test_"):
                    test_functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
    except Exception:  # noqa: BLE001, S110
        pass

    return {
        "file": str(filepath.relative_to(ROOT_DIR)).replace("\\", "/"),
        "lines": lines,
        "functions": functions,
        "classes": classes,
        "test_functions": test_functions,
    }


def generate_inventory() -> dict[str, Any]:
    inventory = {
        "backend": [],
        "planner": [],
        "perception": [],
        "automation": [],
        "overlay": [],
        "providers": [],
        "scripts": [],
        "docs": [],
        "frontend": [],
        "tests": [],
    }

    summary = {
        "total_files": 0,
        "total_lines_of_code": 0,
        "python_files_count": 0,
        "test_files_count": 0,
        "test_functions_count": 0,
        "markdown_files_count": 0,
        "frontend_files_count": 0,
    }

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            p = Path(root) / f
            rel = p.relative_to(ROOT_DIR)
            rel_str = str(rel).replace("\\", "/")
            parts = rel.parts
            top_dir = parts[0]

            summary["total_files"] += 1

            if p.suffix == ".py":
                analysis = analyze_python_file(p)
                summary["python_files_count"] += 1
                summary["total_lines_of_code"] += analysis["lines"]

                if "tests" in parts or f.startswith("test_") or f.endswith("_test.py"):
                    summary["test_files_count"] += 1
                    summary["test_functions_count"] += analysis["test_functions"]
                    inventory["tests"].append(analysis)
                elif top_dir in inventory:
                    inventory[top_dir].append(analysis)
                else:
                    inventory["backend"].append(analysis)
            elif p.suffix == ".md":
                summary["markdown_files_count"] += 1
                lines = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                inventory["docs"].append({"file": rel_str, "lines": lines})
            elif top_dir == "frontend" or p.suffix in (
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".css",
                ".html",
            ):
                summary["frontend_files_count"] += 1
                lines = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                inventory["frontend"].append({"file": rel_str, "lines": lines})

    result = {"summary": summary, "inventory": inventory}

    out_file = ROOT_DIR / "artifacts" / "phase11" / "repository_inventory.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2)

    print("=" * 75)
    print("  COMPASS Phase 11 — Dynamic Repository Inventory Summary")
    print("=" * 75)
    print(f"  Total Tracked Files:     {summary['total_files']}")
    print(f"  Total Lines of Python:   {summary['total_lines_of_code']}")
    print(f"  Python Files:            {summary['python_files_count']}")
    print(f"  Test Files:              {summary['test_files_count']}")
    print(f"  Test Functions Found:    {summary['test_functions_count']}")
    print(f"  Markdown Documents:      {summary['markdown_files_count']}")
    print(f"  Frontend Files:          {summary['frontend_files_count']}")
    print(f"  Inventory JSON saved to: {out_file}")
    print("=" * 75)
    return result


if __name__ == "__main__":
    generate_inventory()
