import subprocess
import time
import ctypes

user32 = ctypes.windll.user32
p = subprocess.Popen(['mspaint.exe'])
time.sleep(2)

def cb(h, _):
    if user32.IsWindowVisible(h):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(h, buf, 512)
        print(f"HWND: {h}, Title: '{buf.value}'")
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUM(cb), 0)
p.kill()
