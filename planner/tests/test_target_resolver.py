"""
Unit tests for TargetResolver and Ambiguity Detection.
"""

from planner.models import TargetReference
from planner.target_resolver import TargetResolver


class TestTargetResolver:
    def setup_method(self):
        self.resolver = TargetResolver()
        self.elements = [
            {
                "name": "Save",
                "control_type": "Button",
                "automation_id": "btn_save",
                "runtime_id": "rid_1",
                "hwnd": 100,
            },
            {
                "name": "Cancel",
                "control_type": "Button",
                "automation_id": "btn_cancel",
                "runtime_id": "rid_2",
                "hwnd": 100,
            },
            {
                "name": "OK",
                "control_type": "Button",
                "automation_id": "btn_ok_1",
                "runtime_id": "rid_3",
                "hwnd": 100,
            },
            {
                "name": "OK",
                "control_type": "Button",
                "automation_id": "btn_ok_2",
                "runtime_id": "rid_4",
                "hwnd": 100,
            },
        ]

    def test_resolve_by_runtime_id(self):
        ref = TargetReference(runtime_id="rid_2")
        res = self.resolver.resolve(ref, self.elements)
        assert res.success is True
        assert res.element["automation_id"] == "btn_cancel"

    def test_resolve_by_automation_id(self):
        ref = TargetReference(automation_id="btn_save")
        res = self.resolver.resolve(ref, self.elements)
        assert res.success is True
        assert res.element["name"] == "Save"

    def test_resolve_ambiguity_rejected(self):
        # Two elements named "OK"
        ref = TargetReference(name="OK")
        res = self.resolver.resolve(ref, self.elements)
        assert res.success is False
        assert res.is_ambiguous is True
        assert "Ambiguous target" in res.error

    def test_resolve_non_existent(self):
        ref = TargetReference(name="SubmitNonExistent")
        res = self.resolver.resolve(ref, self.elements)
        assert res.success is False
        assert res.is_ambiguous is False
        assert "could not be resolved" in res.error
