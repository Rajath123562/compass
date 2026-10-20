import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32

hwnds = []
def callback(hwnd, lparam):
    hwnds.append(hwnd)
    return 1

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
cb = EnumWindowsProc(callback)
res = user32.EnumWindows(cb, 0)
print(f"Result={res}, Total hwnds={len(hwnds)}")
