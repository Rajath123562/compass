import ctypes
import json
import subprocess
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

print("Launching Notepad...")
subprocess.Popen('notepad.exe')
time.sleep(5)

raw_hwnds = []
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

def enum_windows_callback(hwnd, lparam):
    raw_hwnds.append(hwnd)
    return True
    
cb_func = WNDENUMPROC(enum_windows_callback)
user32.EnumWindows(cb_func, 0)

windows = []
for hwnd in raw_hwnds:
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            windows.append({"hwnd": hwnd, "title": buff.value})

with open("windows.json", "w", encoding="utf-8") as f:
    json.dump(windows, f, indent=2)

print(f"Dumped {len(windows)} visible windows to windows.json")
