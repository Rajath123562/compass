"""
COMPASS Supervisor & Lifecycle Manager
Starts backend and frontend processes cleanly, streams output in background threads
to prevent Windows pipe buffer deadlocks, performs active health readiness verification,
tracks PIDs, and prevents duplicate instances.
"""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import psutil

ROOT_DIR = Path(__file__).resolve().parent.parent
PID_FILE = ROOT_DIR / ".compass_pids.json"
VENV_PYTHON = (
    ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if (ROOT_DIR / ".venv" / "Scripts" / "python.exe").exists()
    else Path(sys.executable)
)


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_process_on_port(port: int) -> bool:
    """Find and terminate a process listening on the given port IF AND ONLY IF it is a confirmed COMPASS process.
    Never terminates arbitrary or unknown processes.
    """
    try:
        pids_data = load_pids()
        expected_pids = set()
        if isinstance(pids_data, dict):
            for v in pids_data.values():
                if isinstance(v, int):
                    expected_pids.add(v)

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                conns = proc.net_connections(kind="inet") if hasattr(proc, "net_connections") else proc.connections(kind="inet")
                for conn in conns:
                    if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                        cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                        is_registered = proc.pid in expected_pids
                        is_compass_cmd = any(
                            m in cmdline
                            for m in [
                                "backend.app.main",
                                "uvicorn",
                                "vite",
                                "compass",
                                "overlay.launcher",
                            ]
                        )

                        if is_registered or is_compass_cmd:
                            print(
                                f"[COMPASS Supervisor] Port {port} in use by previous COMPASS process '{proc.info['name']}' (PID {proc.pid}). Auto-releasing..."
                            )
                            terminate_process_tree(proc.pid)
                            time.sleep(0.5)
                            return True
                        else:
                            print(
                                f"[COMPASS Supervisor] Port {port} in use by UNKNOWN process '{proc.info['name']}' (PID {proc.pid}). Refusing to terminate unknown process."
                            )
                            return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"[COMPASS Supervisor] Warning: Could not check port {port}: {e}")
    return False


def save_pids(pids: dict):
    PID_FILE.write_text(json.dumps(pids, indent=2))


