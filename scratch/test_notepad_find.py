import subprocess
import time
import ctypes
import ctypes.wintypes
import psutil

p = subprocess.Popen(["notepad.exe"])
time.sleep(3)

print("Processes with notepad:")
for proc in psutil.process_iter(["pid", "name"]):
    if "notepad" in proc.info["name"].lower():
        print(f"  PID: {proc.info['pid']}, Name: {proc.info['name']}")

user32 = ctypes.windll.user32
windows = []
def _enum(hwnd, _):
    # even if not visible
    length = user32.GetWindowTextLengthW(hwnd)
    tbuf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, tbuf, length + 1)
    
    cbuf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cbuf, 256)
    
    pid = ctypes.wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    windows.append((hwnd, pid.value, user32.IsWindowVisible(hwnd), cbuf.value, tbuf.value))
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows(WNDENUM(_enum), 0)

notepad_pids = {proc.info["pid"] for proc in psutil.process_iter(["pid", "name"]) if "notepad" in proc.info["name"].lower()}
print("Windows belonging to notepad PIDs:")
for w in windows:
    if w[1] in notepad_pids:
        print(f"  HWND={w[0]}, PID={w[1]}, Visible={w[2]}, Class='{w[3]}', Title='{w[4]}'")

p.kill()
