"""
COMPASS — Environment Validation Script
Validates all Phase 1 environment requirements on Windows 11.
"""

import importlib.util
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pytest",
    "httpx",
    "requests",
    "psutil",
    "PySide6",
    "sqlite3",
]

DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_PORT = 5173


def check_os():
    system = platform.system()
    release = platform.release()
    version = platform.version()
    is_windows = system.lower() == "windows"
    return {
        "name": "Operating System",
        "passed": is_windows,
        "detail": f"{system} {release} (build {version})",
        "required": "Windows 10/11",
    }


def check_python():
    v = sys.version_info
    passed = v.major == 3 and v.minor >= 10
    return {
        "name": "Python Version",
        "passed": passed,
        "detail": f"{v.major}.{v.minor}.{v.micro} ({sys.executable})",
        "required": "Python >= 3.10",
    }


def check_node():
    node_found = False
    node_ver = "not found"
    try:
        res = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            node_found = True
            node_ver = res.stdout.strip()
    except Exception as e:  # noqa: BLE001
        node_ver = str(e)
    return {
        "name": "Node.js",
        "passed": node_found,
        "detail": node_ver,
        "required": "Node.js >= 18",
    }


def check_npm():
    npm_found = False
    npm_ver = "not found"
    try:
        npm_bin = shutil.which("npm") or shutil.which("npm.cmd") or "npm.cmd"
        res = subprocess.run(
            [npm_bin, "--version"], capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            npm_found = True
            npm_ver = res.stdout.strip()
    except Exception as e:  # noqa: BLE001
        npm_ver = str(e)
    return {
        "name": "npm Package Manager",
        "passed": npm_found,
        "detail": npm_ver,
        "required": "npm >= 9",
    }


def check_python_packages():
    missing = []
    found = []
    for pkg in REQUIRED_PACKAGES:
        if pkg == "sqlite3":
            try:
                import sqlite3

                found.append(f"sqlite3 (SQLite {sqlite3.sqlite_version})")
            except ImportError:
                missing.append("sqlite3")
        else:
            spec = importlib.util.find_spec(pkg)
            if spec is not None:
                try:
                    mod = __import__(pkg)
                    ver = getattr(mod, "__version__", "installed")
                    found.append(f"{pkg}=={ver}")
                except Exception:  # noqa: BLE001
                    found.append(pkg)
            else:
                missing.append(pkg)
    passed = len(missing) == 0
    return {
        "name": "Python Dependencies",
        "passed": passed,
        "detail": f"Installed: {len(found)} | Missing: {', '.join(missing) if missing else 'None'}",
        "required": ", ".join(REQUIRED_PACKAGES),
    }


def check_port(port: int, service_name: str):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return {
            "name": f"Port {port} ({service_name})",
            "passed": True,
            "detail": "Available",
            "required": f"Port {port} free",
        }
    except OSError:
        return {
            "name": f"Port {port} ({service_name})",
            "passed": False,
            "detail": "In use / occupied by another process",
            "required": f"Port {port} free",
        }


def check_filesystem():
    root = Path(__file__).resolve().parent.parent
    storage_dir = root / "storage"
    logs_dir = root / "logs"
    storage_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    test_storage = storage_dir / ".write_test"
    test_logs = logs_dir / ".write_test"
    try:
        test_storage.write_text("ok")
        test_storage.unlink()
        test_logs.write_text("ok")
        test_logs.unlink()
        return {
            "name": "Filesystem Permissions",
            "passed": True,
            "detail": f"storage/ and logs/ writable at {root}",
            "required": "Writable storage and logs directories",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "name": "Filesystem Permissions",
            "passed": False,
            "detail": f"Write failed: {e}",
            "required": "Writable storage and logs directories",
        }


def check_win32_ctypes():
    try:
        import ctypes

        user32 = ctypes.windll.user32
        has_gwl = hasattr(user32, "GetWindowLongW") or hasattr(
            user32, "GetWindowLongPtrW"
        )
        return {
            "name": "Win32 ctypes Capability",
            "passed": has_gwl,
            "detail": "ctypes.windll.user32 accessible for window transparency",
            "required": "user32 API available",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "name": "Win32 ctypes Capability",
            "passed": False,
            "detail": f"Error: {e}",
            "required": "user32 API available",
        }


def run_all_checks():
    checks = [
        check_os(),
        check_python(),
        check_node(),
        check_npm(),
        check_python_packages(),
        check_port(DEFAULT_BACKEND_PORT, "Backend API"),
        check_port(DEFAULT_FRONTEND_PORT, "Frontend Vite"),
        check_filesystem(),
        check_win32_ctypes(),
    ]

    print("=" * 60)
    print("COMPASS — ENVIRONMENT VALIDATION")
    print("=" * 60)
    all_passed = True
    for c in checks:
        status = "[PASS]" if c["passed"] else "[FAIL]"
        if not c["passed"]:
            all_passed = False
        print(f"{status:7} {c['name']:<25} : {c['detail']}")
    print("=" * 60)
    if all_passed:
        print("ENVIRONMENT VALIDATION PASSED: All Phase 1 requirements satisfied.")
    else:
        print(
            "ENVIRONMENT VALIDATION FAILED: Resolve reported issues before proceeding."
        )
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    passed = run_all_checks()
    sys.exit(0 if passed else 1)
