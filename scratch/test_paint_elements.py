import subprocess
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ctypes
from perception import uia_inspector

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
if hwnd:
    tree = uia_inspector.get_element_tree(hwnd, depth=3, max_elements=30)
    elements = tree.get("elements", [])
    print(f"Elements ({len(elements)}):")
    for el in elements[:10]:
        print(" ", el.get("name"), "|", el.get("control_type"))

p.kill()
