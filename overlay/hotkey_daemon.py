"""
COMPASS Global Hotkey Daemon
Registers system-wide hotkeys (e.g. Alt + Space) using Win32 RegisterHotKey.
Runs a thread-safe Win32 message pump with clean unregistration on shutdown.
"""

import ctypes
import ctypes.wintypes
import sys
import threading
from collections.abc import Callable

from backend.app.logging_config import logger

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VK_SPACE = 0x20
HOTKEY_ID_SUMMON = 9001
WM_HOTKEY = 0x0312


class GlobalHotkeyDaemon:
    def __init__(self, on_summon: Callable[[], None] | None = None):
        self.on_summon = on_summon
        self._thread: threading.Thread | None = None
        self._running = False
        self._registered = False

    def start(self) -> bool:
        if sys.platform != "win32":
            logger.info("GlobalHotkeyDaemon: Non-Windows platform; skipping Win32 hotkey.")
            return False

        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(target=self._msg_loop, daemon=True, name="COMPASS-Hotkey-Daemon")
        self._thread.start()
        return True

    def _msg_loop(self) -> None:
        user32 = ctypes.windll.user32
        # Register Alt + Space
        success = user32.RegisterHotKey(
            None,
            HOTKEY_ID_SUMMON,
            MOD_ALT | MOD_NOREPEAT,
            VK_SPACE,
        )
        if not success:
            # Fallback without MOD_NOREPEAT if older Windows API
            success = user32.RegisterHotKey(
                None,
                HOTKEY_ID_SUMMON,
                MOD_ALT,
                VK_SPACE,
            )

        if success:
            self._registered = True
            logger.info("GlobalHotkeyDaemon: Successfully registered Alt + Space global hotkey.")
        else:
            logger.warning(
                "GlobalHotkeyDaemon: Could not register Alt + Space (may be reserved by PowerToys or system)."
            )

        msg = ctypes.wintypes.MSG()
        while self._running:
            # Non-blocking or 100ms timeout message peek
            has_msg = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)  # PM_REMOVE = 1
            if has_msg:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_SUMMON:
                    logger.info("GlobalHotkeyDaemon: Alt + Space pressed.")
                    if self.on_summon:
                        try:
                            self.on_summon()
                        except Exception as e:
                            logger.error(f"Error in hotkey on_summon callback: {e}")
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                import time
                time.sleep(0.05)

        if self._registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_SUMMON)
            self._registered = False

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)


_hotkey_daemon = GlobalHotkeyDaemon()


def get_hotkey_daemon() -> GlobalHotkeyDaemon:
    return _hotkey_daemon
