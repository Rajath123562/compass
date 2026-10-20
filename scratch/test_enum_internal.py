import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32
hwnds = []

def cb(h, l):
    try:
        length = user32.GetWindowTextLengthW(h)
        hwnds.append(length)
    except Exception as e:  # noqa: BLE001
        print("Error:", e)
    return True

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows(EnumWindowsProc(cb), 0)

print("Lengths:", hwnds[:20])
