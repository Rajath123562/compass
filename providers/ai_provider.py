"""
COMPASS AI Provider — OmniRoute Compatibility Stub
Phase 2: NOT ACTIVATED. Architecture prepared for Phase 3+ integration.

This module defines the interfaces that an OmniRoute AI planner would implement.
No LLM, no model loading, no API calls are made in Phase 2.

Design intent:
  Phase 2:  perception + controlled action (no AI planning)
  Phase 3+: OmniRoute connects here, receives UISnapshot, returns ActionPlan

Future pipeline:
  UISnapshot → OmniRoute/AI Planner → ActionPlan → ActionValidator → Dispatcher
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanningRequest:
    """
    Input to an AI planner.
    Contains the user goal and the current UI state snapshot.
    """

    goal: str
    ui_snapshot: dict[str, Any]  # UISnapshot.to_dict()
    task_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannedAction:
    """A single step in a planned action sequence."""

    action_type: str  # "click", "type", "key", "focus"
    target_ref: dict[str, Any]  # ElementReference dict
    parameters: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""  # Human-readable explanation (if AI provides one)


@dataclass
class PlanningResult:
    """Output from an AI planner."""

    success: bool
    goal: str
    planned_actions: list[PlannedAction] = field(default_factory=list)
    error: str | None = None
    model_used: str | None = None
    latency_ms: float = 0.0


class AIPlannerProvider(ABC):
    """
    Abstract interface for AI planning providers.
    OmniRoute would implement this interface in Phase 3.

    Phase 2 provides only a disabled stub — no model is loaded or called.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'omniroute', 'gpt4', 'gemini')."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True if the provider is configured and ready."""
        ...

    @abstractmethod
    def plan(self, request: PlanningRequest) -> PlanningResult:
        """Generate an action plan for the given goal and UI state."""
        ...


class _DisabledAIProvider(AIPlannerProvider):
    """
    Phase 2 stub — always returns disabled status.
    Will be replaced by OmniRoute implementation in Phase 3.
    """

    @property
    def name(self) -> str:
        return "disabled_stub"

    @property
    def is_available(self) -> bool:
        return False

    def plan(self, request: PlanningRequest) -> PlanningResult:
        return PlanningResult(
            success=False,
            goal=request.goal,
            error=(
                "AI planning is not available in Phase 2. "
                "OmniRoute integration is planned for Phase 3."
            ),
        )


class ModelRouterProvider:
    """
    Placeholder for the model routing layer (OmniRoute).
    Selects the appropriate AI model based on the task and context.
    Phase 2: not activated.
    """

    def __init__(self):
        self._providers: dict[str, AIPlannerProvider] = {}
        self._active: AIPlannerProvider | None = _DisabledAIProvider()

    def register(self, provider: AIPlannerProvider) -> None:
        """Register an AI planning provider."""
        self._providers[provider.name] = provider

    def set_active(self, provider: AIPlannerProvider) -> None:
        """Set the currently active provider."""
        self._active = provider

    def get_active(self) -> AIPlannerProvider | None:
        """Return the currently active provider, or None if disabled."""
        if self._active and self._active.is_available:
            return self._active
        return None

    def get_status(self) -> dict[str, Any]:
        from providers.hardware_detector import get_system_hardware

        is_avail = self._active.is_available if self._active else False
        phase = (
            3 if (self._active and self._active.name == "omniroute" and is_avail) else 2
        )
        return {
            "active_provider": self._active.name if self._active else None,
            "is_available": is_avail,
            "registered_providers": list(self._providers.keys()),
            "phase": phase,
            "note": "OmniRoute active in Phase 3."
            if phase == 3
            else "AI planning not activated in Phase 2. OmniRoute planned for Phase 3.",
            "hardware": get_system_hardware() if phase == 3 else None,
        }


# Module-level singleton
model_router = ModelRouterProvider()
