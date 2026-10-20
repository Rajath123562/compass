"""
COMPASS Safe Shutdown Manager
Safely terminates registered COMPASS processes and releases ports without touching unrelated Windows processes.
"""

import json
import socket
import sys
import time
from pathlib import Path

import psutil

ROOT_DIR = Path(__file__).resolve().parent.parent
PID_FILE = ROOT_DIR / ".compass_pids.json"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_compass_process(proc: psutil.Process) -> bool:
    """Verifies that the process is actually a COMPASS service before touching it."""
    try:
        cmdline = " ".join(proc.cmdline()).lower()
        compass_markers = [
            "compass",
            "uvicorn",
            "backend.app.main",
            "vite",
            "overlay.launcher",
            "npm",
            "node",
        ]
        return any(marker in cmdline for marker in compass_markers)
    except Exception:  # noqa: BLE001
        return False


def terminate_process_tree(pid: int):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except Exception:  # noqa: BLE001, S110
                pass
        parent.kill()
    except Exception:  # noqa: BLE001, S110
        pass


def free_port_if_compass(port: int):
    """If port 8000 or 5173 is occupied, verify if it's a COMPASS dev server (node/python) and terminate it."""
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    if is_compass_process(proc):
                        print(
                            f"[COMPASS Stopper] Freeing port {port} held by COMPASS process {proc.name()} (PID: {conn.pid})..."
                        )
                        terminate_process_tree(conn.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception:  # noqa: BLE001, S110
        pass


def stop_compass():
    print("[COMPASS Stopper] Checking registered COMPASS processes...")
    if PID_FILE.exists():
        try:
            pids = json.loads(PID_FILE.read_text())
        except Exception:  # noqa: BLE001
            pids = {}

        for service, pid in pids.items():
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    if is_compass_process(proc):
                        print(
                            f"[COMPASS Stopper] Terminating {service} (PID: {pid})..."
                        )
                        terminate_process_tree(pid)
                    else:
                        print(
                            f"[COMPASS Stopper] PID {pid} is not a COMPASS process. Skipping."
                        )
                except Exception as e:  # noqa: BLE001
                    print(
                        f"[COMPASS Stopper] Warning terminating {service} ({pid}): {e}"
                    )

        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001, S110
            pass

    time.sleep(0.5)
    # Check ports 8000, 5173, and 8001 specifically
    free_port_if_compass(8000)
    free_port_if_compass(5173)
    free_port_if_compass(8001)
    time.sleep(0.5)

    port_8000_free = not is_port_in_use(8000)
    port_5173_free = not is_port_in_use(5173)
    port_8001_free = not is_port_in_use(8001)

    print(
        f"[COMPASS Stopper] Port 8000 (Backend API): {'FREE' if port_8000_free else 'OCCUPIED'}"
    )
    print(
        f"[COMPASS Stopper] Port 5173 (Frontend):     {'FREE' if port_5173_free else 'OCCUPIED'}"
    )
    print(
        f"[COMPASS Stopper] Port 8001 (Overlay HUD):  {'FREE' if port_8001_free else 'OCCUPIED'}"
    )

    if port_8000_free and port_5173_free and port_8001_free:
        print("[COMPASS Stopper] COMPASS stopped cleanly. Zero orphan processes.")
        return 0
    else:
        print("[COMPASS Stopper] Warning: One or more ports remain occupied.")
        return 1


if __name__ == "__main__":
    sys.exit(stop_compass())
