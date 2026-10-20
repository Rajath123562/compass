"""
COMPASS Phase 6 — Task Decomposer
Decomposes natural language goals into structured, ordered TaskStep nodes
with explicit dependencies, verification strategies, and risk classifications.
Combines deterministic capability templates with AI-assisted decomposition.
"""

from __future__ import annotations

import hashlib
import re

from backend.app.logging_config import logger
from planner.goal_understanding import GoalUnderstandingEngine, GoalUnderstandingResult
from planner.models import (
    DecomposedPlan,
    PlannedAction,
    PlannerActionType,
    RiskLevel,
    TargetReference,
    TaskStep,
)
from planner.plan_validator import PlanValidator


class TaskDecomposer:
    """
    Decomposes natural language objectives into structured DecomposedPlan DAGs.
    Prefers deterministic capability templates for known application workflows,
    falling back to rule-based or AI decomposition when required.
    """

    def __init__(self, validator: PlanValidator | None = None):
        self.validator = validator or PlanValidator()
        self.goal_engine = GoalUnderstandingEngine()

    def decompose(self, task_id: str, goal: str) -> DecomposedPlan:
        """
        Decompose a goal into a validated DecomposedPlan.
        """
        raw_goal = (goal or "").strip()
        goal_understanding = self.goal_engine.understand_goal(raw_goal)

        # Check for deterministic template matches first
        plan = self._try_deterministic_template(task_id, raw_goal, goal_understanding)
        if not plan:
            # Fall back to rule-based multi-step parsing
            plan = self._decompose_rule_based(task_id, raw_goal, goal_understanding)

        # Validate the resulting plan
        is_valid, err = self.validator.validate_plan(plan)
        if not is_valid:
            logger.warning(
                f"Decomposed plan validation warning for task [{task_id}]: {err}"
            )
            # If invalid, simplify to a safe single-step fallback plan
            plan = self._build_safe_fallback_plan(task_id, raw_goal, goal_understanding)

        return plan

    def _try_deterministic_template(
        self, task_id: str, goal: str, gu: GoalUnderstandingResult
    ) -> DecomposedPlan | None:
        """Check if goal matches a standard, high-reliability application template."""
        app = (gu.target_application or "").lower()
        lower_goal = goal.lower()

        # 1. Notepad Multi-Step Workflows
        if "notepad" in app or "notepad" in lower_goal:
            # Extract text to type if specified: e.g. "write hello world", "type 'abc'"
            text_match = re.search(
                r"(?:type|write|enter)\s+['\"]?([^'\"]+?)['\"]?(?:\s+(?:and|then|in)|\s*$)",
                goal,
                re.IGNORECASE,
            )
            has_text_intent = bool(
                text_match
                or any(re.search(rf"\b{re.escape(k)}\b", lower_goal) for k in ["type", "write", "enter", "notes", "text", "message"])
            )
            text_to_type = (
                text_match.group(1).strip()
                if text_match
                else ("COMPASS Phase 6 Verified" if has_text_intent else "")
            )

            steps: list[TaskStep] = [
                TaskStep(
                    step_id="step_1",
                    goal="Launch Notepad Application",
                    preconditions=["Desktop available"],
                    target_description="Notepad executable",
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.LAUNCH_APP,
                            target_description="Notepad Window",
                            expected_result="Notepad window opened and active",
                            parameters={"app": "notepad.exe", "path": "notepad.exe"},
                        )
                    ],
                    risk_level=RiskLevel.LOW,
                    repeatability=True,
                    expected_state_change="Notepad window active on desktop",
                    verification_strategy="WINDOW_STATE",
                    recovery_strategy="REPERCEIVE_DRIFT",
                    completion_condition={"window_title_contains": "Notepad"},
                    dependencies=[],
                )
            ]

            if has_text_intent and text_to_type:
                steps.append(
                    TaskStep(
                        step_id="step_2",
                        goal=f"Enter text into Notepad: '{text_to_type}'",
                        preconditions=["Notepad window active"],
                        target_description="Notepad text editor document area",
                        target=TargetReference(control_type="Edit", name="Text editor"),
                        candidate_actions=[
                            PlannedAction(
                                action_type=PlannerActionType.TYPE,
                                target_description="Text editor",
                                expected_result=f"Text '{text_to_type}' entered into editor",
                                parameters={"text": text_to_type},
                            )
                        ],
                        risk_level=RiskLevel.MEDIUM,
                        repeatability=True,
                        expected_state_change=f"Editor contains '{text_to_type}'",
                        verification_strategy="UIA_PATTERN",
                        recovery_strategy="RETRY_ONCE",
                        completion_condition={"text_contains": text_to_type},
                        dependencies=["step_1"],
                    )
                )

            # If user also asked to save
            if any(k in lower_goal for k in ["save", "save as", "file"]):
                dep_step = "step_2" if (has_text_intent and text_to_type) else "step_1"
                steps.append(
                    TaskStep(
                        step_id="step_3",
                        goal="Save Document",
                        preconditions=["Text entered into editor"],
                        target_description="Save command shortcut",
                        candidate_actions=[
                            PlannedAction(
                                action_type=PlannerActionType.KEY_COMBINATION,
                                target_description="Save shortcut",
                                expected_result="Document save initiated",
                                parameters={"combination": "ctrl+s"},
                            )
                        ],
                        risk_level=RiskLevel.MEDIUM,
                        repeatability=True,
                        expected_state_change="Save dialog or file saved state",
                        verification_strategy="WINDOW_STATE",
                        recovery_strategy="REPLAN",
                        completion_condition={"save_completed": True},
                        dependencies=[dep_step],
                    )
                )

            deps = {s.step_id: s.dependencies for s in steps}
            return DecomposedPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                dependencies=deps,
                plan_hash=self._hash_plan(steps),
            )

        # 2. ChatGPT Workflow
        if "chatgpt" in lower_goal:
            steps = [
                TaskStep(
                    step_id="step_1",
                    goal="Launch Browser to ChatGPT",
                    preconditions=["Desktop available"],
                    target_description="Default web browser",
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.OPEN_URL,
                            target_description="Launch Edge to ChatGPT",
                            expected_result="Browser launching",
                            parameters={"url": "https://chatgpt.com/"},
                        )
                    ],
                    risk_level=RiskLevel.LOW,
                    repeatability=True,
                    expected_state_change="ChatGPT loaded in browser",
                    verification_strategy="NONE",
                    recovery_strategy="NONE",
                    completion_condition={"always_true": True},
                    dependencies=[],
                )
            ]

            if "guide" in lower_goal or "tour" in lower_goal:
                steps.extend(
                    [
                        TaskStep(
                            step_id="step_2",
                            goal="Instructions: Wait for ChatGPT to finish loading",
                            preconditions=["Browser launching"],
                            target_description="Wait 5 seconds",
                            candidate_actions=[
                                PlannedAction(
                                    action_type=PlannerActionType.WAIT,
                                    target_description="Loading page",
                                    expected_result="Page loaded",
                                    parameters={"duration_ms": 5000},
                                )
                            ],
                            risk_level=RiskLevel.LOW,
                            repeatability=True,
                            expected_state_change="Page is ready",
                            verification_strategy="NONE",
                            recovery_strategy="NONE",
                            completion_condition={"always_true": True},
                            dependencies=["step_1"],
                        ),
                        TaskStep(
                            step_id="step_3",
                            goal="Instructions: This is the chat input box. Type your question here.",
                            preconditions=["Page loaded"],
                            target_description="Bottom center area",
                            candidate_actions=[
                                PlannedAction(
                                    action_type=PlannerActionType.MOVE,
                                    target_description="Chat Input Area",
                                    expected_result="Cursor moved to input",
                                    parameters={"x": 800, "y": 800},
                                ),
                                PlannedAction(
                                    action_type=PlannerActionType.WAIT,
                                    target_description="Read instruction",
                                    expected_result="Waited",
                                    parameters={"duration_ms": 4000},
                                ),
                            ],
                            risk_level=RiskLevel.LOW,
                            repeatability=True,
                            expected_state_change="Guided user to input",
                            verification_strategy="NONE",
                            recovery_strategy="NONE",
                            completion_condition={"always_true": True},
                            dependencies=["step_2"],
                        ),
                        TaskStep(
                            step_id="step_4",
                            goal="Instructions: Here is the sidebar where your previous chats are saved.",
                            preconditions=["Input guided"],
                            target_description="Left sidebar area",
                            candidate_actions=[
                                PlannedAction(
                                    action_type=PlannerActionType.MOVE,
                                    target_description="Sidebar Area",
                                    expected_result="Cursor moved to sidebar",
                                    parameters={"x": 150, "y": 400},
                                ),
                                PlannedAction(
                                    action_type=PlannerActionType.WAIT,
                                    target_description="Read instruction",
                                    expected_result="Waited",
                                    parameters={"duration_ms": 4000},
                                ),
                            ],
                            risk_level=RiskLevel.LOW,
                            repeatability=True,
                            expected_state_change="Guided user to sidebar",
                            verification_strategy="NONE",
                            recovery_strategy="NONE",
                            completion_condition={"always_true": True},
                            dependencies=["step_3"],
                        ),
                    ]
                )

            deps = {s.step_id: s.dependencies for s in steps}
            return DecomposedPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                dependencies=deps,
                plan_hash=self._hash_plan(steps),
            )

        # 3. Calculator Workflows
        if "calc" in app or "calculator" in lower_goal:
            has_calc_action = any(
                k in lower_goal
                for k in ["keypad", "button", "calculate", "math", "add", "multiply", "discover", "key"]
            )
            steps = [
                TaskStep(
                    step_id="step_1",
                    goal="Launch Calculator Application",
                    preconditions=["Desktop available"],
                    target_description="Calculator executable",
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.LAUNCH_APP,
                            target_description="Calculator Window",
                            expected_result="Calculator window opened",
                            parameters={"app": "calc.exe", "uri": "calculator:"},
                        )
                    ],
                    risk_level=RiskLevel.LOW,
                    repeatability=True,
                    expected_state_change="Calculator window active",
                    verification_strategy="WINDOW_STATE",
                    recovery_strategy="REPERCEIVE_DRIFT",
                    completion_condition={"window_title_contains": "Calculator"},
                    dependencies=[],
                )
            ]
            if has_calc_action:
                steps.append(
                    TaskStep(
                        step_id="step_2",
                        goal="Discover and Verify Calculator Controls",
                        preconditions=["Calculator window active"],
                        target_description="Calculator Keypad",
                        candidate_actions=[
                            PlannedAction(
                                action_type=PlannerActionType.OBSERVE,
                                target_description="Keypad buttons",
                                expected_result="Keypad controls discovered",
                                parameters={},
                            )
                        ],
                        risk_level=RiskLevel.LOW,
                        repeatability=True,
                        expected_state_change="Controls verified in UIA tree",
                        verification_strategy="UIA_PATTERN",
                        recovery_strategy="REPERCEIVE_DRIFT",
                        completion_condition={"elements_found": True},
                        dependencies=["step_1"],
                    )
                )
            deps = {s.step_id: s.dependencies for s in steps}
            return DecomposedPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                dependencies=deps,
                plan_hash=self._hash_plan(steps),
            )

        # 3. File Explorer Workflows
        if "explorer" in app or "folder" in lower_goal or "directory" in lower_goal:
            is_consequential = (
                gu.safety_level in [RiskLevel.HIGH, RiskLevel.CONSEQUENTIAL]
                or any(k in lower_goal for k in ["delete", "purge", "remove", "erase", "format", "wipe", "destroy"])
            )
            step_risk = RiskLevel.CONSEQUENTIAL if is_consequential else RiskLevel.LOW
            repeatable = not is_consequential
            steps = [
                TaskStep(
                    step_id="step_1",
                    goal="Open File Explorer" if not is_consequential else f"Execute consequential action: {goal}",
                    preconditions=["Desktop available"],
                    target_description="File Explorer Window",
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.LAUNCH_APP,
                            target_description="Explorer Window",
                            expected_result="Explorer window active",
                            parameters={"app": "explorer.exe"},
                        )
                    ],
                    risk_level=step_risk,
                    repeatability=repeatable,
                    expected_state_change="File Explorer window displayed",
                    verification_strategy="WINDOW_STATE",
                    recovery_strategy="REPERCEIVE_DRIFT",
                    completion_condition={"window_title_contains": "Explorer"},
                    dependencies=[],
                )
            ]
            deps = {s.step_id: s.dependencies for s in steps}
            return DecomposedPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                dependencies=deps,
                plan_hash=self._hash_plan(steps),
            )

        # 4. Paint Workflows
        if "paint" in app or "paint" in lower_goal or "canvas" in lower_goal:
            steps = [
                TaskStep(
                    step_id="step_1",
                    goal="Launch or Focus Paint Application",
                    preconditions=["Desktop available"],
                    target_description="Paint Window",
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.LAUNCH_APP,
                            target_description="Paint Window",
                            expected_result="Paint window opened and active",
                            parameters={"app": "mspaint.exe"},
                        )
                    ],
                    risk_level=RiskLevel.LOW,
                    repeatability=True,
                    expected_state_change="Paint window active on desktop",
                    verification_strategy="WINDOW_STATE",
                    recovery_strategy="REPERCEIVE_DRIFT",
                    completion_condition={"window_title_contains": "Paint"},
                    dependencies=[],
                ),
                TaskStep(
                    step_id="step_2",
                    goal="Interact with Paint Window",
                    preconditions=["Paint window active"],
                    target_description="Paint Window",
                    target=TargetReference(control_type="Window", name="Paint"),
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.CLICK,
                            target_description="Paint Window",
                            expected_result="Untitled - Paint",
                            parameters={},
                        )
                    ],
                    risk_level=RiskLevel.LOW,
                    repeatability=True,
                    expected_state_change="Paint focused",
                    verification_strategy="WINDOW_STATE",
                    recovery_strategy="RETRY_ONCE",
                    completion_condition={"element_clicked": True},
                    dependencies=["step_1"],
                ),
            ]
            deps = {s.step_id: s.dependencies for s in steps}
            return DecomposedPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                dependencies=deps,
                plan_hash=self._hash_plan(steps),
            )

        # 5. URL Navigation Workflows
        url_match = re.search(
            r"(?:open|go to|browse|navigate to)\s+(https?://[^\s]+|[a-zA-Z0-9.\-]+\.(?:com|org|net|io|edu|gov|dev|app)[^\s]*)",
            lower_goal,
            re.IGNORECASE,
        )
        if url_match:
            raw_url = url_match.group(1).strip()
            target_url = raw_url if raw_url.startswith("http") else f"https://{raw_url}"
            browser_name = "chrome" if "chrome" in lower_goal else ("edge" if "edge" in lower_goal else None)
            steps = [
                TaskStep(
                    step_id="step_1",
                    goal=f"Open URL: {target_url}",
                    preconditions=["Desktop available"],
                    target_description="Web Browser",
                    candidate_actions=[
                        PlannedAction(
                            action_type=PlannerActionType.OPEN_URL,
                            target_description=f"Open {target_url}",
                            expected_result=f"Browser opened to {target_url}",
                            parameters={"url": target_url, "browser": browser_name},
                        )
                    ],
                    risk_level=RiskLevel.LOW,
                    repeatability=True,
                    expected_state_change="Browser window open with URL",
                    verification_strategy="NONE",
                    recovery_strategy="NONE",
                    completion_condition={"always_true": True},
                    dependencies=[],
                )
            ]
            deps = {s.step_id: s.dependencies for s in steps}
            return DecomposedPlan(
                task_id=task_id,
                goal=goal,
                steps=steps,
                dependencies=deps,
                plan_hash=self._hash_plan(steps),
            )

        # 6. Generic App Launch Workflows (e.g. "open spotify", "launch figma", "start calculator")
        app_launch_match = re.match(
            r"^(?:open|launch|start|run)\s+([a-zA-Z0-9_\-\. ]+)$",
            goal.strip(),
            re.IGNORECASE,
        )
        if app_launch_match or (
            gu.target_application and lower_goal.startswith(("open ", "launch ", "start ", "run "))
        ):
            target_app_name = (
                app_launch_match.group(1).strip()
                if app_launch_match
                else (gu.target_application or "")
            )
            from automation.app_discovery import get_app_discovery

            app_info = get_app_discovery().discover_app(target_app_name)
            if app_info:
                steps = [
                    TaskStep(
                        step_id="step_1",
                        goal=f"Launch {app_info.display_name}",
                        preconditions=["Desktop available"],
                        target_description=f"{app_info.display_name} application",
                        candidate_actions=[
                            PlannedAction(
                                action_type=PlannerActionType.LAUNCH_APP,
                                target_description=app_info.display_name,
                                expected_result=f"{app_info.display_name} launched",
                                parameters={
                                    "app": target_app_name,
                                    "path": app_info.path,
                                    "uri": app_info.uri,
                                },
                            )
                        ],
                        risk_level=RiskLevel.LOW,
                        repeatability=True,
                        expected_state_change=f"{app_info.display_name} window open",
                        verification_strategy="NONE",
                        recovery_strategy="NONE",
                        completion_condition={"always_true": True},
                        dependencies=[],
                    )
                ]
                deps = {s.step_id: s.dependencies for s in steps}
                return DecomposedPlan(
                    task_id=task_id,
                    goal=goal,
                    steps=steps,
                    dependencies=deps,
                    plan_hash=self._hash_plan(steps),
                )

        return None

    def _decompose_rule_based(
        self, task_id: str, goal: str, gu: GoalUnderstandingResult
    ) -> DecomposedPlan:
        """
        Decompose arbitrary multi-step sentence by splitting conjunctions and sequencing steps.
        """
        # Split on common sequencing delimiters: 'and then', 'then', 'after that', ','
        delimiters = r"\b(?:and\s+then|then|after\s+that)\b|(?<=[a-z0-9]),(?=\s+[a-z])"
        sub_goals = [
            g.strip()
            for g in re.split(delimiters, goal, flags=re.IGNORECASE)
            if g.strip()
        ]

        if not sub_goals:
            sub_goals = [goal]

        steps: list[TaskStep] = []
        prev_id: str | None = None

        for idx, sg in enumerate(sub_goals):
            step_id = f"step_{idx + 1}"
            deps = [prev_id] if prev_id else []

            # Assess risk
            risk = RiskLevel.LOW
            is_consequential = any(
                kw in sg.lower() for kw in PlanValidator.CONSEQUENTIAL_KEYWORDS
            )
            if is_consequential:
                risk = RiskLevel.CONSEQUENTIAL

            act_type = (
                PlannerActionType.CLICK
                if "click" in sg.lower()
                else (
                    PlannerActionType.TYPE
                    if any(k in sg.lower() for k in ["type", "write", "enter"])
                    else PlannerActionType.OBSERVE
                )
            )
            steps.append(
                TaskStep(
                    step_id=step_id,
                    goal=sg,
                    preconditions=[f"Completed {prev_id}"] if prev_id else [],
                    target_description=f"Target for {sg}",
                    candidate_actions=[
                        PlannedAction(
                            action_type=act_type,
                            target_description=sg,
                            expected_result=f"Action for '{sg}' executed",
                            parameters={},
                        )
                    ],
                    risk_level=risk,
                    repeatability=not is_consequential,
                    expected_state_change=f"Executed {sg}",
                    verification_strategy="UIA_PATTERN",
                    recovery_strategy="REPLAN" if is_consequential else "RETRY_ONCE",
                    completion_condition={"goal_part": sg},
                    dependencies=deps,
                )
            )
            prev_id = step_id

        deps_map = {s.step_id: s.dependencies for s in steps}
        return DecomposedPlan(
            task_id=task_id,
            goal=goal,
            steps=steps,
            dependencies=deps_map,
            plan_hash=self._hash_plan(steps),
        )

    def _build_safe_fallback_plan(
        self, task_id: str, goal: str, gu: GoalUnderstandingResult
    ) -> DecomposedPlan:
        """Fallback single-step safe plan when decomposition fails or produces invalid DAG."""
        step = TaskStep(
            step_id="step_1",
            goal=goal,
            preconditions=[],
            target_description="Primary goal target",
            candidate_actions=[],
            risk_level=gu.safety_level,
            repeatability=True,
            expected_state_change="Goal achieved",
            verification_strategy="UIA_PATTERN",
            recovery_strategy="REPERCEIVE_DRIFT",
            completion_condition={"goal": goal},
            dependencies=[],
        )
        return DecomposedPlan(
            task_id=task_id,
            goal=goal,
            steps=[step],
            dependencies={"step_1": []},
            plan_hash=self._hash_plan([step]),
        )

    def _hash_plan(self, steps: list[TaskStep]) -> str:
        """Deterministic hash of plan step IDs and goals."""
        blob = "|".join(f"{s.step_id}:{s.goal}" for s in steps)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
