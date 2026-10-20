import threading
import time
import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from perception import uia_inspector

user32 = ctypes.windll.user32
root_ref = []

def run_win():
    root = tk.Tk()
    root.title("*Untitled - Notepad")
    root.geometry("800x600")
    txt = tk.Text(root)
    txt.pack(expand=True, fill="both")
    root_ref.append(root)
    root.mainloop()

t = threading.Thread(target=run_win, daemon=True)
t.start()
time.sleep(1)

found = []
def _enum(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if "notepad" in buf.value.lower():
            found.append(hwnd)
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUM(_enum), 0)
print("Found HWND:", found)
if found:
    hwnd = found[0]
    tree = uia_inspector.get_element_tree(hwnd, depth=2)
    print("Element tree count:", len(tree.get("elements", [])))
    for el in tree.get("elements", [])[:3]:
        print("  Element:", el.get("name"), el.get("control_type"))

if root_ref:
    root_ref[0].destroy()
