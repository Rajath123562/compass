import tkinter as tk
import time
import ctypes
import ctypes.wintypes

root = tk.Tk()
root.title("COMPASS Test Window - Notepad Simulation")
root.geometry("400x300")
root.update()

user32 = ctypes.windll.user32
h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
if h_default:
    user32.SetThreadDesktop(h_default)

hwnd = user32.FindWindowW(None, "COMPASS Test Window - Notepad Simulation")
print(f"Tkinter window HWND: {hwnd}")

root.destroy()
