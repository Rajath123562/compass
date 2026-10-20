import ctypes
import ctypes.wintypes
import subprocess
import sys
import time

sys.path.insert(0, ".")
from scripts.test_real_windows_phase7 import safe_kill_process_by_name

user32 = ctypes.windll.user32


def find_window_by_substr(substr: str, timeout_sec: float = 5.0):
    WNDENUM = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    t_end = time.time() + timeout_sec
    while time.time() < t_end:
        found = []

        def _enum(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if substr.lower() in buf.value.lower():
                        found.append(hwnd)  # noqa: B023
            return True

        user32.EnumWindows(WNDENUM(_enum), 0)
        if found:
            return found[0]
        time.sleep(0.3)
    return None


safe_kill_process_by_name("notepad")
time.sleep(0.5)
proc = subprocess.Popen(["notepad.exe"])
hwnd = find_window_by_substr("Notepad", timeout_sec=5.0)
print("Found hwnd:", hwnd)

user32.SetWindowPos(hwnd, 0, 100, 100, 800, 600, 0x0040)
user32.ShowWindow(hwnd, 5)
user32.SetForegroundWindow(hwnd)
time.sleep(0.8)

from automation import action_dispatcher

action_dispatcher.type_text({"hwnd": hwnd}, "Save Document Here")
time.sleep(0.8)

from perception.multimodal_service import MultimodalPerceptionService

svc = MultimodalPerceptionService()
snap = svc.capture_multimodal_snapshot(
    task_id="wf_A", step_id="step_1", target_hwnd=hwnd, include_ocr=True
)

print(
    "UIA count:",
    len(
        snap.get_by_source(
            from_src := snap.get_by_source.__annotations__.get("source", None) or 0
        )
    ),
)
uia_items = [e for e in snap.evidence_items if e.source.value == "UIA"]
ocr_items = [e for e in snap.evidence_items if e.source.value == "OCR"]
print(f"UIA items: {len(uia_items)}, OCR items: {len(ocr_items)}")
for o in ocr_items[:10]:
    print("  OCR word:", repr(o.extracted_text))

target = (
    svc.resolve_target(snap, target_name="File")
    or svc.resolve_target(snap, target_name="Document")
    or svc.resolve_target(snap, target_name="Save")
    or svc.resolve_target(snap, target_name="Text editor")
    or svc.resolve_target(snap, target_name="Notepad")
)
print("Target resolved:", target.name if target else None)

safe_kill_process_by_name("notepad")
