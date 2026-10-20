import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32

for i in range(3):
    hwnds = []
    def callback(hwnd, lparam):
        hwnds.append(hwnd)  # noqa: B023
        return True
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    res = user32.EnumWindows(EnumWindowsProc(callback), 0)
    print(f"Iter {i}: Result={res}, Total hwnds={len(hwnds)}")
