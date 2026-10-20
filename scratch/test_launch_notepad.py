import subprocess
import time
import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32
h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
if h_default:
    user32.SetThreadDesktop(h_default)

si = subprocess.STARTUPINFO()
si.lpDesktop = r"WinSta0\Default"

proc = subprocess.Popen(["notepad.exe"], startupinfo=si)
time.sleep(2.0)

found = []
def _enum(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        tbuf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, tbuf, length + 1)
        
        cbuf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cbuf, 256)
        
        title = tbuf.value
        cls = cbuf.value
        if "notepad" in title.lower() or "notepad" in cls.lower() or "untitled" in title.lower():
            found.append((hwnd, cls, title))
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows(WNDENUM(_enum), 0)
print("Found windows with lpDesktop=WinSta0\\Default:", found)
proc.kill()
