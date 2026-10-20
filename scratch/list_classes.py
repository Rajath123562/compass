import ctypes
import subprocess
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]

print("Launching Mock Notepad...")
subprocess.Popen(r'assurance\notepad.exe')
time.sleep(5)

hwnds = []
def enum_windows_callback(hwnd, lparam):
    hwnds.append(hwnd)
    return 1

user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

for h in hwnds:
    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, cls_buf, 256)
    
    length = user32.GetWindowTextLengthW(h)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    if length > 0:
        user32.GetWindowTextW(h, title_buf, length + 1)
        
    print(f"HWND: {h}, Class: {cls_buf.value}, Title: {title_buf.value}, Visible: {bool(user32.IsWindowVisible(h))}")
