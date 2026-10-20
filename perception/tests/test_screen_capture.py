"""
Unit tests for Desktop Screen Capture Engine.
"""

from unittest.mock import MagicMock, patch
from PIL import Image

from perception.screen_capture import ScreenCapture, capture_desktop, get_screen_capture


class TestScreenCapture:
    """Test screen capture resolution scaling, format conversion, and DPI handling."""

    def test_singleton_instance(self):
        c1 = get_screen_capture()
        c2 = get_screen_capture()
        assert c1 is c2

    def test_get_screen_resolution(self):
        sc = ScreenCapture()
        w, h = sc.get_screen_resolution()
        assert w > 0
        assert h > 0

    @patch("PIL.ImageGrab.grab")
    def test_capture_and_downscale(self, mock_grab):
        # Create a mock 4K display image (3840 x 2160)
        mock_img = Image.new("RGB", (3840, 2160), color=(100, 150, 200))
        mock_grab.return_value = mock_img

        sc = ScreenCapture(max_dimension=1440, jpeg_quality=80)
        snapshot = sc.capture_screen()

        assert snapshot.original_width == 3840
        assert snapshot.original_height == 2160
        # Scaled max dimension should be <= 1440
        assert max(snapshot.width, snapshot.height) <= 1440
        assert snapshot.scale_factor_x > 1.0
        assert snapshot.scale_factor_y > 1.0
        assert len(snapshot.image_bytes) > 0
        assert len(snapshot.base64_jpeg) > 0

    @patch("PIL.ImageGrab.grab")
    def test_capture_desktop_convenience_function(self, mock_grab):
        mock_img = Image.new("RGB", (1280, 720), color=(50, 50, 50))
        mock_grab.return_value = mock_img

        snapshot = capture_desktop()
        assert snapshot.original_width == 1280
        assert snapshot.original_height == 720
        assert snapshot.width == 1280
        assert snapshot.height == 720
        assert snapshot.scale_factor_x == 1.0
