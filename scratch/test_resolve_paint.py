import subprocess
import time
import sys
import ctypes
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from perception import uia_inspector
from planner.target_resolver import TargetResolver, TargetReference

user32 = ctypes.windll.user32
p = subprocess.Popen(["mspaint.exe"])
time.sleep(1.5)
hwnd = None

def _enum(h, _):
    global hwnd
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, buf, 512)
    if "paint" in buf.value.lower():
        hwnd = h
    return True

user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_enum), 0)

tree = uia_inspector.get_element_tree(hwnd, depth=2)
resolver = TargetResolver(check_foreground=False)
res = resolver.resolve(TargetReference(control_type="Window", name="Paint"), tree)
print("Resolve result:", res.success, res.element.get("name") if res.element else None)
p.kill()
