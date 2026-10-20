"""
COMPASS Phase 6 — Context Analyzer
Extracts and structures hierarchical UI relationships from live UIA element trees:
Window -> Application -> Dialog -> Panel -> Toolbar -> Menu -> Control -> State.
Detects unexpected modal dialogs, alerts, and modal blockers with uncertainty estimation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UIContextNode(BaseModel):
    """Hierarchical node representing an element within its structural UI tree."""

    element_id: str
    name: str = ""
    control_type: str = ""
    automation_id: str = ""
    role: str = "control"  # window, dialog, panel, toolbar, menu, control
    bounds: dict[str, Any] | None = None
    is_modal: bool = False
    is_enabled: bool = True
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)


class ContextAnalysisResult(BaseModel):
    """Aggregated structural context of the current foreground workspace."""

    app_name: str = ""
    window_title: str = ""
    hwnd: int | None = None
    has_modal_dialog: bool = False
    active_dialog_title: str | None = None
    nodes: dict[str, UIContextNode] = Field(default_factory=dict)
    panels: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    uncertainty_reasons: list[str] = Field(default_factory=list)


class UIContextAnalyzer:
    """
    Analyzes UIA trees and foreground window state to produce a structured,
    contextual understanding of the desktop without vision hallucinations.
    """

    MODAL_INDICATORS = [  # noqa: RUF012
        "dialog",
        "confirm",
        "alert",
        "prompt",
        "warning",
        "save as",
        "open",
        "print",
        "error",
        "properties",
        "settings",
    ]

    PANEL_TYPES = ["Pane", "Group", "Tab", "Custom", "ToolBar", "MenuBar"]  # noqa: RUF012

    def analyze_context(
        self, window_info: dict[str, Any] | None, uia_tree: dict[str, Any] | None
    ) -> ContextAnalysisResult:
        """
        Analyze live window information and UIA element tree to construct structural context.
        """
        if not window_info and not uia_tree:
            return ContextAnalysisResult(
                confidence=0.0,
                uncertainty_reasons=["No window_info or uia_tree available."],
            )

        w_title = (window_info or {}).get("title", "")
        hwnd = (window_info or {}).get("hwnd")
        app_name = (window_info or {}).get("process_name", "") or w_title.split(" - ")[
            -1
        ]

        result = ContextAnalysisResult(
            app_name=app_name, window_title=w_title, hwnd=hwnd
        )

        # Check if window title suggests an active dialog
        lower_title = w_title.lower()
        if any(ind in lower_title for ind in self.MODAL_INDICATORS):
            result.has_modal_dialog = True
            result.active_dialog_title = w_title

        # Traverse UIA Tree
        if uia_tree:
            self._traverse_tree(uia_tree, None, result)

        if not result.nodes:
            result.confidence = 0.5
            result.uncertainty_reasons.append("UIA tree contains no actionable nodes.")

        return result

    def _traverse_tree(
        self,
        node: dict[str, Any],
        parent_id: str | None,
        result: ContextAnalysisResult,
    ) -> str | None:
        """Recursively index nodes into the context hierarchy."""
        if not isinstance(node, dict):
            return None

        name = node.get("name") or ""
        ctype = node.get("control_type") or "Unknown"
        autoid = node.get("automation_id") or ""
        node_id = f"{ctype}_{autoid}_{name}_{len(result.nodes)}"

        role = "control"
        if ctype in ["Window", "Dialog"]:
            role = (
                "dialog"
                if "dialog" in ctype.lower() or "dialog" in name.lower()
                else "window"
            )
            if role == "dialog":
                result.has_modal_dialog = True
                result.active_dialog_title = name or result.active_dialog_title
        elif ctype in self.PANEL_TYPES:
            role = "panel"
            result.panels.append(name or ctype)
        elif ctype in ["MenuItem", "Menu"]:
            role = "menu"

        ctx_node = UIContextNode(
            element_id=node_id,
            name=name,
            control_type=ctype,
            automation_id=autoid,
            role=role,
            bounds=node.get("bounds"),
            is_enabled=node.get("is_enabled", True),
            parent_id=parent_id,
        )

        result.nodes[node_id] = ctx_node

        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                child_id = self._traverse_tree(child, node_id, result)
                if child_id:
                    ctx_node.children.append(child_id)

        return node_id
