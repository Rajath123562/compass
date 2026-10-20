import subprocess
import time
import ctypes

user32 = ctypes.windll.user32

p = subprocess.Popen([r"C:\Windows\System32\notepad.exe"])
time.sleep(1.5)

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
print("Found notepad windows:", found)
p.kill()
