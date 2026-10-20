"""
COMPASS Phase 6 — Multi-Step Execution Controller
Orchestrates closed-loop, dependency-grounded execution of multi-step plans.
Strictly dispatches ONE action at a time with live pre-dispatch target revalidation,
contextual risk boundaries, dual-layer verification, checkpointing, and universal STOP.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from automation import action_dispatcher
from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.models import TaskState
from backend.app.services.task_service import task_service
from perception import uia_inspector
from perception.context_analyzer import UIContextAnalyzer
from perception.models_multimodal import (
    EvidenceSource as MultiEvidenceSource,
)
from perception.models_multimodal import (
    ResolvedTarget,
)
from perception.multimodal_service import MultimodalPerceptionService
from planner.checkpoint_manager import CheckpointManager
from planner.dependency_manager import StepDependencyManager
from planner.dynamic_replanner import DynamicReplanner
from planner.execution_trace import ExecutionTraceManager
from planner.loop_detector import LoopDetector
from planner.models import (
    DecomposedPlan,
    PlannerActionType,
    RiskLevel,
    StepStatus,
    TaskStep,
    VerificationStatus,
)
from planner.multi_step_verifier import MultiStepVerifier
from planner.plan_validator import PlanValidator
from planner.task_decomposer import TaskDecomposer


class MultiStepExecutionController:
    """
    Coordinates end-to-end multi-step task execution adhering to the strict closed loop:
    UNDERSTAND -> DECOMPOSE -> VALIDATE -> PERCEIVE -> TARGET RESOLUTION ->
    SAFETY CHECK -> READY TO ACT -> ACT ONE ACTION -> VERIFY -> UPDATE STEP ->
    ADAPT/RECOVER/REPLAN -> NEXT STEP -> FINAL GOAL VERIFICATION -> TRUTHFUL COMPLETION.
    """

    def __init__(
        self,
        decomposer: TaskDecomposer | None = None,
        validator: PlanValidator | None = None,
        dependency_manager: StepDependencyManager | None = None,
        replanner: DynamicReplanner | None = None,
        verifier: MultiStepVerifier | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        loop_detector: LoopDetector | None = None,
        trace_manager: ExecutionTraceManager | None = None,
        perception_service: MultimodalPerceptionService | None = None,
    ):
        self.validator = validator or PlanValidator()
        self.decomposer = decomposer or TaskDecomposer(validator=self.validator)
        self.dep_manager = dependency_manager or StepDependencyManager()
        self.replanner = replanner or DynamicReplanner(
            validator=self.validator, decomposer=self.decomposer
        )
        self.verifier = verifier or MultiStepVerifier()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.loop_detector = loop_detector or LoopDetector()
        self.trace_manager = trace_manager or ExecutionTraceManager()
        self.context_analyzer = UIContextAnalyzer()
        self.perception_service = perception_service or MultimodalPerceptionService()

        self._locks: dict[str, threading.Lock] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._global_lock = threading.Lock()

    def _get_stop_event(self, task_id: str) -> threading.Event:
        with self._global_lock:
            if task_id not in self._stop_events:
                self._stop_events[task_id] = threading.Event()
            return self._stop_events[task_id]

    def stop_task(self, task_id: str, reason: str = "User requested STOP") -> bool:
        """Universal, thread-safe cancellation across all 14 lifecycle points."""
        logger.info(f"Universal STOP requested for task [{task_id}]: {reason}")
        stop_evt = self._get_stop_event(task_id)
        stop_evt.set()

        try:
            task_service.transition_state(task_id, TaskState.CANCELLED, reason=reason)
        except Exception:  # noqa: BLE001
            try:
                task_service.transition_state(task_id, TaskState.STOPPED, reason=reason)
            except Exception:  # noqa: BLE001, S110
                pass

        self.trace_manager.record_stop_event(task_id, reason)
        return True

    def is_stopped(self, task_id: str) -> bool:
        return self._get_stop_event(task_id).is_set()

    def run_multistep_task(
        self,
        task_id: str,
        goal: str,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        target_hwnd: int | None = None,
        max_duration_s: float = 180.0,
    ) -> dict[str, Any]:
        """
        Execute multi-step task with full safety, DAG management, step-by-step verification,
        checkpointing, and truthful completion.
        """
        start_time = time.time()
        stop_evt = self._get_stop_event(task_id)

        def emit(event_type: str, payload: dict[str, Any]):
            db.log_task_event(task_id=task_id, event_type=event_type, payload=payload)
            if on_event:
                try:
                    on_event(event_type, payload)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Error in on_event callback: {e}")

        # Initialize Execution Trace
        self.trace_manager.start_trace(task_id, goal)
        emit("task_started", {"task_id": task_id, "goal": goal})

        try:
            # 1. Checkpoint 1: Understanding
            if stop_evt.is_set():
                return self._handle_stop(task_id, emit, "STOP before understanding")

            task_service.transition_state(
                task_id,
                TaskState.UNDERSTANDING,
                reason="Parsing intent and constraints",
            )
            emit("state_changed", {"state": TaskState.UNDERSTANDING.value})

            # 2. Checkpoint 2: Decomposing
            if stop_evt.is_set():
                return self._handle_stop(task_id, emit, "STOP before decomposition")

            task_service.transition_state(
                task_id, TaskState.DECOMPOSING, reason="Building multi-step DAG plan"
            )
            emit("state_changed", {"state": TaskState.DECOMPOSING.value})

            plan: DecomposedPlan = self.decomposer.decompose(task_id, goal)
            emit(
                "plan_decomposed",
                {
                    "step_count": len(plan.steps),
                    "plan_hash": plan.plan_hash,
                    "steps": [
                        {
                            "step_id": s.step_id,
                            "goal": s.goal,
                            "dependencies": s.dependencies,
                        }
                        for s in plan.steps
                    ],
                },
            )

            # 3. Checkpoint 3: Plan Validation
            if stop_evt.is_set():
                return self._handle_stop(task_id, emit, "STOP before plan validation")

            task_service.transition_state(
                task_id,
                TaskState.VALIDATING,
                reason="Validating DAG and parameter safety",
            )
            emit("state_changed", {"state": TaskState.VALIDATING.value})

            is_valid, val_err = self.validator.validate_plan(plan)
            if not is_valid:
                reason = f"Plan validation failed: {val_err}"
                task_service.transition_state(task_id, TaskState.FAILED, reason=reason)
                self.trace_manager.finalize_trace(task_id, "FAILED", {"error": reason})
                return {"success": False, "status": "FAILED", "error": reason}

            # 4. Multi-Step Execution Loop
            completed_steps: list[TaskStep] = []
            max_steps_allowed = len(plan.steps) * 2  # Bounded execution loop
            iterations = 0

            while iterations < max_steps_allowed:
                iterations += 1

                # Check total task timeout
                if time.time() - start_time > max_duration_s:
                    timeout_reason = f"Task [{task_id}] exceeded maximum duration budget ({max_duration_s}s)."
                    task_service.transition_state(
                        task_id, TaskState.FAILED, reason=timeout_reason
                    )
                    self.trace_manager.finalize_trace(
                        task_id, "FAILED", {"error": timeout_reason}
                    )
                    return {
                        "success": False,
                        "status": "FAILED",
                        "error": timeout_reason,
                    }

                # Checkpoint 4: Start of step cycle STOP check
                if stop_evt.is_set():
                    return self._handle_stop(
                        task_id, emit, "STOP during execution loop"
                    )

                # Get ready steps
                ready_steps = self.dep_manager.get_ready_steps(plan.steps)
                if not ready_steps:
                    # Check if all completed
                    if all(s.status == StepStatus.COMPLETED for s in plan.steps):
                        break
                    # Otherwise, check if downstream steps were blocked
                    plan.steps = self.dep_manager.cascade_downstream_blocks(plan.steps)
                    blocked = [s for s in plan.steps if s.status == StepStatus.BLOCKED]
                    if blocked:
                        b_reason = f"Execution blocked: steps {[s.step_id for s in blocked]} cannot proceed due to upstream failures."
                        task_service.transition_state(
                            task_id, TaskState.BLOCKED, reason=b_reason
                        )
                        self.trace_manager.finalize_trace(
                            task_id, "BLOCKED", {"error": b_reason}
                        )
                        return {
                            "success": False,
                            "status": "BLOCKED",
                            "error": b_reason,
                        }
                    break

                # Pick first ready step in deterministic topological order
                curr_step = ready_steps[0]
                curr_step.status = StepStatus.IN_PROGRESS
                step_entry = self.trace_manager.record_step_start(  # noqa: F841
                    task_id, curr_step.step_id, curr_step.goal
                )

                emit(
                    "step_started",
                    {
                        "step_id": curr_step.step_id,
                        "goal": curr_step.goal,
                        "risk_level": curr_step.risk_level.value,
                    },
                )

                # Checkpoint 5: Perceiving
                if stop_evt.is_set():
                    return self._handle_stop(
                        task_id, emit, f"STOP before perceiving {curr_step.step_id}"
                    )

                task_service.transition_state(
                    task_id,
                    TaskState.PERCEIVING,
                    reason=f"Perceiving state for {curr_step.step_id}",
                )
                emit(
                    "state_changed",
                    {"state": TaskState.PERCEIVING.value, "step_id": curr_step.step_id},
                )
                emit(
                    "perception_started",
                    {"step_id": curr_step.step_id, "task_id": task_id},
                )

                # Capture fresh multimodal perception snapshot (UIA + Screen + OCR)
                obs_snapshot = self.perception_service.capture_multimodal_snapshot(
                    task_id=task_id, step_id=curr_step.step_id, include_ocr=True
                )
                emit(
                    "screenshot_captured",
                    {
                        "screenshot_path": obs_snapshot.screenshot_path,
                        "step_id": curr_step.step_id,
                    },
                )
                emit(
                    "uia_observed",
                    {
                        "count": len(
                            obs_snapshot.get_by_source(MultiEvidenceSource.UIA)
                        ),
                        "step_id": curr_step.step_id,
                    },
                )
                emit(
                    "ocr_completed",
                    {
                        "count": len(
                            obs_snapshot.get_by_source(MultiEvidenceSource.OCR)
                        ),
                        "step_id": curr_step.step_id,
                    },
                )
                emit(
                    "evidence_fused",
                    {
                        "evidence_count": len(obs_snapshot.evidence_items),
                        "step_id": curr_step.step_id,
                    },
                )

                resolved_target = None
                if curr_step.target_description:
                    resolved_target = self.perception_service.resolve_target(
                        snapshot=obs_snapshot, target_name=curr_step.target_description
                    )
                    if resolved_target:
                        emit(
                            "target_resolved",
                            {
                                "target_name": resolved_target.name,
                                "confidence": resolved_target.confidence,
                                "method": resolved_target.resolution_method.value,
                                "consistency": resolved_target.consistency.value,
                                "step_id": curr_step.step_id,
                            },
                        )
                        is_fresh, stale_reason = (
                            self.perception_service.fusion_engine.validate_target_staleness(
                                target=resolved_target,
                                current_window_hwnd=obs_snapshot.window_hwnd,
                                current_window_title=obs_snapshot.window_title,
                                current_snapshot=obs_snapshot,
                            )
                        )
                        if not is_fresh:
                            emit(
                                "observation_stale",
                                {"reason": stale_reason, "step_id": curr_step.step_id},
                            )
                            if "CONFLICT" in stale_reason:
                                emit(
                                    "target_conflict",
                                    {
                                        "reason": stale_reason,
                                        "step_id": curr_step.step_id,
                                    },
                                )

                fw = uia_inspector.get_foreground_window()
                win_info = fw.get("window") or {}
                if not win_info and obs_snapshot.window_title:
                    win_info = {
                        "hwnd": obs_snapshot.window_hwnd,
                        "title": obs_snapshot.window_title,
                    }
                hwnd = win_info.get("hwnd")
                uia_tree = None
                if hwnd:
                    try:
                        tree_res = uia_inspector.get_element_tree(hwnd=hwnd, depth=3)
                        if isinstance(tree_res, dict) and tree_res.get("success"):
                            uia_tree = tree_res.get("elements")
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"get_element_tree call failed: {e}")

                # Analyze UI context (detect modals, prompts)
                ctx_analysis = self.context_analyzer.analyze_context(
                    win_info, {"children": uia_tree} if uia_tree else None
                )
                if ctx_analysis.has_modal_dialog:
                    logger.info(
                        f"Context analyzer detected modal: '{ctx_analysis.active_dialog_title}'"
                    )

                # Checkpoint 6: Safety Check & Consequential Risk Guard
                if stop_evt.is_set():
                    return self._handle_stop(
                        task_id, emit, f"STOP before safety check {curr_step.step_id}"
                    )

                task_service.transition_state(
                    task_id,
                    TaskState.SAFETY_CHECK,
                    reason=f"Safety validation for {curr_step.step_id}",
                )
                emit(
                    "state_changed",
                    {
                        "state": TaskState.SAFETY_CHECK.value,
                        "step_id": curr_step.step_id,
                    },
                )

                # Consequential action safety check
                if curr_step.risk_level in [RiskLevel.CONSEQUENTIAL, RiskLevel.BLOCKED]:
                    # Consequential operations without explicit external authorization are blocked
                    block_msg = f"Consequential action blocked by safety contract: '{curr_step.goal}'. Human approval required."
                    curr_step.status = StepStatus.BLOCKED
                    curr_step.error = block_msg
                    task_service.transition_state(
                        task_id, TaskState.SAFETY_BLOCKED, reason=block_msg
                    )
                    emit(
                        "step_blocked",
                        {"step_id": curr_step.step_id, "reason": block_msg},
                    )
                    self.trace_manager.record_step_finish(
                        task_id, curr_step.step_id, "BLOCKED", "BLOCKED", block_msg
                    )
                    self.trace_manager.finalize_trace(
                        task_id, "SAFETY_BLOCKED", {"error": block_msg}
                    )
                    return {
                        "success": False,
                        "status": "SAFETY_BLOCKED",
                        "error": block_msg,
                    }

                # Checkpoint 7: Ready to Act
                if stop_evt.is_set():
                    return self._handle_stop(
                        task_id, emit, f"STOP before acting {curr_step.step_id}"
                    )

                task_service.transition_state(
                    task_id,
                    TaskState.READY_TO_ACT,
                    reason=f"Ready to dispatch {curr_step.step_id}",
                )
                emit(
                    "state_changed",
                    {
                        "state": TaskState.READY_TO_ACT.value,
                        "step_id": curr_step.step_id,
                    },
                )

                # Checkpoint 8: Acting (Dispatch strictly ONE action)
                task_service.transition_state(
                    task_id, TaskState.ACTING, reason=f"Executing {curr_step.step_id}"
                )
                emit(
                    "state_changed",
                    {"state": TaskState.ACTING.value, "step_id": curr_step.step_id},
                )

                action_res = self._dispatch_step_action(
                    curr_step, win_info, resolved_target=resolved_target
                )

                # Checkpoint 9: Verification
                if stop_evt.is_set():
                    return self._handle_stop(
                        task_id,
                        emit,
                        f"STOP before verification of {curr_step.step_id}",
                    )

                task_service.transition_state(
                    task_id,
                    TaskState.VERIFYING,
                    reason=f"Verifying {curr_step.step_id}",
                )
                emit(
                    "state_changed",
                    {"state": TaskState.VERIFYING.value, "step_id": curr_step.step_id},
                )

                # Post-action perception for multimodal delta verification
                emit("verification_started", {"step_id": curr_step.step_id})
                post_obs = self.perception_service.capture_multimodal_snapshot(
                    task_id=task_id, step_id=curr_step.step_id, include_ocr=True
                )
                t_comp = (
                    self.perception_service.temporal_comparator.compare_observations(
                        obs_snapshot,
                        post_obs,
                        expected_target_name=curr_step.target_description,
                    )
                )
                all_post_ocr = " ".join(
                    e.extracted_text
                    for e in post_obs.get_by_source(MultiEvidenceSource.OCR)
                )

                post_fw = uia_inspector.get_foreground_window()
                post_win = post_fw.get("window") or {
                    "hwnd": post_obs.window_hwnd,
                    "title": post_obs.window_title,
                }
                post_state = {
                    "window": post_win,
                    "edit_text": action_res.get("observed_text", ""),
                    "action_success": action_res.get("success", False),
                    "ocr_text": all_post_ocr,
                    "pixel_difference_ratio": t_comp.pixel_difference_ratio,
                    "temporal_transitions": [
                        t.value for t in t_comp.detected_transitions
                    ],
                    "observation": post_obs,
                }

                verif_res = self.verifier.verify_step(
                    step=curr_step,
                    pre_state={"window": win_info, "observation": obs_snapshot},
                    post_state=post_state,
                    action_type=curr_step.candidate_actions[0].action_type.value
                    if curr_step.candidate_actions
                    else "observe",
                )
                emit(
                    "verification_completed",
                    {
                        "step_id": curr_step.step_id,
                        "status": verif_res.status.value,
                        "details": verif_res.details,
                    },
                )

                # Check Loop Detector
                is_loop, loop_msg = self.loop_detector.record_action_attempt(
                    action_type=curr_step.candidate_actions[0].action_type.value
                    if curr_step.candidate_actions
                    else "observe",
                    target_id=curr_step.target_description,
                    success=(verif_res.status == VerificationStatus.VERIFIED),
                    verification_status=verif_res.status.value,
                )
                if is_loop:
                    task_service.transition_state(
                        task_id, TaskState.FAILED, reason=loop_msg
                    )
                    self.trace_manager.finalize_trace(
                        task_id, "FAILED", {"error": loop_msg}
                    )
                    return {"success": False, "status": "FAILED", "error": loop_msg}

                # Evaluate Verification Result
                if verif_res.status == VerificationStatus.VERIFIED:
                    curr_step.status = StepStatus.COMPLETED
                    completed_steps.append(curr_step)

                    # Checkpoint 10: Step Completed
                    task_service.transition_state(
                        task_id,
                        TaskState.STEP_COMPLETED,
                        reason=f"Step {curr_step.step_id} verified",
                    )
                    emit(
                        "step_completed",
                        {"step_id": curr_step.step_id, "details": verif_res.details},
                    )

                    # Save Checkpoint
                    self.checkpoint_manager.save_checkpoint(
                        task_id=task_id,
                        step_id=curr_step.step_id,
                        completed_step_ids=[s.step_id for s in completed_steps],
                        verified_state={
                            "step_id": curr_step.step_id,
                            "status": "VERIFIED",
                        },
                        current_app=win_info.get("title"),
                        expected_window_title=win_info.get("title"),
                    )

                    self.trace_manager.record_step_finish(
                        task_id,
                        curr_step.step_id,
                        "COMPLETED",
                        "VERIFIED",
                        verif_res.details,
                    )

                    # Checkpoint 10b: STOP immediately after step completion
                    if stop_evt.is_set():
                        return self._handle_stop(
                            task_id,
                            emit,
                            f"STOP immediately after completion of {curr_step.step_id}",
                        )

                else:
                    # Step failed or unverified
                    logger.warning(
                        f"Step [{curr_step.step_id}] verification failed: {verif_res.details}"
                    )
                    curr_step.status = StepStatus.FAILED
                    curr_step.error = verif_res.details

                    # Check if non-repeatable -> halt immediately
                    if not curr_step.repeatability:
                        fail_msg = f"Non-repeatable step [{curr_step.step_id}] failed verification. Auto-retry prohibited."
                        task_service.transition_state(
                            task_id, TaskState.BLOCKED, reason=fail_msg
                        )
                        self.trace_manager.record_step_finish(
                            task_id,
                            curr_step.step_id,
                            "FAILED",
                            verif_res.status.value,
                            fail_msg,
                        )
                        self.trace_manager.finalize_trace(
                            task_id, "BLOCKED", {"error": fail_msg}
                        )
                        return {
                            "success": False,
                            "status": "BLOCKED",
                            "error": fail_msg,
                        }

                    # Trigger Dynamic Replanning
                    task_service.transition_state(
                        task_id,
                        TaskState.ADAPTING,
                        reason=f"Triggering dynamic replanning for {curr_step.step_id}",
                    )
                    replan_ok, new_plan, replan_err = (
                        self.replanner.handle_replan_trigger(
                            current_plan=plan,
                            failed_step_id=curr_step.step_id,
                            reason=verif_res.details,
                            live_window_info=post_win,
                            live_uia_tree=uia_tree,
                        )
                    )

                    if replan_ok and new_plan:
                        plan = new_plan
                        logger.info(
                            f"Dynamic replan succeeded. Continuing with updated {len(plan.steps)} steps."
                        )
                    else:
                        halt_msg = f"Recovery/replanning exhausted: {replan_err or verif_res.details}"
                        task_service.transition_state(
                            task_id, TaskState.FAILED, reason=halt_msg
                        )
                        self.trace_manager.record_step_finish(
                            task_id,
                            curr_step.step_id,
                            "FAILED",
                            verif_res.status.value,
                            halt_msg,
                        )
                        self.trace_manager.finalize_trace(
                            task_id, "FAILED", {"error": halt_msg}
                        )
                        return {"success": False, "status": "FAILED", "error": halt_msg}

            # 5. Checkpoint 11: Final Goal Verification
            if stop_evt.is_set():
                return self._handle_stop(
                    task_id, emit, "STOP before final goal verification"
                )

            task_service.transition_state(
                task_id,
                TaskState.VERIFYING,
                reason="Performing final holistic goal verification",
            )
            final_verif = self.verifier.verify_final_goal(plan, post_win)

            if final_verif.status == VerificationStatus.VERIFIED:
                task_service.transition_state(
                    task_id,
                    TaskState.TASK_COMPLETED,
                    reason="All steps and holistic goal confirmed verified",
                )
                emit("task_completed", {"details": final_verif.details})
                self.trace_manager.finalize_trace(
                    task_id, "TASK_COMPLETED", final_verif.to_dict()
                )
                return {
                    "success": True,
                    "status": "TASK_COMPLETED",
                    "details": final_verif.details,
                }
            else:
                task_service.transition_state(
                    task_id, TaskState.UNVERIFIED, reason=final_verif.details
                )
                emit("task_unverified", {"details": final_verif.details})
                self.trace_manager.finalize_trace(
                    task_id, "UNVERIFIED", final_verif.to_dict()
                )
                return {
                    "success": False,
                    "status": "UNVERIFIED",
                    "details": final_verif.details,
                }

        except Exception as e:  # noqa: BLE001
            err_str = f"Execution engine unhandled error: {e!s}"
            logger.error(err_str, exc_info=True)
            try:
                task_service.transition_state(task_id, TaskState.FAILED, reason=err_str)
            except Exception:  # noqa: BLE001, S110
                pass
            self.trace_manager.finalize_trace(task_id, "FAILED", {"error": err_str})
            return {"success": False, "status": "FAILED", "error": err_str}

    def _dispatch_step_action(
        self,
        step: TaskStep,
        win_info: dict[str, Any],
        resolved_target: ResolvedTarget | None = None,
    ) -> dict[str, Any]:
        """Dispatch the primary planned action for a step."""
        if not step.candidate_actions:
            # Benign observation / passive step
            return {"success": True, "details": "Passive step observed"}

        action = step.candidate_actions[0]
        atype = action.action_type
        params = action.parameters

        if atype == PlannerActionType.OBSERVE:
            app_exe = params.get("app")
            if app_exe:
                # Launch target app if not active
                import subprocess

                try:
                    subprocess.Popen([app_exe], shell=False)
                    time.sleep(1.5)
                    # Try to bring window to foreground if launched
                    import ctypes

                    u32 = ctypes.windll.user32
                    found_hwnd = None

                    def _enum_wnd(h, l):
                        nonlocal found_hwnd
                        if u32.IsWindowVisible(h):
                            length = u32.GetWindowTextLengthW(h)
                            if length > 0:
                                buf = ctypes.create_unicode_buffer(length + 1)
                                u32.GetWindowTextW(h, buf, length + 1)
                                if any(
                                    k in buf.value.lower()
                                    for k in ["notepad", "calculator", "explorer"]
                                ):
                                    found_hwnd = h
                                    return False
                        return True

                    WNDENUMPROC = ctypes.WINFUNCTYPE(
                        ctypes.c_bool, ctypes.c_int, ctypes.c_int
                    )
                    u32.EnumWindows(WNDENUMPROC(_enum_wnd), 0)
                    if found_hwnd:
                        u32.SetForegroundWindow(found_hwnd)
                        time.sleep(0.3)
                except Exception as e:  # noqa: BLE001
                    return {"success": False, "error": str(e)}
            return {"success": True, "details": f"Observed/launched {app_exe}"}

        elif atype == PlannerActionType.CLICK:
            if resolved_target and resolved_target.bounding_box.is_valid:
                target_dict = {
                    "hwnd": resolved_target.hwnd or win_info.get("hwnd", 0),
                    "name": resolved_target.name,
                    "control_type": "Button",
                    "bounds": resolved_target.bounding_box.to_dict(),
                    "runtime_id": "",
                }
                try:
                    res = action_dispatcher.click_element(target_dict)
                    succ = (
                        getattr(res, "success", True)
                        if hasattr(res, "success")
                        else (
                            res.get("success", True) if isinstance(res, dict) else True
                        )
                    )
                    return {
                        "success": succ,
                        "clicked_target": resolved_target.name,
                        "center": resolved_target.center_point,
                    }
                except Exception as e:  # noqa: BLE001
                    return {"success": False, "error": str(e)}
            else:
                snapshot = {
                    "hwnd": win_info.get("hwnd", 0),
                    "name": step.target_description or "Button",
                    "control_type": "Button",
                    "bounds": {},
                    "runtime_id": "",
                }
                try:
                    res = action_dispatcher.click_element(snapshot)
                    succ = (
                        getattr(res, "success", True)
                        if hasattr(res, "success")
                        else (
                            res.get("success", True) if isinstance(res, dict) else True
                        )
                    )
                    return {"success": succ}
                except Exception as e:  # noqa: BLE001
                    return {"success": False, "error": str(e)}

        elif atype == PlannerActionType.TYPE:
            text = params.get("text", "")
            snapshot = {
                "hwnd": win_info.get("hwnd", 0),
                "name": step.target_description or "Edit",
                "control_type": "Edit",
                "runtime_id": "",
            }
            try:
                res = action_dispatcher.type_text(snapshot, text)
                succ = (
                    getattr(res, "success", True)
                    if hasattr(res, "success")
                    else (res.get("success", True) if isinstance(res, dict) else True)
                )
                return {"success": succ, "observed_text": text}
            except Exception as e:  # noqa: BLE001
                return {"success": False, "error": str(e)}

        elif atype in [PlannerActionType.KEY, PlannerActionType.KEY_COMBINATION]:
            comb = params.get("combination") or params.get("key", "")
            try:
                if "+" in comb:
                    res = action_dispatcher.send_key_combination(comb)
                else:
                    res = action_dispatcher.send_key(comb)
                succ = (
                    getattr(res, "success", True)
                    if hasattr(res, "success")
                    else (res.get("success", True) if isinstance(res, dict) else True)
                )
                return {"success": succ}
            except Exception as e:  # noqa: BLE001
                return {"success": False, "error": str(e)}

        return {"success": True, "details": "Default dispatch"}

    def _handle_stop(
        self, task_id: str, emit_fn: Callable, reason: str
    ) -> dict[str, Any]:
        """Handle universal STOP assertion cleanly."""
        logger.info(f"Task [{task_id}] halted by STOP checkpoint: {reason}")
        t = task_service.get_task(task_id)
        curr_st = getattr(t, "state", None) if t else None
        if curr_st not in [TaskState.CANCELLED, TaskState.STOPPED]:
            try:
                task_service.transition_state(
                    task_id, TaskState.CANCELLED, reason=reason
                )
            except Exception:  # noqa: BLE001
                try:
                    task_service.transition_state(
                        task_id, TaskState.STOPPED, reason=reason
                    )
                except Exception:  # noqa: BLE001, S110
                    pass

        emit_fn("task_stopped", {"reason": reason})
        self.trace_manager.record_stop_event(task_id, reason)
        self.trace_manager.finalize_trace(task_id, "CANCELLED", {"reason": reason})
        return {"success": False, "status": "CANCELLED", "reason": reason}
