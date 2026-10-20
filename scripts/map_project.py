import ast
import os


def get_ast_info(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)

        classes = []
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
        return {"classes": classes, "functions": functions}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


project_map = {}
for root, dirs, files in os.walk("."):
    dirs[:] = [
        d
        for d in dirs
        if d
        not in {
            ".git",
            ".venv",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
            "docs",
            "scratch",
            "artifacts",
        }
    ]
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            project_map[full_path] = get_ast_info(full_path)

# Update MODULES.md
modules_content = (
    "# Modules\n\nThis document outlines the core modules of the COMPASS project.\n\n"
)
for path, info in project_map.items():
    if "error" not in info and (info["classes"] or info["functions"]):
        modules_content += f"## `{path}`\n"
        if info["classes"]:
            modules_content += "**Classes:**\n"
            for c in info["classes"]:
                modules_content += f"- `{c}`\n"
        if info["functions"]:
            modules_content += "**Functions:**\n"
            for f in info["functions"]:
                modules_content += f"- `{f}`\n"
        modules_content += "\n"

with open("docs/MODULES.md", "w", encoding="utf-8") as f:
    f.write(modules_content)

# Update PROJECT_OVERVIEW.md
overview = """# Project Overview: COMPASS

COMPASS is an AI-based system designed to guide users step-by-step through complex digital interfaces. It includes a frontend overlay, backend APIs, and several core engines:
- **Planner**: Handles multi-step verifications, state reconciliation, and orchestration.
- **Perception**: Interacts with the OS (Windows) and parses UI components.
- **Automation**: Coordinates UI automation actions safely.
- **Storage**: SQLite WAL database for resilience.

## Codebase Organization
The project is strictly organized to allow agents to easily ingest and resolve errors:
1. `backend/`: Fastapi server and core APIs.
2. `frontend/`: React components.
3. `planner/`: Core logic for DAG workflows and execution.
4. `perception/`: Vision and UI trees.
5. `automation/`: Action dispatchers.
6. `docs/`: Comprehensive agent-readable documentation suite.

*Optimized for production and AI readability.*
"""
with open("docs/PROJECT_OVERVIEW.md", "w", encoding="utf-8") as f:
    f.write(overview)

# Update ARCHITECTURE.md
arch = """# Architecture

## Core Flow
1. **Goal Input** -> Target Resolution (Heuristics + AI)
2. **Context Builder** -> Parses current state from `perception/`
3. **Planning** -> AI model creates TaskPlan.
4. **Execution** -> Sent via DAG workflow to `automation/`.
5. **Verification** -> 6-point live tree check.

## Data Flow
- In-memory checks backed up by SQLite WAL (`compass.db`).
"""
with open("docs/ARCHITECTURE.md", "w", encoding="utf-8") as f:
    f.write(arch)

print("Documentation mapping complete.")