def load_pids() -> dict:
    if PID_FILE.exists():
        try:
            return json.loads(PID_FILE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def stream_pipe(proc: subprocess.Popen, prefix: str):
    """
    Continuously reads proc.stdout line-by-line in a background daemon thread.
    This prevents OS pipe buffer exhaustion (4KB limit on Windows) and provides
    real-time visibility of child process logs.
    """
    def _reader():
        if proc.stdout is None:
            return
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                sys.stdout.write(f"[{prefix}] {line}")
                sys.stdout.flush()
        except Exception:  # noqa: BLE001, S110
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:  # noqa: BLE001, S110
                pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()


def terminate_process_tree(pid: int):
    """Terminates process and all its children recursively."""
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


def start_backend(port: int = 8000) -> subprocess.Popen:
    print(f"[COMPASS Supervisor] Starting FastAPI backend on 127.0.0.1:{port}...")
    cmd = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stream_pipe(proc, "Backend")
    return proc


def start_frontend(port: int = 5173) -> subprocess.Popen:
    print(f"[COMPASS Supervisor] Starting React+Vite frontend on 127.0.0.1:{port}...")
    frontend_dir = ROOT_DIR / "frontend"
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm") or ("npm.cmd" if sys.platform == "win32" else "npm")
    cmd = [npm_cmd, "run", "dev"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(frontend_dir),
        shell=(sys.platform == "win32"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stream_pipe(proc, "Frontend")
    return proc


def is_pyside6_available() -> bool:
    try:
        proc = subprocess.run(
            [str(VENV_PYTHON), "-c", "import PySide6"],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        return False


def start_overlay(duration: float = 0.0) -> subprocess.Popen | None:
    if not is_pyside6_available():
        print("[COMPASS Supervisor] PySide6 not detected. Desktop overlay HUD skipped; running in web UI mode.")
        return None
    print("[COMPASS Supervisor] Starting PySide6 Overlay...")
    cmd = [str(VENV_PYTHON), "-m", "overlay.launcher"]
    if duration > 0:
        cmd.extend(["--duration", str(duration)])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    stream_pipe(proc, "Overlay")
    return proc


def wait_for_backend(proc: subprocess.Popen, port: int = 8000, timeout: float = 20.0) -> bool:
    """Actively polls /api/health until backend reports HTTP 200 OK."""
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "COMPASS-Supervisor"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:  # nosec B310
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    return False


def wait_for_port(proc: subprocess.Popen, port: int, timeout: float = 20.0) -> bool:
    """Actively polls port until the listening socket is bound."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        if is_port_in_use(port):
            return True
        time.sleep(0.3)
    return False


def main():
    parser = argparse.ArgumentParser(description="COMPASS Unified Supervisor")
    parser.add_argument(
        "--backend-only", action="store_true", help="Start only backend"
    )
    parser.add_argument(
        "--with-overlay", action="store_true", help="Launch overlay window"
    )
    parser.add_argument(
        "--overlay-duration",
        type=float,
        default=0.0,
        help="Auto-close overlay after N seconds",
    )
    parser.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=True,
        help="Automatically open browser to COMPASS Web UI",
    )
    parser.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="Do not open browser",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all running COMPASS services tracked by supervisor",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Run for N seconds then shutdown automatically (for tests)",
    )
    args = parser.parse_args()

    if args.stop:
        pids = load_pids()
        if not pids:
            print("[COMPASS Supervisor] No running COMPASS processes tracked.")
            sys.exit(0)
        print(f"[COMPASS Supervisor] Stopping COMPASS processes: {pids}...")
        for name, pid in pids.items():
            try:
                terminate_process_tree(pid)
                print(f"  [+] Stopped {name} (PID {pid})")
            except Exception as e:
                print(f"  [-] Could not stop {name} (PID {pid}): {e}")
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        print("[COMPASS Supervisor] All COMPASS processes stopped.")
        sys.exit(0)

    processes = []
    pids = {}

    backend_proc = start_backend(8000)
    processes.append(("backend", backend_proc))
    pids["backend"] = backend_proc.pid

    # Active readiness probe
    print("[COMPASS Supervisor] Verifying FastAPI backend readiness...")
    if not wait_for_backend(backend_proc, 8000, timeout=20.0):
        if backend_proc.poll() is not None:
            print(
                f"[FATAL] Backend exited prematurely with code {backend_proc.returncode}.",
                file=sys.stderr,
            )
        else:
            print(
                "[FATAL] Backend failed to respond to /api/health within 20 seconds.",
                file=sys.stderr,
            )
        sys.exit(1)
    print("[COMPASS Supervisor] Backend is online and verified healthy.")

    # 3. Launch Frontend (if requested)
    if not args.backend_only:
        frontend_proc = start_frontend(5173)
        processes.append(("frontend", frontend_proc))
        pids["frontend"] = frontend_proc.pid
        print("[COMPASS Supervisor] Verifying React+Vite frontend readiness...")
        if not wait_for_port(frontend_proc, 5173, timeout=20.0):
            print("[FATAL] Frontend failed to bind port 5173.", file=sys.stderr)
            sys.exit(1)
        print("[COMPASS Supervisor] Frontend is online and verified ready.")

    # 4. Launch Overlay (if requested)
    if args.with_overlay:
        overlay_proc = start_overlay(args.overlay_duration)
        if overlay_proc is not None:
            processes.append(("overlay", overlay_proc))
            pids["overlay"] = overlay_proc.pid

    # 5. Persist PIDs
    save_pids(pids)
    print(f"[COMPASS Supervisor] All services started successfully. PIDs: {pids}")
    print("[COMPASS Supervisor] Access UI at: http://127.0.0.1:5173")
    print("[COMPASS Supervisor] Access API at: http://127.0.0.1:8000/api/docs")
    print("[COMPASS Supervisor] Press Ctrl+C to stop all services cleanly.")

    # 6. Automatically open browser
    if not args.backend_only and args.open_browser:
        try:
            time.sleep(0.5)
            print("[COMPASS Supervisor] Opening browser to: http://127.0.0.1:5173")
            import webbrowser
            webbrowser.open("http://127.0.0.1:5173")
        except Exception as e:  # noqa: BLE001
            try:
                if sys.platform == "win32":
                    os.system("start http://127.0.0.1:5173")
            except Exception:
                print(
                    f"[COMPASS Supervisor] Notice: Could not open browser automatically ({e}). Please visit http://127.0.0.1:5173 manually."
                )

    # 7. Graceful shutdown handler
    def handle_signal(sig, frame):
        print("\n[COMPASS Supervisor] Shutting down all services gracefully...")
        for name, proc in processes:
            try:
                terminate_process_tree(proc.pid)
            except Exception:  # noqa: BLE001, S110
                pass
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        print("[COMPASS Supervisor] All services stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    start_time = time.time()
    try:
        while True:
            time.sleep(1)
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                print(
                    f"[COMPASS Supervisor] Duration limit ({args.duration}s) reached. Shutting down..."
                )
                handle_signal(None, None)
            # Check if critical backend process died
            if backend_proc.poll() is not None:
                print(
                    f"[COMPASS Supervisor] Backend process exited unexpectedly with code {backend_proc.returncode}."
                )
                break
    except KeyboardInterrupt:
        handle_signal(None, None)


if __name__ == "__main__":
    main()
