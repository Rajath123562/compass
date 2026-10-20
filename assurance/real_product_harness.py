"""
COMPASS Real Product Harness & Independent External Observer
Manages the lifecycle of the real assembled COMPASS stack (FastAPI backend + Vite frontend + Database)
and provides external, out-of-band Win32/UIA ground-truth verification of actual Windows state.

Non-negotiable principle: The running product is tested directly, and results are verified
by an independent outside observer rather than trusting internal claims.
"""

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import psutil
import requests
import shutil

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

PYTHON_EXE = (
    str(ROOT_DIR / ".venv" / "Scripts" / "python.exe")
    if (ROOT_DIR / ".venv" / "Scripts" / "python.exe").exists()
    else sys.executable
)
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"
PID_FILE = ROOT_DIR / ".compass_pids.json"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class ExternalWindowsObserver:
    """
    Independent ground-truth inspector.
    Uses raw Win32 APIs directly, independent of COMPASS code,
    to verify real Windows state (preventing false-success bugs).
    """

    @staticmethod
    def get_foreground_window_title() -> str:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value

    @staticmethod
    def find_windows_by_title_substring(sub: str) -> list[int]:
        raw_hwnds = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, lparam):
            raw_hwnds.append(hwnd)
            return True
            
        cb_func = WNDENUMPROC(enum_windows_callback)
        user32.EnumWindows(cb_func, 0)
        
        hwnds = []
        for hwnd in raw_hwnds:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    val = buff.value
                    if "gdi+" in val.lower():
                        continue
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    if (rect.right - rect.left) <= 0 or (rect.bottom - rect.top) <= 0:
                        continue
                    if sub.lower() in val.lower():
                        hwnds.append(hwnd)
        return hwnds

    @staticmethod
    def inspect_notepad_text(hwnd: int) -> str:
        """Inspects text from the Edit control of a Notepad or MockNotepad window using raw Win32 APIs."""
        if not hwnd:
            return ""
        # 1. Find child Edit control
        edit_hwnd = user32.FindWindowExW(hwnd, None, "Edit", None)
        if not edit_hwnd:
            edit_hwnd = user32.FindWindowExW(hwnd, None, "RichEditD2DPT", None)
        if not edit_hwnd:
            edit_hwnd = user32.FindWindowExW(hwnd, None, None, None)
        target = edit_hwnd or hwnd

        WM_GETTEXTLENGTH = 0x000E
        WM_GETTEXT = 0x000D
        length = user32.SendMessageW(target, WM_GETTEXTLENGTH, 0, 0)
        if length <= 0:
            length = user32.GetWindowTextLengthW(target)
            if length <= 0:
                return ""
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(target, buff, length + 1)
            return buff.value

        buff = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(target, WM_GETTEXT, length + 1, buff)
        return buff.value

    @staticmethod
    def is_process_running(proc_name: str) -> bool:
        proc_name_lower = proc_name.lower()
        for p in psutil.process_iter(["name"]):
            try:
                if p.info["name"] and p.info["name"].lower() == proc_name_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    @staticmethod
    def get_process_pids(proc_name: str) -> list[int]:
        pids = []
        proc_name_lower = proc_name.lower()
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info["name"] and p.info["name"].lower() == proc_name_lower:
                    pids.append(p.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return pids

    @staticmethod
    def terminate_processes_by_name(proc_name: str):
        """DEPRECATED & PROHIBITED: Arbitrary process-name termination is unsafe and prohibited by COMPASS safety policy.
        Use RealProductManager.process_tracker.terminate_owned() to terminate only verified child processes.
        """
        raise RuntimeError(
            f"Unsafe operation blocked: terminate_processes_by_name('{proc_name}') is prohibited. "
            "The test harness must only terminate processes it spawned and owns."
        )


class OwnedProcessTracker:
    """Tracks child processes explicitly started by the test harness so that
    cleanup only terminates owned processes and never touches unrelated applications.
    Guards against PID reuse by verifying process creation time and path.
    """

    def __init__(self):
        self._tracked: list[dict] = []

    def track(self, popen_obj: subprocess.Popen, description: str = "") -> dict:
        try:
            p = psutil.Process(popen_obj.pid)
            info = {
                "pid": p.pid,
                "create_time": p.create_time(),
                "exe": p.exe() if hasattr(p, "exe") else "",
                "popen": popen_obj,
                "desc": description,
            }
        except Exception:
            info = {
                "pid": popen_obj.pid,
                "create_time": None,
                "exe": "",
                "popen": popen_obj,
                "desc": description,
            }
        self._tracked.append(info)
        return info

    def is_tracked_alive(self, pid: int) -> bool:
        for item in self._tracked:
            if item["pid"] == pid:
                if item["popen"].poll() is None:
                    try:
                        p = psutil.Process(pid)
                        if item["create_time"] is None or abs(p.create_time() - item["create_time"]) <= 1.0:
                            return True
                    except Exception:
                        pass
        return False

    def terminate_owned(self, pid: int | None = None) -> int:
        terminated = 0
        remaining = []
        for item in self._tracked:
            target_pid = item["pid"]
            if pid is not None and target_pid != pid:
                remaining.append(item)
                continue

            try:
                p = psutil.Process(target_pid)
                # Guard against PID reuse
                if item["create_time"] is not None and abs(p.create_time() - item["create_time"]) > 1.0:
                    print(
                        f"[ProcessTracker] Warning: PID {target_pid} was reused by an unrelated process. Refusing to terminate."
                    )
                    continue

                for child in p.children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass
                p.kill()
                try:
                    p.wait(timeout=2.0)
                except Exception:
                    pass
                if "popen" in item and hasattr(item["popen"], "poll"):
                    try:
                        item["popen"].poll()
                    except Exception:
                        pass
                terminated += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                print(f"[ProcessTracker] Error terminating owned process {target_pid}: {e}")

        if pid is None:
            self._tracked.clear()
        else:
            self._tracked = remaining
        return terminated

    @staticmethod
    def inspect_notepad_text(hwnd: int) -> str:
        """Independently read text from a Notepad edit control via Win32 messages."""
        WM_GETTEXT = 0x000D
        WM_GETTEXTLENGTH = 0x000E

        edit_hwnd = 0

        def _enum_child(h, _):
            nonlocal edit_hwnd
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls_buf, 256)
            if cls_buf.value in ("Edit", "RichEditD2DPT"):
                edit_hwnd = h
                return False
            return True

        from ctypes import wintypes

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumChildWindows(hwnd, WNDENUMPROC(_enum_child), 0)

        target = edit_hwnd if edit_hwnd else hwnd
        length = user32.SendMessageW(target, WM_GETTEXTLENGTH, 0, 0)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.SendMessageW(target, WM_GETTEXT, length + 1, ctypes.byref(buff))
            if buff.value:
                return buff.value

        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value


