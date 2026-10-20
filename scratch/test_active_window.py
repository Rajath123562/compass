import ctypes
from ctypes import wintypes

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)

hwnds = []
def cb(h, lp):
    if user32.IsWindowVisible(h) and not user32.IsIconic(h):
        l = user32.GetWindowTextLengthW(h)
        if l > 0:
            b = ctypes.create_unicode_buffer(l + 1)
            user32.GetWindowTextW(h, b, l + 1)
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, buf, 256)
            if buf.value not in ("Progman", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow"):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                pname = psutil.Process(pid.value).name() if pid.value else "unknown"
                hwnds.append({"hwnd": h, "title": b.value, "class": buf.value, "process": pname})
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(cb), 0)

print(f"Total found: {len(hwnds)}")
for item in hwnds[:5]:
    print(item)
