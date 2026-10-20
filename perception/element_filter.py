"""
COMPASS Element Filter
Deterministic heuristic filtering and ranking of UI elements.

Accepts either UIElement objects or dict representations (e.g. from API/tree serialization).

NOTE: rank_by_relevance() is a lightweight deterministic heuristic,
NOT an AI saliency model. It ranks elements by structural properties
(interactivity, enabled state, visibility, named content, bounds)
without any semantic or visual understanding.
"""

from typing import Any

# Control types that support user interaction
INTERACTIVE_CONTROL_TYPES = {
    "Button",
    "CheckBox",
    "ComboBox",
    "Edit",
    "Hyperlink",
    "ListItem",
    "MenuItem",
    "RadioButton",
    "Slider",
    "Spinner",
    "SplitButton",
    "Tab",
    "TabItem",
    "TreeItem",
    "DataItem",
}

# Control types that are editable (accept text input)
EDITABLE_CONTROL_TYPES = {"Edit", "Document"}

# Control types used for reading (non-interactive)
STATIC_CONTROL_TYPES = {
    "Text",
    "Image",
    "ProgressBar",
    "StatusBar",
    "TitleBar",
    "Separator",
    "ToolTip",
}


def _get(el: Any, attr: str, default: Any = None) -> Any:
    if isinstance(el, dict):
        return el.get(attr, default)
    return getattr(el, attr, default)


def _is_bounds_valid(el: Any) -> bool:
    b = _get(el, "bounds")
    if hasattr(b, "is_valid"):
        return bool(b.is_valid)
    if isinstance(b, dict):
        return (b.get("width", 0) or 0) > 0 and (b.get("height", 0) or 0) > 0
    return False


def _bounds_area(el: Any) -> int:
    b = _get(el, "bounds")
    if hasattr(b, "area"):
        return int(b.area)
    if isinstance(b, dict):
        w = b.get("width", 0) or 0
        h = b.get("height", 0) or 0
        return int(w * h)
    return 0


def filter_interactive(elements: list[Any]) -> list[Any]:
    """
    Return elements that belong to interactive control types.
    Does NOT guarantee an action will succeed (use action_validator for that).
    """
    return [e for e in elements if _get(e, "control_type") in INTERACTIVE_CONTROL_TYPES]


def filter_visible(elements: list[Any]) -> list[Any]:
    """Return elements that are visible and have a valid non-zero bounding rect."""
    return [e for e in elements if _get(e, "is_visible", False) and _is_bounds_valid(e)]


def filter_enabled(elements: list[Any]) -> list[Any]:
    """Return elements that are enabled."""
    return [e for e in elements if _get(e, "is_enabled", False)]


def filter_editable(elements: list[Any]) -> list[Any]:
    """Return elements that accept text input (Edit, Document controls)."""
    return [e for e in elements if _get(e, "control_type") in EDITABLE_CONTROL_TYPES]


def find_by_text(
    elements: list[Any],
    text: str,
    fuzzy: bool = False,
    case_sensitive: bool = False,
) -> list[Any]:
    """
    Find elements whose name or text matches the query.

    Args:
        text:           Query string.
        fuzzy:          If True, use substring match; if False, exact match.
        case_sensitive: If True, match is case-sensitive.

    Returns:
        List of matching UIElement or dict objects.
    """
    if not case_sensitive:
        text = text.lower()

    results = []
    for el in elements:
        name = _get(el, "name", "") or ""
        txt = _get(el, "text", "") or ""
        el_name = name if case_sensitive else name.lower()
        el_text = txt if case_sensitive else txt.lower()

        if fuzzy:
            if text in el_name or text in el_text:
                results.append(el)
        else:
            if text == el_name or text == el_text:
                results.append(el)
    return results


def find_by_type(elements: list[Any], control_type: str) -> list[Any]:
    """Return elements matching the specified control type (case-insensitive)."""
    ct_lower = control_type.lower()
    return [e for e in elements if (_get(e, "control_type") or "").lower() == ct_lower]


def rank_by_relevance(elements: list[Any]) -> list[Any]:
    """
    Sort elements by a lightweight deterministic relevance heuristic.

    Ranking factors (higher = more relevant):
      1. Interactive control type (+4)
      2. Enabled state (+3)
      3. Visible and non-offscreen (+3)
      4. Non-empty meaningful name (+2)
      5. Reasonable bounding area (> 100 px²) (+2)
      6. Focused state (+1)

    This is a structural ranking, not semantic AI saliency.
    Future phases may extend this with visual or model-based scoring.
    """

    def _score(el: Any) -> int:
        score = 0
        ct = _get(el, "control_type")
        if ct in INTERACTIVE_CONTROL_TYPES:
            score += 4
        if _get(el, "is_enabled", False):
            score += 3
        if _get(el, "is_visible", False) and not _get(el, "is_offscreen", False):
            score += 3
        name = _get(el, "name", "")
        if name and name.strip():
            score += 2
        if _bounds_area(el) > 100:
            score += 2
        if _get(el, "is_focused", False):
            score += 1
        return score

    return sorted(elements, key=_score, reverse=True)


def get_best_edit_target(elements: list[Any]) -> Any | None:
    """
    Return the most suitable editable text element in the list.
    Prefers focused > enabled+visible > any editable.
    """
    editable = filter_editable(elements)
    if not editable:
        return None

    # Prefer focused element first
    focused = [e for e in editable if _get(e, "is_focused", False)]
    if focused:
        return focused[0]

    # Then enabled + visible
    ev = [
        e
        for e in editable
        if _get(e, "is_enabled", False) and _get(e, "is_visible", False)
    ]
    if ev:
        return ev[0]

    return editable[0]


def summarize_elements(elements: list[Any]) -> dict:
    """Return a summary dict of element counts by type and state."""
    by_type: dict = {}
    for el in elements:
        ct = _get(el, "control_type") or "Unknown"
        by_type[ct] = by_type.get(ct, 0) + 1

    return {
        "total": len(elements),
        "interactive": len(filter_interactive(elements)),
        "visible": len(filter_visible(elements)),
        "enabled": len(filter_enabled(elements)),
        "editable": len(filter_editable(elements)),
        "by_control_type": by_type,
    }
