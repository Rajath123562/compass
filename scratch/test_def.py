import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
hwnds = []

def cb(h, l):
    hwnds.append(h)
    return True

cb_func = WNDENUMPROC(cb)
user32.EnumWindows(cb_func, 0)
print(len(hwnds))
