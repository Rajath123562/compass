import ctypes
import ctypes.wintypes
import time

time.sleep(1)
user32 = ctypes.windll.user32

hwnds = []
def callback(hwnd, lparam):
    hwnds.append(hwnd)
    return True

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
res = user32.EnumWindows(EnumWindowsProc(callback), 0)
print(f"Result={res}, Total hwnds={len(hwnds)}")
