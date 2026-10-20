import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.EnumWindows.restype = ctypes.c_int

hwnds = []

@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def enum_windows_callback(hwnd, lparam):
    hwnds.append(hwnd)
    return True

res = user32.EnumWindows(enum_windows_callback, 0)
print(f"Result={res}, Total hwnds={len(hwnds)}")
