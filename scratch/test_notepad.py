import ctypes
import ctypes.wintypes
import subprocess
import time

subprocess.Popen("notepad.exe")
time.sleep(2)

user32 = ctypes.windll.user32
hwnds = []

def enum_cb(hwnd, lParam):
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value
        
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        
        if "notepad" in title.lower():
            print(f"Found Window: HWND={hwnd}, Title={title}, Class={cls_buf.value}")
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
