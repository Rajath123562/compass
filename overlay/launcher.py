"""
COMPASS Overlay Process Launcher with Local IPC Server
Runs the PySide6 overlay window as a standalone process and listens
on 127.0.0.1:8001 for highlight and clear commands from the automation layer.
"""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from overlay.win32_helper import set_dpi_awareness
from overlay.window import CompassOverlayWindow


class OverlayBridge(QObject):
    highlight_signal = Signal(list, int)
    clear_signal = Signal()


bridge = OverlayBridge()


class OverlayRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/highlight":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                elements = data.get("elements", [])
                duration_ms = data.get("duration_ms", 2000)
                bridge.highlight_signal.emit(elements, duration_ms)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        elif self.path == "/clear":
            bridge.clear_signal.emit()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "cleared"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "overlay_active"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress verbose HTTP server logs


def main():
    parser = argparse.ArgumentParser(description="COMPASS Overlay Launcher")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Auto-close after N seconds (0 = keep open)",
    )
    parser.add_argument(
        "--click-through",
        action="store_true",
        default=True,
        help="Enable click-through",
    )
    parser.add_argument(
        "--no-click-through",
        action="store_false",
        dest="click_through",
        help="Disable click-through",
    )
    args = parser.parse_args()

    # 1. Enable Windows DPI Awareness
    set_dpi_awareness()

    # 2. Create Qt Application
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 3. Create and show overlay window
    window = CompassOverlayWindow(
        click_through=args.click_through, auto_close_sec=args.duration
    )
    window.show()

    def handle_highlight(elements, duration_ms):
        normalized = []
        for el in elements:
            bounds = el.get("bounds") or el.get("bounding_box") or {}
            left = bounds.get("left", 0)
            top = bounds.get("top", 0)
            width = bounds.get("width") or max(0, bounds.get("right", left) - left)
            height = bounds.get("height") or max(0, bounds.get("bottom", top) - top)
            normalized.append(
                {
                    "bounds": {
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height,
                    },
                    "control_type": el.get("control_type", "Button"),
                    "name": el.get("name", "Target"),
                    "element_id": el.get("element_id", "el_target"),
                }
            )
        window.update_elements(normalized)
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, window.clear_annotations)

    bridge.highlight_signal.connect(handle_highlight)
    bridge.clear_signal.connect(window.clear_annotations)

    # 4. Start HTTP server daemon thread on port 8001
    def run_server():
        try:
            server = HTTPServer(("127.0.0.1", 8001), OverlayRequestHandler)
            server.serve_forever()
        except Exception:
            pass

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    print(
        f"[COMPASS Overlay] Running (PID: {QApplication.applicationPid()}, click-through: {args.click_through}, IPC: 127.0.0.1:8001)",
        flush=True,
    )
    exit_code = app.exec()
    print("[COMPASS Overlay] Closed cleanly.", flush=True)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
