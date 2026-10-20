import ctypes
import ctypes.wintypes
import subprocess
import time

user32 = ctypes.windll.user32

proc = subprocess.Popen(["notepad.exe"])
time.sleep(2.0)

WNDENUM = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

all_windows = []


def _enum(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            all_windows.append((hwnd, buf.value))
    return True


user32.EnumWindows(WNDENUM(_enum), 0)
print("Visible windows with titles:")
for h, t in all_windows:
    if "note" in t.lower() or "pad" in t.lower():
        print(f"  FOUND NOTEPAD: HWND={h}, Title='{t}'")
    else:
        # print some
        pass

for p in (proc.poll(),):
    proc.terminate()
