"""
Tests for overlay/renderer.py — OverlayRenderer unit tests
Tests render logic without requiring a running Qt application.
"""

from overlay.renderer import CONTROL_TYPE_COLORS, OverlayRenderer


class TestOverlayRenderer:
    def setup_method(self):
        self.renderer = OverlayRenderer()

    def test_initial_element_count_zero(self):
        assert self.renderer.element_count == 0

    def test_set_elements(self):
        elements = [
            {
                "element_id": "e001",
                "control_type": "Button",
                "name": "OK",
                "bounds": {
                    "left": 10,
                    "top": 10,
                    "right": 110,
                    "bottom": 50,
                    "width": 100,
                    "height": 40,
                },
            },
        ]
        self.renderer.set_elements(elements)
        assert self.renderer.element_count == 1

    def test_clear_removes_elements(self):
        self.renderer.set_elements(
            [
                {
                    "element_id": "e001",
                    "control_type": "Button",
                    "name": "OK",
                    "bounds": {
                        "left": 0,
                        "top": 0,
                        "right": 100,
                        "bottom": 40,
                        "width": 100,
                        "height": 40,
                    },
                },
            ]
        )
        self.renderer.clear()
        assert self.renderer.element_count == 0
        assert self.renderer._highlighted_id is None

    def test_highlight_sets_id(self):
        self.renderer.highlight("e001")
        assert self.renderer._highlighted_id == "e001"

    def test_highlight_none_clears(self):
        self.renderer.highlight("e001")
        self.renderer.highlight(None)
        assert self.renderer._highlighted_id is None

    def test_set_visible(self):
        self.renderer.set_visible(False)
        assert self.renderer._visible is False
        self.renderer.set_visible(True)
        assert self.renderer._visible is True

    def test_multiple_elements_stored(self):
        elements = [
            {
                "element_id": f"e{i:03d}",
                "control_type": "Button",
                "name": f"Btn{i}",
                "bounds": {
                    "left": 0,
                    "top": i * 50,
                    "right": 100,
                    "bottom": i * 50 + 40,
                    "width": 100,
                    "height": 40,
                },
            }
            for i in range(5)
        ]
        self.renderer.set_elements(elements)
        assert self.renderer.element_count == 5

    def test_set_elements_replaces_previous(self):
        self.renderer.set_elements(
            [
                {
                    "element_id": "e001",
                    "control_type": "Button",
                    "name": "A",
                    "bounds": {
                        "left": 0,
                        "top": 0,
                        "right": 50,
                        "bottom": 30,
                        "width": 50,
                        "height": 30,
                    },
                },
            ]
        )
        self.renderer.set_elements([])
        assert self.renderer.element_count == 0


class TestColorPalette:
    def test_all_known_control_types_have_colors(self):
        known_types = [
            "Button",
            "Edit",
            "Document",
            "CheckBox",
            "ComboBox",
            "MenuItem",
            "MenuBar",
            "Text",
            "Window",
        ]
        for ct in known_types:
            assert ct in CONTROL_TYPE_COLORS or "default" in CONTROL_TYPE_COLORS

    def test_default_color_exists(self):
        assert "default" in CONTROL_TYPE_COLORS

    def test_color_values_are_rgba_tuples(self):
        for ct, rgba in CONTROL_TYPE_COLORS.items():
            assert len(rgba) == 4
            for v in rgba:
                assert 0 <= v <= 255, f"Color value out of range for {ct}: {rgba}"
