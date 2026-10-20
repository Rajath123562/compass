import ctypes
import ctypes.wintypes
import subprocess
import time

user32 = ctypes.windll.user32

subprocess.Popen('notepad.exe')
time.sleep(2)

hwnds = []
def callback(hwnd, lparam):
    hwnds.append(hwnd)
    return True

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows(EnumWindowsProc(callback), 0)

for h in hwnds:
    length = user32.GetWindowTextLengthW(h)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(h, buff, length + 1)
        if 'notepad' in buff.value.lower():
            visible = user32.IsWindowVisible(h)
            print(f"HWND: {h}, Title: {buff.value}, Visible: {bool(visible)}")