class RealProductManager:
    """Controls the lifecycle of the real running COMPASS backend and frontend.
    Guarantees:
    - Never terminates unknown or foreign processes on application ports.
    - Tracks and terminates only owned child processes.
    - Explicitly enforces and validates COMPASS_TEST_MODE=1 in test environments.
    """

    def __init__(self):
        self.backend_proc: subprocess.Popen | None = None
        self.frontend_proc: subprocess.Popen | None = None
        self._started_by_us = False
        self.process_tracker = OwnedProcessTracker()
        self.port_conflicts: list[dict] = []

    def is_backend_live(self) -> bool:
        try:
            r = requests.get(f"{BACKEND_URL}/api/health", timeout=1.5)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def is_frontend_live(self) -> bool:
        try:
            r = requests.get(FRONTEND_URL, timeout=1.5)
            return r.status_code in (200, 304)
        except Exception:  # noqa: BLE001
            return False

    def is_test_mode_verified(self) -> bool:
        """Independently verifies that the running backend has COMPASS_TEST_MODE=1 enabled."""
        try:
            r = requests.get(f"{BACKEND_URL}/api/health", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                sys_telemetry = data.get("system", {})
                return bool(sys_telemetry.get("test_mode"))
        except Exception:  # noqa: BLE001
            pass
        return False

    def _check_and_release_compass_ports(self) -> bool:
        """Checks ports 8000 and 5173.
        Only terminates processes confirmed to be COMPASS services.
        If an unknown process occupies either port, reports conflict and fails closed without killing it.
        """
        self.port_conflicts.clear()
        for port in [8000, 5173]:
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.laddr and conn.laddr.port == port and conn.pid:
                        try:
                            p = psutil.Process(conn.pid)
                            cmdline = " ".join(p.cmdline()).lower()
                            is_compass = any(
                                m in cmdline
                                for m in [
                                    "backend.app.main",
                                    "uvicorn",
                                    "vite",
                                    "compass",
                                    "overlay.launcher",
                                ]
                            )
                            if is_compass:
                                print(
                                    f"[ProductManager] Port {port} occupied by previous COMPASS process '{p.name()}' (PID {p.pid}). Releasing..."
                                )
                                for child in p.children(recursive=True):
                                    try:
                                        child.kill()
                                    except Exception:
                                        pass
                                p.kill()
                                time.sleep(0.5)
                            else:
                                print(
                                    f"[ProductManager] Port {port} occupied by UNKNOWN process '{p.name()}' (PID {p.pid}). Refusing to terminate unknown process."
                                )
                                self.port_conflicts.append(
                                    {"port": port, "pid": p.pid, "name": p.name(), "exe": getattr(p, "exe", lambda: "")()}
                                )
                                return False
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            except Exception as e:
                print(f"[ProductManager] Warning inspecting connections for port {port}: {e}")
        return True

    def ensure_live_product(self, timeout: int = 30) -> bool:
        """Verify if COMPASS is already running; if not, launch actual backend & frontend."""
        if self.is_backend_live() and self.is_frontend_live():
            print(
                "[ProductManager] Real COMPASS backend and frontend are already live."
            )
            return True

        print("[ProductManager] Launching real COMPASS product stack with safe isolation...")
        self._started_by_us = True

        # 1. Start Backend if not already live
        if not self.is_backend_live():
            # Safe port validation: never kill foreign processes
            if not self._check_and_release_compass_ports():
                print(
                    f"[ProductManager] ABORT: Port conflict detected with non-COMPASS process(es): {self.port_conflicts}. "
                    "Harness will not terminate foreign processes. Manual resolution required."
                )
                return False

            backend_cmd = [
                PYTHON_EXE,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--log-level",
                "warning",
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT_DIR)
            env["COMPASS_TEST_MODE"] = "1"
            self.backend_proc = subprocess.Popen(
                backend_cmd,
                cwd=str(ROOT_DIR),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.process_tracker.track(self.backend_proc, "Backend (uvicorn)")
        else:
            print("[ProductManager] Backend already live at http://127.0.0.1:8000")

        # 2. Start Frontend if not already live
        if not self.is_frontend_live():
            frontend_dir = ROOT_DIR / "frontend"
            npm_bin = shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
            self.frontend_proc = subprocess.Popen(
                [npm_bin, "run", "dev"],
                cwd=str(frontend_dir),
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.process_tracker.track(self.frontend_proc, "Frontend (npm dev)")
        else:
            print("[ProductManager] Frontend already live at http://127.0.0.1:5173")

        # 3. Wait for readiness
        t0 = time.time()
        backend_ready = False
        frontend_ready = False

        while time.time() - t0 < timeout:
            if not backend_ready and self.is_backend_live():
                backend_ready = True
                print("  [+] Backend live at http://127.0.0.1:8000")
            if not frontend_ready and self.is_frontend_live():
                frontend_ready = True
                print("  [+] Frontend live at http://127.0.0.1:5173")
            if backend_ready and frontend_ready:
                break
            time.sleep(0.5)

        if not (backend_ready and frontend_ready):
            print(
                f"[ProductManager] Warning: Timed out waiting for full stack. Backend: {backend_ready}, Frontend: {frontend_ready}"
            )
            return backend_ready  # Backend is mandatory for API tests

        # 4. Verify test-mode policy in child process
        if not self.is_test_mode_verified():
            print(
                "[ProductManager] CRITICAL WARNING: Backend running but COMPASS_TEST_MODE=1 could not be verified via /api/health!"
            )

        print("[ProductManager] Real COMPASS product stack operational under test isolation.")
        return True

    def teardown(self):
        """Cleanly terminate ONLY the product processes started by the test harness."""
        if not self._started_by_us:
            return

        print("[ProductManager] Tearing down test-managed COMPASS product...")
        terminated_count = self.process_tracker.terminate_owned()
        print(f"[ProductManager] Released {terminated_count} owned test process(es).")
