"""
Unit tests for UIContextAnalyzer (Phase 6, Capability F, §8, §10).
Verifies structural UI hierarchy extraction, modal dialog detection,
and uncertainty handling when UIA elements are ambiguous or missing.
"""

from perception.context_analyzer import ContextAnalysisResult, UIContextAnalyzer


def test_analyze_context_with_modal_dialog():
    """Detects modal dialog indicators in window title and UIA nodes."""
    analyzer = UIContextAnalyzer()
    win_info = {
        "title": "Confirm Save - Notepad",
        "hwnd": 12345,
        "process_name": "notepad.exe",
    }
    uia_tree = {
        "name": "Confirm Save",
        "control_type": "Dialog",
        "children": [
            {"name": "Save", "control_type": "Button", "automation_id": "btn_save"},
            {"name": "Cancel", "control_type": "Button", "automation_id": "btn_cancel"},
        ],
    }

    result: ContextAnalysisResult = analyzer.analyze_context(win_info, uia_tree)
    assert result.has_modal_dialog is True
    assert "Confirm Save" in result.active_dialog_title
    assert len(result.nodes) >= 3


def test_analyze_context_hierarchy_panels():
    """Extracts panels, toolbars, and controls properly."""
    analyzer = UIContextAnalyzer()
    win_info = {"title": "Calculator", "hwnd": 22222, "process_name": "calc.exe"}
    uia_tree = {
        "name": "Calculator",
        "control_type": "Window",
        "children": [
            {
                "name": "Number Pad",
                "control_type": "Group",
                "children": [
                    {
                        "name": "Seven",
                        "control_type": "Button",
                        "automation_id": "btn_7",
                    }
                ],
            }
        ],
    }

    result = analyzer.analyze_context(win_info, uia_tree)
    assert result.has_modal_dialog is False
    assert "Number Pad" in result.panels
    assert len(result.nodes) >= 3


def test_analyze_context_empty_fallback_uncertainty():
    """Empty or missing tree returns uncertainty reasons rather than hallucinating."""
    analyzer = UIContextAnalyzer()
    result = analyzer.analyze_context(None, None)
    assert result.confidence == 0.0
    assert len(result.uncertainty_reasons) > 0
