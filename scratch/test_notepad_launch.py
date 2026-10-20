import subprocess
import time
import ctypes
import os

user32 = ctypes.windll.user32

# Try launching via explorer
subprocess.Popen(["explorer.exe", "shell:appsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"])
time.sleep(2.5)

found = []
def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if "notepad" in buf.value.lower():
            found.append((hwnd, buf.value))
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUM(enum_cb), 0)
print("Found via explorer:", found)

# Try launching via start
subprocess.Popen(["cmd.exe", "/c", "start", "notepad.exe"])
time.sleep(2.5)
found2 = []
user32.EnumWindows(WNDENUM(enum_cb), 0)
print("Found via start:", found2)
