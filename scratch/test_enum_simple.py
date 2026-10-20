import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
hwnds = []
def callback(hwnd, lparam):
    hwnds.append(hwnd)
    return True
cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback)
user32.EnumWindows(cb, 0)
print(len(hwnds))
