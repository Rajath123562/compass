"""
COMPASS Continuous Production Assurance — Application Inventory Builder
Automatically discovers and documents code, dependencies, interfaces, runtime
components, and attack surface from the actual repository.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

PYTHON_EXE = (
    str(ROOT_DIR / ".venv" / "Scripts" / "python.exe")
    if (ROOT_DIR / ".venv" / "Scripts" / "python.exe").exists()
    else sys.executable
)
REPORT_DIR = ROOT_DIR / "assurance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def discover_python_files() -> list[dict]:
    """Discover all Python source files excluding venv and cache."""
    files = []
    for p in ROOT_DIR.rglob("*.py"):
        rel = str(p.relative_to(ROOT_DIR))
        if any(
            skip in rel for skip in [".venv", "__pycache__", "node_modules", ".git"]
        ):
            continue
        try:
            size = p.stat().st_size
            content = p.read_text(encoding="utf-8", errors="ignore")
            line_count = content.count("\n") + 1
        except Exception:  # noqa: BLE001
            size, line_count = 0, 0
        files.append(
            {
                "path": rel,
                "size_bytes": size,
                "lines": line_count,
                "is_test": "test_" in p.name or "/tests/" in rel.replace("\\", "/"),
            }
        )
    return files


def discover_js_files() -> list[dict]:
    """Discover JavaScript/JSX/CSS frontend files."""
    files = []
    frontend_dir = ROOT_DIR / "frontend" / "src"
    if not frontend_dir.exists():
        return files
    for p in frontend_dir.rglob("*"):
        if p.is_file() and p.suffix in (".js", ".jsx", ".ts", ".tsx", ".css"):
            rel = str(p.relative_to(ROOT_DIR))
            files.append({"path": rel, "size_bytes": p.stat().st_size})
    return files


def discover_api_endpoints() -> list[dict]:
    """Parse FastAPI routers to discover API endpoints."""
    endpoints = []
    routers_dir = ROOT_DIR / "backend" / "app" / "routers"
    if not routers_dir.exists():
        return endpoints

    endpoint_re = re.compile(
        r'@(?:router|app)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    for f in routers_dir.glob("*.py"):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            for m in endpoint_re.finditer(content):
                method = m.group(1).upper()
                path = m.group(2)
                endpoints.append(
                    {
                        "method": method,
                        "path": path,
                        "source_file": str(f.relative_to(ROOT_DIR)),
                    }
                )
        except Exception:  # noqa: BLE001, S110
            pass

    # Also check main.py for root endpoints
    main_py = ROOT_DIR / "backend" / "app" / "main.py"
    if main_py.exists():
        try:
            content = main_py.read_text(encoding="utf-8", errors="ignore")
            for m in endpoint_re.finditer(content):
                endpoints.append(
                    {
                        "method": m.group(1).upper(),
                        "path": m.group(2),
                        "source_file": "backend/app/main.py",
                    }
                )
        except Exception:  # noqa: BLE001, S110
            pass

    return endpoints


def discover_sse_endpoints() -> list[dict]:
    """Find SSE (Server-Sent Events) streaming endpoints."""
    sse_eps = []
    for p in ROOT_DIR.rglob("*.py"):
        rel = str(p.relative_to(ROOT_DIR))
        if any(skip in rel for skip in [".venv", "__pycache__", "node_modules"]):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            if "EventSourceResponse" in content or "text/event-stream" in content:
                sse_eps.append({"source_file": rel})
        except Exception:  # noqa: BLE001, S110
            pass
    return sse_eps


def discover_python_dependencies() -> list[dict]:
    """Parse requirements.txt and check installed versions."""
    deps = []
    req_file = ROOT_DIR / "requirements.txt"
    if not req_file.exists():
        return deps

    try:
        pip_list = subprocess.run(  # noqa: PLW1510
            [PYTHON_EXE, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        installed = {}
        if pip_list.returncode == 0:
            for pkg in json.loads(pip_list.stdout):
                installed[pkg["name"].lower()] = pkg["version"]
    except Exception:  # noqa: BLE001
        installed = {}

    for line in req_file.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Parse "package>=version"
        match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*(.*)", line)
        if match:
            name = match.group(1)
            constraint = match.group(2)
            inst_ver = installed.get(name.lower().replace("-", "-"), "UNKNOWN")
            deps.append(
                {
                    "name": name,
                    "constraint": constraint,
                    "installed_version": inst_ver,
                    "runtime": True,
                }
            )
    return deps


def discover_node_dependencies() -> list[dict]:
    """Parse frontend/package.json dependencies."""
    deps = []
    pkg_file = ROOT_DIR / "frontend" / "package.json"
    if not pkg_file.exists():
        return deps
    try:
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
        for name, ver in pkg.get("dependencies", {}).items():
            deps.append({"name": name, "version": ver, "type": "runtime"})
        for name, ver in pkg.get("devDependencies", {}).items():
            deps.append({"name": name, "version": ver, "type": "dev"})
    except Exception:  # noqa: BLE001, S110
        pass
    return deps


def discover_dangerous_patterns() -> list[dict]:
    """Find potentially dangerous code patterns for attack surface analysis."""
    patterns = [
        (
            r"\bsubprocess\.(run|Popen|call|check_output|check_call)\b",
            "subprocess_execution",
            "HIGH",
        ),
        (r"\bos\.system\b", "os_system_call", "HIGH"),
        (r"\beval\b\s*\(", "eval_call", "CRITICAL"),
        (r"\bexec\b\s*\(", "exec_call", "CRITICAL"),
        (r"\bpickle\.loads?\b", "unsafe_deserialization", "HIGH"),
        (r"\bsqlite3\.connect\b", "database_connection", "MEDIUM"),
        (r"\bopen\s*\(", "file_operation", "LOW"),
        (r"ctypes\.\w+", "ctypes_usage", "MEDIUM"),
        (r"comtypes\.\w+", "com_interaction", "MEDIUM"),
        (r"\bshell\s*=\s*True\b", "shell_injection_risk", "HIGH"),
        (r"requests?\.(get|post|put|delete|patch)\b", "http_request", "MEDIUM"),
        (r"httpx\.\w+", "http_client", "MEDIUM"),
        (r"webbrowser\.open", "browser_launch", "MEDIUM"),
    ]
    findings = []
    for p in ROOT_DIR.rglob("*.py"):
        rel = str(p.relative_to(ROOT_DIR))
        if any(
            skip in rel for skip in [".venv", "__pycache__", "node_modules", ".git"]
        ):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for line_num, line in enumerate(content.splitlines(), 1):
                for pat, cat, sev in patterns:
                    if re.search(pat, line):
                        findings.append(
                            {
                                "file": rel,
                                "line": line_num,
                                "pattern": cat,
                                "severity": sev,
                                "snippet": line.strip()[:120],
                            }
                        )
        except Exception:  # noqa: BLE001, S110
            pass
    return findings


def build_attack_surface() -> dict:
    """Assemble the complete application attack surface."""
    return {
        "api_endpoints": discover_api_endpoints(),
        "sse_endpoints": discover_sse_endpoints(),
        "dangerous_code_patterns": discover_dangerous_patterns(),
        "external_interfaces": [
            {"type": "REST API", "port": 8000, "bind": "127.0.0.1"},
            {"type": "Vite Dev Server", "port": 5173, "bind": "127.0.0.1"},
            {"type": "Windows UIA COM IPC", "protocol": "out-of-process COM"},
            {"type": "Win32 SendInput", "protocol": "kernel32"},
            {"type": "SQLite Database", "protocol": "file"},
            {"type": "Subprocess (notepad, calc, etc.)", "protocol": "CreateProcess"},
        ],
    }


def build_inventory() -> dict:
    """Build the complete application inventory."""
    print("[Inventory] Discovering Python source files...")
    py_files = discover_python_files()
    print(
        f"  Found {len(py_files)} Python files ({sum(1 for f in py_files if f['is_test'])} test files)"
    )

    print("[Inventory] Discovering JavaScript/React files...")
    js_files = discover_js_files()
    print(f"  Found {len(js_files)} frontend files")

    print("[Inventory] Discovering API endpoints...")
    api_eps = discover_api_endpoints()
    print(f"  Found {len(api_eps)} API endpoints")

    print("[Inventory] Discovering SSE endpoints...")
    sse_eps = discover_sse_endpoints()
    print(f"  Found {len(sse_eps)} SSE-capable files")

    print("[Inventory] Discovering Python dependencies...")
    py_deps = discover_python_dependencies()
    print(f"  Found {len(py_deps)} Python packages")

    print("[Inventory] Discovering Node dependencies...")
    node_deps = discover_node_dependencies()
    print(f"  Found {len(node_deps)} Node packages")

    print("[Inventory] Building attack surface map...")
    attack_surface = build_attack_surface()
    print(
        f"  Found {len(attack_surface['dangerous_code_patterns'])} dangerous code patterns"
    )

    inventory = {
        "timestamp": time.time(),
        "repository_root": str(ROOT_DIR),
        "code": {
            "python_files": py_files,
            "python_source_count": len([f for f in py_files if not f["is_test"]]),
            "python_test_count": len([f for f in py_files if f["is_test"]]),
            "python_total_lines": sum(f["lines"] for f in py_files),
            "javascript_files": js_files,
        },
        "dependencies": {
            "python": py_deps,
            "node": node_deps,
        },
        "interfaces": {
            "api_endpoints": api_eps,
            "sse_endpoints": sse_eps,
        },
        "subsystems": [
            {
                "name": "backend",
                "type": "FastAPI REST API",
                "entry": "backend/app/main.py",
            },
            {
                "name": "frontend",
                "type": "React + Vite SPA",
                "entry": "frontend/src/App.jsx",
            },
            {
                "name": "planner",
                "type": "AI Task Planner & Orchestrator",
                "entry": "planner/execution_engine.py",
            },
            {
                "name": "perception",
                "type": "Windows UIA + OCR + Screen Capture",
                "entry": "perception/uia_inspector.py",
            },
            {
                "name": "automation",
                "type": "Win32 Action Dispatch (keyboard/mouse)",
                "entry": "automation/action_dispatcher.py",
            },
            {"name": "overlay", "type": "PySide6 Desktop Overlay", "entry": "overlay/"},
            {
                "name": "providers",
                "type": "AI/LLM Provider Abstraction (OmniRoute)",
                "entry": "providers/omniroute_provider.py",
            },
            {
                "name": "database",
                "type": "SQLite WAL",
                "entry": "backend/app/database.py",
            },
        ],
        "attack_surface": attack_surface,
    }

    out_file = REPORT_DIR / "application_inventory.json"
    out_file.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"\n[Inventory] Saved to: {out_file}")
    return inventory


if __name__ == "__main__":
    build_inventory()
