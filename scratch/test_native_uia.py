import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
import time
from perception import uia_inspector, screen_capture

root = tk.Tk()
root.title("COMPASS Native Test Target - Notepad")
entry = tk.Entry(root, name="txtInput")
entry.pack()
btn = tk.Button(root, text="Save Document", name="btnSave")
btn.pack()
root.update()

import ctypes
user32 = ctypes.windll.user32
hwnd = user32.FindWindowW(None, "COMPASS Native Test Target - Notepad")
print(f"Native Window HWND: {hwnd}")

tree = uia_inspector.get_element_tree(hwnd, depth=3)
print("UIA Elements found:", len(tree.get("elements", [])))
for el in tree.get("elements", []):
    print("  Candidate:", el.get("control_type"), el.get("name"), el.get("bounding_box"))

root.destroy()
