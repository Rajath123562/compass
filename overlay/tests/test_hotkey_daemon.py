"""
Unit tests for Global Hotkey Daemon (Alt + Space summon).
"""

from overlay.hotkey_daemon import GlobalHotkeyDaemon, get_hotkey_daemon


def test_hotkey_daemon_initialization():
    called = []
    daemon = GlobalHotkeyDaemon(on_summon=lambda: called.append(True))
    assert daemon._running is False
    assert daemon.on_summon is not None


def test_hotkey_daemon_lifecycle():
    daemon = GlobalHotkeyDaemon()
    started = daemon.start()
    assert isinstance(started, bool)
    assert daemon._running is True

    # Clean shutdown
    daemon.stop()
    assert daemon._running is False


def test_get_hotkey_daemon_singleton():
    d1 = get_hotkey_daemon()
    d2 = get_hotkey_daemon()
    assert d1 is d2
