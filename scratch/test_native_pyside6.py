import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QLineEdit, QPushButton, QVBoxLayout, QWidget
import ctypes

app = QApplication.instance() or QApplication(sys.argv)
win = QMainWindow()
win.setWindowTitle("Notepad")

central = QWidget()
layout = QVBoxLayout(central)
edit = QLineEdit("Hello COMPASS")
btn = QPushButton("Save")
layout.addWidget(edit)
layout.addWidget(btn)
win.setCentralWidget(central)
win.show()
app.processEvents()

user32 = ctypes.windll.user32
hwnd = win.winId()
print(f"PySide6 Window HWND: {hwnd}")

from perception import uia_inspector
tree = uia_inspector.get_element_tree(int(hwnd), depth=3)
print("UIA Elements found:", len(tree.get("elements", [])))
for el in tree.get("elements", []):
    print("  Candidate:", el.get("control_type"), el.get("name"), el.get("bounding_box"))

win.close()
