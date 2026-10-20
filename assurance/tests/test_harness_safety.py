"""
COMPASS Test Harness Safety Regression Tests
Verifies fixes for COMPASS-AUDIT-004, COMPASS-AUDIT-005, and COMPASS-AUDIT-006:
- Proves no arbitrary process-name killing of unrelated processes.
- Proves foreign/unknown port listeners are never killed and conflicts fail closed.
- Proves OwnedProcessTracker terminates only owned child processes and guards PID reuse.
- Proves test-mode isolation enforcement prevents unisolated adversarial execution.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from assurance.real_product_harness import (
    ExternalWindowsObserver,
    OwnedProcessTracker,
    RealProductManager,
)
from scripts.start_compass import kill_process_on_port


def test_arbitrary_terminate_by_name_is_prohibited():
    """COMPASS-AUDIT-004: Proves that terminate_processes_by_name is blocked with an error."""
    with pytest.raises(RuntimeError, match="Unsafe operation blocked"):
        ExternalWindowsObserver.terminate_processes_by_name("notepad.exe")


def test_unrelated_process_not_terminated_by_tracker():
    """COMPASS-AUDIT-004: Proves that unrelated running processes are never terminated."""
    # Spawn an unrelated dummy process
    unrelated_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        tracker = OwnedProcessTracker()
        # Spawn an owned dummy process
        owned_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        tracker.track(owned_proc, "Owned dummy process")

        # Terminate owned
        terminated = tracker.terminate_owned()
        assert terminated == 1
        owned_proc.wait(timeout=2)
        assert owned_proc.poll() is not None

        # Assert unrelated process remains completely untouched and alive
        assert unrelated_proc.poll() is None
    finally:
        unrelated_proc.kill()
        unrelated_proc.wait()


def test_tracker_pid_reuse_protection():
    """COMPASS-AUDIT-004: Proves that OwnedProcessTracker verifies process creation time before killing."""
    tracker = OwnedProcessTracker()
    dummy_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        # Register with intentionally mismatched create_time to simulate PID reuse by foreign process
        info = {
            "pid": dummy_proc.pid,
            "create_time": time.time() - 1000.0,  # 1000s in the past
            "exe": sys.executable,
            "popen": dummy_proc,
            "desc": "Simulated reused PID",
        }
        tracker._tracked.append(info)

        # Terminate attempt should refuse because creation time does not match
        tracker.terminate_owned(dummy_proc.pid)
        assert dummy_proc.poll() is None, "Tracker must NOT terminate a process if create_time differs"
    finally:
        dummy_proc.kill()
        dummy_proc.wait()


def test_unrelated_port_listener_never_killed():
    """COMPASS-AUDIT-005: Proves that an unknown process listening on a port is not killed."""
    # Start a server socket on an ephemeral port
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    try:
        # Test start_compass.kill_process_on_port on this port
        result = kill_process_on_port(port)
        # Should return False (refusing to kill unknown process)
        assert result is False

        # Socket should still be open and alive
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(1.0)
        conn_res = client_sock.connect_ex(("127.0.0.1", port))
        client_sock.close()
        assert conn_res == 0, "Unknown listener must remain alive"
    finally:
        server_sock.close()


def test_harness_detects_port_conflict_safely():
    """COMPASS-AUDIT-005: Proves RealProductManager detects port conflict and fails closed without killing."""
    mgr = RealProductManager()
    
    # Temporarily bind a socket on port 8000
    try:
        sock8000 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock8000.bind(("127.0.0.1", 8000))
        sock8000.listen(1)
        
        # Check port release policy
        can_proceed = mgr._check_and_release_compass_ports()
        assert can_proceed is False, "Must fail closed when foreign process holds port 8000"
        assert len(mgr.port_conflicts) > 0
        assert mgr.port_conflicts[0]["port"] == 8000
    except OSError:
        pytest.skip("Port 8000 cannot be bound for test")
    finally:
        sock8000.close()


def test_test_mode_isolation_enforcement():
    """COMPASS-AUDIT-006: Proves that absence of COMPASS_TEST_MODE in environment fails isolation check."""
    mgr = RealProductManager()
    
    # Without backend live or without test_mode telemetry, is_test_mode_verified() must be False
    assert mgr.is_test_mode_verified() is False
