"""
Unit tests for TaskDecomposer & PlanValidator (Phase 6, Capability A, D, §3, §6).
Verifies deterministic templates, rule-based decomposition, plan validation,
risk categorization, and rejection of invalid plans.
"""

from planner.models import RiskLevel, TaskStep
from planner.plan_validator import PlanValidator
from planner.task_decomposer import TaskDecomposer


def test_decompose_notepad_template():
    """Test deterministic Notepad decomposition produces ordered steps with dependencies."""
    decomposer = TaskDecomposer()
    plan = decomposer.decompose(
        "task_101", "Open Notepad and type 'Hello COMPASS Phase 6'"
    )

    assert plan.task_id == "task_101"
    assert len(plan.steps) >= 2
    assert plan.steps[0].step_id == "step_1"
    assert "Notepad" in plan.steps[0].goal
    assert plan.steps[1].step_id == "step_2"
    assert plan.steps[1].dependencies == ["step_1"]
    assert (
        "Hello COMPASS Phase 6" in plan.steps[1].candidate_actions[0].parameters["text"]
    )


def test_decompose_notepad_with_save():
    """Test Notepad decomposition with save instruction generates 3 steps."""
    decomposer = TaskDecomposer()
    plan = decomposer.decompose("task_102", "Open Notepad, write notes, and save file")

    assert len(plan.steps) == 3
    assert plan.steps[2].step_id == "step_3"
    assert plan.steps[2].dependencies == ["step_2"]
    assert "Save" in plan.steps[2].goal


def test_decompose_calculator_template():
    """Test Calculator template decomposition."""
    decomposer = TaskDecomposer()
    plan = decomposer.decompose("task_103", "Launch Calculator and discover keypad")

    assert len(plan.steps) == 2
    assert "Calculator" in plan.steps[0].goal
    assert plan.steps[1].dependencies == ["step_1"]


def test_decompose_rule_based_conjunctions():
    """Test rule-based decomposition splitting on conjunctions."""
    decomposer = TaskDecomposer()
    plan = decomposer.decompose(
        "task_104", "Open browser then check status and then report results"
    )

    assert len(plan.steps) == 3
    assert plan.steps[0].step_id == "step_1"
    assert plan.steps[1].dependencies == ["step_1"]
    assert plan.steps[2].dependencies == ["step_2"]


def test_plan_validator_consequential_risk_enforcement():
    """PlanValidator must reject consequential actions marked LOW or repeatability=True."""
    validator = PlanValidator()
    decomposer = TaskDecomposer(validator=validator)

    # Decompose a consequential action
    plan = decomposer.decompose("task_105", "Delete temporary cache files")
    step = plan.steps[0]
    assert step.risk_level in [RiskLevel.HIGH, RiskLevel.CONSEQUENTIAL]
    assert step.repeatability is False

    # Force invalid repeatability on consequential step
    step.repeatability = True
    is_valid, err = validator.validate_plan(plan)
    assert is_valid is False
    assert "cannot have repeatability=True" in err


def test_plan_validator_step_limit_enforced():
    """PlanValidator rejects plans exceeding max_steps limit."""
    validator = PlanValidator(max_steps=5)
    decomposer = TaskDecomposer(validator=validator)
    plan = decomposer.decompose(
        "task_106", "step 1 then step 2 then step 3 then step 4 then step 5 then step 6"
    )

    # Manually append to exceed 5 steps
    for i in range(len(plan.steps), 7):
        plan.steps.append(
            TaskStep(
                step_id=f"extra_{i}",
                goal="Extra",
                dependencies=[plan.steps[-1].step_id],
            )
        )

    is_valid, err = validator.validate_plan(plan)
    assert is_valid is False
    assert "exceeding maximum limit" in err
