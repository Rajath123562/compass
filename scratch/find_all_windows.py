import ctypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GENERIC_ALL = 0x10000000
h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF) # DESKTOP_ALL
err = kernel32.GetLastError()
print(f"OpenDesktop('Default') returned: {h_default}, GetLastError: {err}")

if h_default:
    res = user32.SetThreadDesktop(h_default)
    print(f"SetThreadDesktop returned: {res}")
    
    count = 0
    titles = []
    def _cb(hwnd, lparam):
        global count
        count += 1
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            titles.append((hwnd, buf.value))
        return True

    WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    res2 = user32.EnumWindows(WNDENUM(_cb), 0)
    print(f"EnumWindows on Default returned: {res2}, total HWNDs: {count}")
    print(f"Sample titles: {titles[:5]}")
