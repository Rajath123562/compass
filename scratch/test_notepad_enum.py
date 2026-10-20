import subprocess
import time
import ctypes
import psutil

user32 = ctypes.windll.user32

p = subprocess.Popen(['notepad.exe'])
time.sleep(2)
print('Notepad pid:', p.pid)
for proc in psutil.process_iter(['pid', 'name']):
    if 'notepad' in proc.info['name'].lower():
        print('Found proc:', proc.info)

def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if 'notepad' in buf.value.lower():
                print('Found window:', hwnd, buf.value)
    return True

WNDENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUM(enum_cb), 0)

# Check thread desktop
h_desk = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
name_buf = ctypes.create_unicode_buffer(256)
user32.GetUserObjectInformationW(h_desk, 2, name_buf, 512, None)
print("Current thread desktop:", name_buf.value)

# Try attaching to Default desktop
h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
print("OpenDesktop Default:", h_def)
if h_def:
    user32.SetThreadDesktop(h_def)
    print("Enumerating on Default desktop:")
    user32.EnumWindows(WNDENUM(enum_cb), 0)

try:
    p.kill()
except Exception:
    pass
for proc in psutil.process_iter(['pid', 'name']):
    if 'notepad' in proc.info['name'].lower():
        try:
            proc.kill()
        except:
            pass
