import ctypes
import ctypes.wintypes
import subprocess
import time

user32 = ctypes.windll.user32
subprocess.Popen('notepad.exe')

for i in range(10):
    time.sleep(1)
    hwnds = []
    def callback(hwnd, lparam):
        hwnds.append(hwnd)  # noqa: B023
        return True
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(EnumWindowsProc(callback), 0)
    print(f"Total hwnds: {len(hwnds)}")
    found = False
    for h in hwnds:
        length = user32.GetWindowTextLengthW(h)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h, buff, length + 1)
            if 'notepad' in buff.value.lower():
                visible = user32.IsWindowVisible(h)
                print(f"Sec {i}: HWND: {h}, Title: {buff.value}, Visible: {bool(visible)}")
                found = True
    if not found:
        print(f"Sec {i}: Not found yet.")
