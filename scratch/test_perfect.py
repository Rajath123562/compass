import ctypes
import subprocess
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

# Define types
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

print("Launching Notepad...")
subprocess.Popen('notepad.exe')
time.sleep(5)

raw_hwnds = []

def enum_windows_callback(hwnd, lparam):
    raw_hwnds.append(hwnd)
    return 1 # return TRUE to continue

cb_func = WNDENUMPROC(enum_windows_callback)
res = user32.EnumWindows(cb_func, 0)

print(f"EnumWindows returned {res}")
print(f"Enumerated {len(raw_hwnds)} total windows")

for hwnd in raw_hwnds:
    print(f"HWND: {hwnd}")
