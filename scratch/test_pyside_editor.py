import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QTextEdit, QMainWindow
from perception import uia_inspector

app = QApplication.instance() or QApplication(sys.argv)
win = QMainWindow()
win.setWindowTitle("*Untitled - Notepad")
win.resize(800, 600)
editor = QTextEdit(win)
editor.setObjectName("ContentElement")
win.setCentralWidget(editor)
win.show()
app.processEvents()

hwnd = int(win.winId())
print("Created PySide6 Notepad window HWND:", hwnd)

tree = uia_inspector.get_element_tree(hwnd, depth=3)
print("Elements found in PySide6 window:", len(tree.get("elements", [])))
for el in tree.get("elements", []):
    print("  Elem:", el.get("name"), el.get("control_type"))

win.close()
app.processEvents()
