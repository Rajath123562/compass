"""
Tests for perception/element_filter.py
Pure unit tests — no Windows runtime dependency.
"""

from perception import element_filter
from perception.models import BoundingRect, UIElement


def _make_element(
    control_type="Button",
    name="Test",
    is_enabled=True,
    is_visible=True,
    is_offscreen=False,
    is_focused=False,
    bounds=None,
    element_id="e0001",
    text="",
) -> UIElement:
    if bounds is None:
        bounds = BoundingRect(left=0, top=0, right=100, bottom=40)
    return UIElement(
        element_id=element_id,
        control_type=control_type,
        name=name,
        is_enabled=is_enabled,
        is_visible=is_visible,
        is_offscreen=is_offscreen,
        is_focused=is_focused,
        bounds=bounds,
        text=text,
        source="uia",
        confidence=None,
    )


class TestFilterInteractive:
    def test_returns_interactive_types(self):
        elements = [
            _make_element("Button", "OK"),
            _make_element("Edit", "Input"),
            _make_element("Text", "Label"),  # non-interactive
            _make_element("StatusBar", "Status"),  # non-interactive
        ]
        result = element_filter.filter_interactive(elements)
        types = {e.control_type for e in result}
        assert "Button" in types
        assert "Edit" in types
        assert "Text" not in types
        assert "StatusBar" not in types

    def test_empty_list(self):
        assert element_filter.filter_interactive([]) == []


class TestFilterVisible:
    def test_keeps_visible_elements(self):
        elements = [
            _make_element(
                "Button", "OK", is_visible=True, bounds=BoundingRect(0, 0, 100, 40)
            ),
            _make_element(
                "Button", "Hidden", is_visible=False, bounds=BoundingRect(0, 0, 100, 40)
            ),
            _make_element(
                "Button", "ZeroBounds", is_visible=True, bounds=BoundingRect(0, 0, 0, 0)
            ),
        ]
        result = element_filter.filter_visible(elements)
        assert len(result) == 1
        assert result[0].name == "OK"

    def test_empty_list(self):
        assert element_filter.filter_visible([]) == []


class TestFilterEditable:
    def test_only_edit_and_document(self):
        elements = [
            _make_element("Edit", "TextBox"),
            _make_element("Document", "Doc"),
            _make_element("Button", "NotEditable"),
            _make_element("Text", "Label"),
        ]
        result = element_filter.filter_editable(elements)
        types = {e.control_type for e in result}
        assert "Edit" in types
        assert "Document" in types
        assert "Button" not in types

    def test_empty_list(self):
        assert element_filter.filter_editable([]) == []


class TestFindByText:
    def test_exact_match(self):
        elements = [
            _make_element("Button", "Save"),
            _make_element("Button", "Save As"),
        ]
        result = element_filter.find_by_text(elements, "Save", fuzzy=False)
        assert len(result) == 1
        assert result[0].name == "Save"

    def test_fuzzy_match(self):
        elements = [
            _make_element("Button", "Save"),
            _make_element("Button", "Save As"),
            _make_element("Button", "Cancel"),
        ]
        result = element_filter.find_by_text(elements, "save", fuzzy=True)
        assert len(result) == 2

    def test_text_field_match(self):
        elements = [_make_element("Edit", "Editor", text="hello world")]
        result = element_filter.find_by_text(elements, "hello world", fuzzy=False)
        assert len(result) == 1

    def test_no_match(self):
        elements = [_make_element("Button", "OK")]
        result = element_filter.find_by_text(elements, "Cancel")
        assert result == []

    def test_case_insensitive_by_default(self):
        elements = [_make_element("Button", "SAVE")]
        result = element_filter.find_by_text(elements, "save", fuzzy=True)
        assert len(result) == 1


class TestFindByType:
    def test_matches_control_type(self):
        elements = [
            _make_element("Button", "OK"),
            _make_element("Edit", "Input"),
            _make_element("Button", "Cancel"),
        ]
        result = element_filter.find_by_type(elements, "Button")
        assert len(result) == 2

    def test_case_insensitive(self):
        elements = [_make_element("Button", "OK")]
        result = element_filter.find_by_type(elements, "button")
        assert len(result) == 1

    def test_no_match(self):
        elements = [_make_element("Button", "OK")]
        result = element_filter.find_by_type(elements, "Edit")
        assert result == []


class TestRankByRelevance:
    def test_interactive_elements_score_higher(self):
        elements = [
            _make_element("Text", "Label", element_id="e001"),  # static
            _make_element("Button", "OK", element_id="e002"),  # interactive
        ]
        ranked = element_filter.rank_by_relevance(elements)
        assert ranked[0].element_id == "e002"  # Button should be first

    def test_focused_element_gets_boost(self):
        elements = [
            _make_element("Button", "Save", is_focused=False, element_id="e001"),
            _make_element("Button", "Cancel", is_focused=True, element_id="e002"),
        ]
        ranked = element_filter.rank_by_relevance(elements)
        assert ranked[0].element_id == "e002"  # Focused gets +1

    def test_disabled_elements_score_lower(self):
        elements = [
            _make_element("Button", "Save", is_enabled=True, element_id="e001"),
            _make_element("Button", "Delete", is_enabled=False, element_id="e002"),
        ]
        ranked = element_filter.rank_by_relevance(elements)
        assert ranked[0].element_id == "e001"

    def test_empty_list(self):
        assert element_filter.rank_by_relevance([]) == []


class TestGetBestEditTarget:
    def test_prefers_focused_edit(self):
        elements = [
            _make_element("Edit", "Unfocused", is_focused=False, element_id="e001"),
            _make_element("Edit", "Focused", is_focused=True, element_id="e002"),
        ]
        result = element_filter.get_best_edit_target(elements)
        assert result is not None
        assert result.element_id == "e002"

    def test_returns_none_if_no_editable(self):
        elements = [_make_element("Button", "OK")]
        result = element_filter.get_best_edit_target(elements)
        assert result is None

    def test_returns_enabled_visible_fallback(self):
        elements = [
            _make_element("Edit", "DisabledEdit", is_enabled=False, element_id="e001"),
            _make_element("Edit", "EnabledEdit", is_enabled=True, element_id="e002"),
        ]
        result = element_filter.get_best_edit_target(elements)
        assert result is not None
        assert result.element_id == "e002"


class TestSummarizeElements:
    def test_summary_counts(self):
        elements = [
            _make_element("Button", "OK", is_enabled=True, is_visible=True),
            _make_element("Edit", "Input", is_enabled=True, is_visible=True),
            _make_element("Text", "Label", is_enabled=True, is_visible=True),
        ]
        summary = element_filter.summarize_elements(elements)
        assert summary["total"] == 3
        assert summary["interactive"] == 2  # Button + Edit
        assert summary["editable"] == 1  # Only Edit
        assert "by_control_type" in summary
        assert summary["by_control_type"]["Button"] == 1
        assert summary["by_control_type"]["Edit"] == 1

    def test_empty_summary(self):
        summary = element_filter.summarize_elements([])
        assert summary["total"] == 0
        assert summary["interactive"] == 0
