import subprocess
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ctypes
from backend.app.services.task_service import task_service
from planner.execution_engine import execution_engine
from planner.human_approval import human_approval_controller, GuidanceMode

user32 = ctypes.windll.user32
p = subprocess.Popen(["mspaint.exe"])
time.sleep(2.0)

def find_paint():
    found = []
    def _enum(h, _):
        if user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, buf, 512)
            if "paint" in buf.value.lower():
                found.append(h)
        return True
    cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_enum)
    user32.EnumWindows(cb, 0)
    return found[0] if found else None

hwnd = find_paint()
print("Paint HWND:", hwnd)

human_approval_controller.set_mode(GuidanceMode.AUTONOMOUS)
task = task_service.create_task("Click Canvas in Paint", metadata={"guidance_mode": "autonomous"})
events = []
res = execution_engine.run_task(
    task_id=task["id"],
    on_event=lambda ev, d: events.append(ev),
    target_hwnd=hwnd,
)
print("Execution Result:", res)
final_task = task_service.get_task(task["id"])
print("Final State:", final_task.get("state"))
print("Events:", events)

p.kill()
