"""
Unit tests for providers/ (OmniRoute compatibility layer and provider wrappers).
"""

from providers.ai_provider import (
    PlannedAction,
    PlanningRequest,
    PlanningResult,
    _DisabledAIProvider,
    model_router,
)
from providers.screen_provider import screen_provider
from providers.uia_provider import uia_provider


class TestAIProviderStub:
    def test_disabled_provider_properties(self):
        p = _DisabledAIProvider()
        assert p.name == "disabled_stub"
        assert p.is_available is False

    def test_disabled_provider_plan_returns_disabled_error(self):
        p = _DisabledAIProvider()
        req = PlanningRequest(goal="Test goal", ui_snapshot={})
        res = p.plan(req)
        assert isinstance(res, PlanningResult)
        assert res.success is False
        assert "not available in Phase 2" in (res.error or "")

    def test_model_router_status(self):
        status = model_router.get_status()
        assert status["phase"] == 2
        assert status["is_available"] is False
        assert status["active_provider"] == "disabled_stub"

    def test_planning_request_dataclass(self):
        req = PlanningRequest(
            goal="Open Notepad",
            ui_snapshot={"window": {"title": "Desktop"}},
            task_id="task_123",
            context={"env": "win11"},
        )
        assert req.goal == "Open Notepad"
        assert req.task_id == "task_123"
        assert req.context["env"] == "win11"

    def test_planned_action_dataclass(self):
        action = PlannedAction(
            action_type="click",
            target_ref={"hwnd": 1234, "control_type": "Button"},
            rationale="Click the OK button",
        )
        assert action.action_type == "click"
        assert action.rationale == "Click the OK button"


class TestPerceptionProviders:
    def test_uia_provider_metadata(self):
        assert uia_provider.name == "uia"
        assert "UI Automation" in uia_provider.description

    def test_screen_provider_metadata(self):
        assert screen_provider.name == "gdi_screen"
        assert "GDI" in screen_provider.description

    def test_screen_provider_capabilities(self):
        caps = screen_provider.get_capabilities()
        assert "gdi_available" in caps
        assert "pillow_available" in caps
