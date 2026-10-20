import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

raw_hwnds = []
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

def enum_windows_callback(hwnd, lparam):
    try:
        raw_hwnds.append(hwnd)
        return True
    except Exception as e:  # noqa: BLE001
        print("Error in callback:", e)
        return False
    
cb_func = WNDENUMPROC(enum_windows_callback)
user32.EnumWindows(cb_func, 0)

print(f"Enumerated {len(raw_hwnds)} total windows")
