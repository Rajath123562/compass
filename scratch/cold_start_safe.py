import ctypes
import ctypes.wintypes
import subprocess
import time

import psutil

user32 = ctypes.windll.user32

for p in psutil.process_iter():
    try:
        if 'notepad' in p.name().lower():
            p.kill()
    except:  # noqa: E722, S110
        pass

time.sleep(1)
subprocess.Popen('notepad.exe')
time.sleep(5)

hwnds = []
def callback(hwnd, lparam):
    hwnds.append(hwnd)
    return True

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows(EnumWindowsProc(callback), 0)

for h in hwnds:
    if user32.IsWindowVisible(h):
        length = user32.GetWindowTextLengthW(h)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h, buff, length + 1)
            try:
                print(f"HWND: {h}, Title: {buff.value.encode('ascii', 'replace').decode('ascii')}")
            except Exception:  # noqa: BLE001, S110
                pass
