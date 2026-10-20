"""
Tests for perception/service.py — PerceptionService
"""

import sys
import time

import pytest

from perception.service import PerceptionService


class TestPerceptionService:
    def setup_method(self):
        self.svc = PerceptionService(
            poll_interval_sec=0.2,
            capture_enabled=False,
            max_depth=2,
            max_elements=50,
        )

    def test_get_status_returns_dict(self):
        status = self.svc.get_status()
        assert isinstance(status, dict)
        assert "polling" in status
        assert "uia" in status
        assert "screen_capture" in status

    def test_initial_polling_false(self):
        status = self.svc.get_status()
        assert status["polling"] is False

    def test_get_snapshot_returns_snapshot(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        snapshot = self.svc.get_snapshot()
        assert snapshot is not None
        assert snapshot.timestamp is not None
        assert snapshot.timestamp.year >= 2020
        assert isinstance(snapshot.elements, list)

    def test_polling_start_stop(self):
        started = self.svc.start_polling()
        assert started is True
        time.sleep(0.1)
        assert self.svc.get_status()["polling"] is True
        self.svc.stop_polling()
        assert self.svc.get_status()["polling"] is False

    def test_polling_start_twice_returns_false(self):
        self.svc.start_polling()
        result = self.svc.start_polling()
        assert result is False
        self.svc.stop_polling()

    def test_subscriber_called_on_poll(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        received = []
        self.svc.subscribe(lambda s: received.append(s))
        self.svc.start_polling()
        time.sleep(0.5)
        self.svc.stop_polling()
        assert len(received) >= 1

    def test_unsubscribe(self):
        received = []
        cb = lambda s: received.append(s)
        self.svc.subscribe(cb)
        self.svc.unsubscribe(cb)
        self.svc.start_polling()
        time.sleep(0.4)
        self.svc.stop_polling()
        assert len(received) == 0

    def teardown_method(self):
        self.svc.stop_polling()
