import tkinter as tk
import threading
import time
import ctypes

user32 = ctypes.windll.user32

def run_win():
    root = tk.Tk()
    root.title('Test Notepad Window')
    entry = tk.Entry(root)
    entry.pack()
    root.mainloop()

t = threading.Thread(target=run_win, daemon=True)
t.start()
time.sleep(1)

found = []
def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if 'test notepad window' in buf.value.lower():
            found.append((hwnd, buf.value))
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUM(enum_cb), 0)
print('Found window in current desktop:', found)
