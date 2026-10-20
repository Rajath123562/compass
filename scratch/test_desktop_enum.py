import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32

h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
print("OpenDesktop Default handle:", h_def)

def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if any(k in title.lower() for k in ["notepad", "paint", "chrome", "code", "compass"]):
                print(f"HWND {hwnd}: {title}")
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
print("Calling EnumDesktopWindows:")
user32.EnumDesktopWindows(h_def, WNDENUM(enum_cb), 0)
