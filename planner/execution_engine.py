"""
COMPASS Phase 4 Closed-Loop Execution Engine
Orchestrates Goal Understanding, Real Perception, Structured Decision Engine,
Evidence-Based Confidence, Contextual Risk, Anti-Bypass Human Approval,
Pre-Dispatch Stale Observation Guard, Extended Actions, Post-Action Verification,
Adaptive Recovery preserving completed steps, and Thread-Safe STOP.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from automation import action_dispatcher
from automation.action_validator import ActionValidator
from automation.safety import check_coordinates_safe, get_safety_manager
from backend.app.database import db
from backend.app.logging_config import logger
from backend.app.models import TERMINAL_STATES, TaskState
from backend.app.services.task_service import task_service
from perception import uia_inspector
from planner.circuit_breaker import ai_circuit_breaker
from planner.decision_engine import decision_engine
from planner.goal_understanding import (
    GoalUnderstandingResult,
    goal_understanding_engine,
)
from planner.human_approval import ApprovalState, human_approval_controller
from planner.models import (
    Decision,
    PlannedAction,
    PlannerActionType,
    RecoveryCause,
    RiskLevel,
    TaskPlan,
    TimelineEntry,
    VerificationResult,
    VerificationStatus,
)
from planner.planner_service import PlannerService, planner_service
from planner.recovery_engine import recovery_engine
from planner.resource_governor import resource_governor
from planner.stale_guard import stale_guard
from planner.target_resolver import TargetResolutionResult, TargetResolver
from planner.verification_engine import VerificationEngine, verification_engine

TIMEOUT_GOAL_UNDERSTANDING_S = 10.0
TIMEOUT_AI_REQUEST_S = float(os.environ.get("COMPASS_LLM_TIMEOUT", "120.0"))
TIMEOUT_OBSERVATION_S = 5.0
TIMEOUT_DECISION_S = 5.0
TIMEOUT_VERIFICATION_S = 10.0
TIMEOUT_RECOVERY_S = 15.0


class ExecutionEngine:
    """
    Closed-loop runner executing one action at a time with strict safety and verification gates.
    """

    def __init__(
        self,
        planner: PlannerService | None = None,
        resolver: TargetResolver | None = None,
        verifier: VerificationEngine | None = None,
        max_retries_per_step: int = 3,
    ):
        self.planner = planner or planner_service
        self.resolver = resolver or TargetResolver()
        self.verifier = verifier or verification_engine
        self.max_retries_per_step = max_retries_per_step

        self._validator = ActionValidator(check_foreground=True)
        self._safety = get_safety_manager()

        # Task-scoped concurrency locks and cancellation flags
        self._locks: dict[str, threading.Lock] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._active_plans: dict[str, TaskPlan] = {}
        self._timelines: dict[str, list[TimelineEntry]] = {}
        self._global_lock = threading.Lock()

    def _get_task_lock(self, task_id: str) -> threading.Lock:
        with self._global_lock:
            if task_id not in self._locks:
                self._locks[task_id] = threading.Lock()
            return self._locks[task_id]

    def _get_stop_event(self, task_id: str) -> threading.Event:
        with self._global_lock:
            if task_id not in self._stop_events:
                self._stop_events[task_id] = threading.Event()
            return self._stop_events[task_id]

    def stop_task(self, task_id: str, reason: str = "User requested stop") -> bool:
        """
        Thread-safe signal to immediately halt task execution.
        Sets cancellation event and updates task state to STOPPED.
        Idempotent: safe to call repeatedly from any phase.
        """
        logger.info(
            f"ExecutionEngine received STOP request for task [{task_id}]: {reason}"
        )
        stop_evt = self._get_stop_event(task_id)
        stop_evt.set()

        try:
            task_service.stop_task(task_id, reason=reason)
            db.log_task_event(
                task_id=task_id,
                event_type="task_stopped",
                payload={"reason": reason, "timestamp": time.time()},
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error while updating task [{task_id}] to STOPPED: {e}")
            return False

    def is_stopped(self, task_id: str) -> bool:
        return self._get_stop_event(task_id).is_set()

    def get_active_plan(self, task_id: str) -> TaskPlan | None:
        return self._active_plans.get(task_id)

    def get_timeline(self, task_id: str) -> list[TimelineEntry]:
        return self._timelines.get(task_id, [])

    def record_timeline_entry(self, entry: TimelineEntry) -> None:
        if entry.task_id not in self._timelines:
            self._timelines[entry.task_id] = []
        self._timelines[entry.task_id].append(entry)

    def run_task(
        self,
        task_id: str,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        target_hwnd: int | None = None,
        confirmation_timeout_s: float = 30.0,
    ) -> dict[str, Any]:
        """
        Run closed-loop execution loop for the given task.
        Executes strictly ONE action at a time with full gap-closure safety gates.
        """
        lock = self._get_task_lock(task_id)
        if not lock.acquire(blocking=False):
            return {
                "success": False,
                "error": f"Task [{task_id}] is already executing in another thread.",
                "task_id": task_id,
            }

        stop_evt = self._get_stop_event(task_id)

        # Honor pre-set stop flags
        if stop_evt.is_set():
            logger.info(f"Task [{task_id}] was pre-stopped before execution started.")
            lock.release()
            return {"success": False, "status": "STOPPED", "task_id": task_id}

        stop_evt.clear()

        def emit(event_type: str, payload: dict[str, Any]):
            db.log_task_event(task_id=task_id, event_type=event_type, payload=payload)
            if on_event:
                try:
                    on_event(event_type, payload)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Error in on_event callback: {e}")

        try:
            task_record = task_service.get_task(task_id)
            goal = task_record.get("goal", "")

            emit("task_started", {"task_id": task_id, "goal": goal})

            task_metadata = task_record.get("metadata", {})
            guidance_mode = task_metadata.get("guidance_mode", "assist")

            if guidance_mode == "chat":
                # Pure Chat Mode: Bypass UI execution, just return a conversational response
                task_service.transition_state(
                    task_id,
                    TaskState.UNDERSTANDING,
                    reason="Chat mode: Parsing prompt...",
                )
                from providers.omniroute_provider import OmniRouteProvider

                # Chat mode: allow ALL models (not just free) and use generous timeout for local model warm-up
                provider = OmniRouteProvider(
                    free_only=False,
                    timeout_seconds=float(os.environ.get("COMPASS_LLM_TIMEOUT", "120.0")),
                )
                chat_model = task_metadata.get("model_id")
                logger.info(
                    f"Chat mode for [{task_id}]: model={chat_model}, goal='{goal}'"
                )
                token_buffer: list[str] = []
                last_token_time = [time.time()]

                def on_chat_token(token: str):
                    token_buffer.append(token)
                    now = time.time()
                    if len(token_buffer) >= 3 or (now - last_token_time[0]) >= 0.15:
                        chunk = "".join(token_buffer)
                        token_buffer.clear()
                        last_token_time[0] = now
                        emit("chat_token", {"chunk": chunk, "task_id": task_id})

                try:
                    resp = provider.chat_completion(
                        messages=[
                            {
                                "role": "system",
                                "content": "You are COMPASS, a helpful AI assistant. Answer the user's question clearly and concisely.",
                            },
                            {"role": "user", "content": goal},
                        ],
                        model=chat_model,
                        temperature=0.7,
                        max_tokens=2000,
                        on_token=on_chat_token,
                    )
                    if token_buffer:
                        chunk = "".join(token_buffer)
                        token_buffer.clear()
                        emit("chat_token", {"chunk": chunk, "task_id": task_id})

                    logger.info(
                        f"Chat mode response for [{task_id}]: success={resp.get('success')}, error={resp.get('error', 'none')}"
                    )
                    task_service.transition_state(
                        task_id,
                        TaskState.OBSERVING,
                        reason="Chat mode: Formatting response...",
                    )
                    if resp.get("success"):
                        chat_reply = resp.get("content", "")
                        emit(
                            "task_completed",
                            {
                                "details": chat_reply,
                                "evidence": {"chat_reply": chat_reply},
                            },
                        )
                        task_service.transition_state(
                            task_id,
                            TaskState.COMPLETED,
                            reason="Chat response generated",
                        )
                        return {
                            "success": True,
                            "status": "COMPLETED",
                            "task_id": task_id,
                            "evidence": {"chat_reply": chat_reply},
                        }
                    else:
                        err = resp.get("error", "Unknown error")
                        logger.error(f"Chat mode failed for [{task_id}]: {err}")
                        emit(
                            "task_completed",
                            {
                                "details": f"⚠️ Could not get AI response: {err}",
                                "evidence": {
                                    "chat_reply": f"⚠️ Could not get AI response: {err}"
                                },
                            },
                        )
                        task_service.transition_state(
                            task_id, TaskState.COMPLETED, reason=f"Chat error: {err}"
                        )
                        return {
                            "success": True,
                            "status": "COMPLETED",
                            "task_id": task_id,
                            "evidence": {"chat_reply": f"Error: {err}"},
                        }
                except Exception as ex:  # noqa: BLE001
                    logger.error(f"Chat mode exception for [{task_id}]: {ex}")
                    task_service.transition_state(
                        task_id, TaskState.OBSERVING, reason="Handling error..."
                    )
                    task_service.transition_state(
                        task_id, TaskState.COMPLETED, reason=f"Chat error: {ex}"
                    )
                    emit(
                        "task_completed",
                        {
                            "details": f"⚠️ Error: {ex!s}",
                            "evidence": {"chat_reply": f"⚠️ Error: {ex!s}"},
                        },
                    )
                    return {
                        "success": True,
                        "status": "COMPLETED",
                        "task_id": task_id,
                        "evidence": {"chat_reply": str(ex)},
                    }

            # Apply task-configured guidance mode
            if guidance_mode and guidance_mode != "chat":
                try:
                    from planner.models import GuidanceMode
                    mode_key = guidance_mode.upper()
                    if mode_key in GuidanceMode.__members__:
                        human_approval_controller.set_mode(GuidanceMode[mode_key])
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Could not apply guidance mode '{guidance_mode}': {e}")

            # Route to Claude Opus 5.5 Computer-Use Loop if configured
            model_id = task_metadata.get("model_id")
            if model_id == "claude-opus-5-5" or task_metadata.get("computer_use_mode") == "claude":
                logger.info(
                    f"Routing task [{task_id}] to Claude Opus 5.5 Computer-Use Loop"
                )
                from planner.claude_agent_loop import ClaudeComputerUseAgentLoop

                agent_loop = ClaudeComputerUseAgentLoop(
                    verifier=self.verifier,
                    max_iterations=int(task_metadata.get("max_iterations", 15)),
                )
                return agent_loop.run(
                    task_id=task_id,
                    goal=goal,
                    stop_event=stop_evt,
                    on_event=on_event,
                    confirmation_timeout_s=confirmation_timeout_s,
                )

            # Stage 1: Goal Understanding
            if stop_evt.is_set():
                emit(
                    "task_stopped",
                    {"reason": "STOP asserted during goal understanding"},
                )
                return {"success": False, "status": "STOPPED", "task_id": task_id}

            task_service.transition_state(
                task_id,
                TaskState.UNDERSTANDING,
                reason="Parsing goal intent and constraints",
            )
            goal_result: GoalUnderstandingResult = (
                goal_understanding_engine.understand_goal(goal)
            )
            emit(
                "goal_understood",
                {
                    "objective": goal_result.objective,
                    "target_app": goal_result.target_application,
                    "safety_level": goal_result.safety_level.value,
                    "is_ambiguous": goal_result.is_ambiguous,
                },
            )

            step_retries = 0
            plan: TaskPlan | None = None
            current_step_idx = 0
            verified_completed_steps: list[PlannedAction] = []
            total_dispatched_actions = 0

            while True:
                # 0. STOP Check at start of cycle
                if stop_evt.is_set():
                    logger.info(
                        f"Execution loop halted for task [{task_id}]: STOP flag set."
                    )
                    try:
                        db.update_task_state(
                            task_id,
                            TaskState.STOPPED.value,
                            reason="STOP flag asserted",
                        )
                    except Exception:  # noqa: BLE001, S110
                        pass
                    emit("task_stopped", {"reason": "STOP flag asserted"})
                    return {"success": False, "status": "STOPPED", "task_id": task_id}

                # 1. Perception: Capture live UI state & Observation Freshness
                task_service.transition_state(
                    task_id, TaskState.OBSERVING, reason="Observing current UI state"
                )
                obs_start = time.time()
                active_hwnd = target_hwnd

                import ctypes

                user32 = ctypes.windll.user32
                if active_hwnd and user32.IsWindow(active_hwnd):
                    try:
                        user32.ShowWindow(active_hwnd, 9)
                        user32.SetForegroundWindow(active_hwnd)
                    except Exception:  # noqa: BLE001, S110
                        pass
                    fw = uia_inspector.get_foreground_window()
                    w_info = fw.get("window") or {}
                    if not w_info or w_info.get("hwnd") != active_hwnd:
                        w_info = {
                            "hwnd": active_hwnd,
                            "title": uia_inspector._get_window_title(active_hwnd),
                            "class_name": uia_inspector._get_window_class(active_hwnd),
                            "process_id": uia_inspector._get_window_pid(active_hwnd),
                        }
                    hwnd = active_hwnd
                else:
                    fw = uia_inspector.get_foreground_window()
                    w_info = fw.get("window") or {}
                    hwnd = w_info.get("hwnd") if fw.get("success") else None

                tree_res = (
                    uia_inspector.get_element_tree(hwnd, depth=3, max_elements=80)
                    if hwnd
                    else {"elements": []}
                )
                current_snapshot = {
                    "window": w_info,
                    "elements": tree_res.get("elements", []),
                }
                obs_id = f"obs_{uuid.uuid4().hex[:8]}"
                resource_governor.record_frame(current_snapshot)

                emit(
                    "perception_updated",
                    {
                        "observation_id": obs_id,
                        "window_title": w_info.get("title"),
                        "hwnd": hwnd,
                        "element_count": len(current_snapshot["elements"]),
                    },
                )

                # 2. Plan generation / replanning if needed
                if plan is None or current_step_idx >= len(plan.steps):
                    if plan is not None and current_step_idx >= len(plan.steps):
                        # All planned steps executed -> perform real final-state verification
                        task_service.transition_state(
                            task_id,
                            TaskState.VERIFYING,
                            reason="Performing final state verification",
                        )
                        final_verif = None
                        verif_err_detail = None
                        if hasattr(self.verifier, "verify_final_goal_state"):
                            try:
                                final_verif = self.verifier.verify_final_goal_state(
                                    goal=goal,
                                    desired_final_state=goal_result.desired_final_state,
                                    current_snapshot=current_snapshot,
                                    completed_step_count=len(verified_completed_steps),
                                    target_app=goal_result.target_application,
                                )
                            except Exception as e:  # noqa: BLE001
                                verif_err_detail = f"Final verifier exception: {e}"
                                logger.error(verif_err_detail)
                                final_verif = None
                        else:
                            verif_err_detail = "Final verifier missing verify_final_goal_state method"

                        # COMPASS-AUDIT-001 fix: Never synthesize a VERIFIED result from completed steps.
                        # Missing/throwing/malformed/insufficient verifier must result in UNVERIFIED/BLOCKED.
                        if not isinstance(final_verif, VerificationResult):
                            detail_msg = verif_err_detail or "Final verifier returned invalid result type"
                            final_verif = VerificationResult(
                                status=VerificationStatus.UNVERIFIED,
                                details=detail_msg,
                                evidence={
                                    "error": detail_msg,
                                    "completed_steps_count": len(verified_completed_steps),
                                },
                            )
                        elif final_verif.status == VerificationStatus.VERIFIED and not final_verif.evidence:
                            # Must have goal-specific evidence
                            final_verif.status = VerificationStatus.UNVERIFIED
                            final_verif.details = "Final verification lacked sufficient goal-specific evidence."

                        if final_verif.status == VerificationStatus.VERIFIED:
                            detail_msg = str(
                                final_verif.details or "Final state verified"
                            )
                            task_service.transition_state(
                                task_id, TaskState.COMPLETED, reason=detail_msg
                            )
                            emit(
                                "task_completed",
                                {
                                    "task_id": task_id,
                                    "goal": goal,
                                    "evidence": final_verif.evidence
                                    if isinstance(final_verif.evidence, dict)
                                    else {},
                                    "details": detail_msg,
                                },
                            )
                            return {
                                "success": True,
                                "status": "COMPLETED",
                                "task_id": task_id,
                                "evidence": final_verif.evidence,
                            }
                        else:
                            detail_str = str(
                                final_verif.details or "Final-state unverified"
                            )
                            task_service.transition_state(
                                task_id, TaskState.BLOCKED, reason=detail_str
                            )
                            emit("task_blocked", {"reason": detail_str})
                            return {
                                "success": False,
                                "status": "BLOCKED",
                                "error": detail_str,
                                "task_id": task_id,
                            }

                    # Check STOP before transitioning to planning
                    if stop_evt.is_set():
                        try:
                            task_service.stop_task(
                                task_id, reason="STOP asserted before planning"
                            )
                        except Exception:  # noqa: BLE001, S110
                            pass
                        emit(
                            "task_stopped", {"reason": "STOP asserted before planning"}
                        )
                        return {
                            "success": False,
                            "status": "STOPPED",
                            "task_id": task_id,
                        }

                    task_service.transition_state(
                        task_id, TaskState.PLANNING, reason="Generating AI action plan"
                    )
                    emit("planning_started", {"task_id": task_id, "goal": goal})

                    # Check Circuit Breaker before AI request (§17)
                    if not ai_circuit_breaker.can_execute():
                        circuit_err = "AI provider circuit breaker is OPEN (service temporarily unavailable)."
                        logger.error(circuit_err)
                        task_service.transition_state(
                            task_id, TaskState.FAILED, reason=circuit_err
                        )
                        emit(
                            "task_failed",
                            {"reason": circuit_err, "error_code": "AI_UNAVAILABLE"},
                        )
                        emit("task_ai_unavailable", {"reason": circuit_err})
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": circuit_err,
                            "error_code": "AI_UNAVAILABLE",
                            "task_id": task_id,
                        }

                    t_start_ai = time.time()
                    try:
                        task_metadata = task_record.get("metadata", {})
                        selected_model = task_metadata.get(
                            "model_id"
                        ) or task_metadata.get("model")
                        success, new_plan, plan_err = self.planner.create_plan(
                            goal=goal,
                            ui_snapshot=current_snapshot,
                            task_id=task_id,
                            model=selected_model,
                        )
                        if time.time() - t_start_ai > TIMEOUT_AI_REQUEST_S and not (success and new_plan and getattr(new_plan, "steps", None)):
                            ai_circuit_breaker.record_failure()
                            success = False
                            plan_err = f"AI planning request timed out after {TIMEOUT_AI_REQUEST_S}s."
                        elif not success:
                            ai_circuit_breaker.record_failure()
                        else:
                            ai_circuit_breaker.record_success()
                    except Exception as ai_ex:  # noqa: BLE001
                        ai_circuit_breaker.record_failure()
                        success = False
                        new_plan = None
                        plan_err = f"AI planning exception: {ai_ex}"

                    # Check STOP immediately after late AI response (Directive §21)
                    if stop_evt.is_set():
                        logger.info(
                            f"Late AI response ignored for cancelled task [{task_id}]."
                        )
                        try:
                            task_service.stop_task(
                                task_id, reason="Late AI response discarded due to STOP"
                            )
                        except Exception:  # noqa: BLE001, S110
                            pass
                        emit(
                            "task_stopped",
                            {
                                "reason": "STOP asserted during planning; late response discarded"
                            },
                        )
                        return {
                            "success": False,
                            "status": "STOPPED",
                            "task_id": task_id,
                        }

                    if not success or not new_plan:
                        task_service.transition_state(
                            task_id,
                            TaskState.FAILED,
                            reason=f"Planning failed: {plan_err}",
                        )
                        emit("task_failed", {"reason": plan_err})
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": plan_err,
                            "task_id": task_id,
                        }

                    # Check plan length budget (§16)
                    plan_len_ok, plan_len_err = resource_governor.check_plan_length(
                        len(new_plan.steps)
                    )
                    if not plan_len_ok:
                        task_service.transition_state(
                            task_id, TaskState.FAILED, reason=plan_len_err
                        )
                        emit("task_failed", {"reason": plan_len_err})
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": plan_len_err,
                            "task_id": task_id,
                        }

                    plan = new_plan
                    self._active_plans[task_id] = plan
                    current_step_idx = 0
                    emit(
                        "planning_completed",
                        {
                            "plan_version": plan.plan_version,
                            "steps_count": len(plan.steps),
                            "summary": plan.reasoning_summary,
                        },
                    )

                # 3. Select ONE action & Formulate Structured Decision
                action = plan.steps[current_step_idx]
                task_service.transition_state(
                    task_id,
                    TaskState.DECIDING,
                    reason=f"Formulating Decision for action #{current_step_idx + 1}",
                )

                # Target Resolution
                resolved_el: dict[str, Any] | None = None
                if action.action_type in [
                    PlannerActionType.CLICK,
                    PlannerActionType.DOUBLE_CLICK,
                    PlannerActionType.RIGHT_CLICK,
                    PlannerActionType.TYPE,
                    PlannerActionType.FOCUS,
                    PlannerActionType.SCROLL,
                    PlannerActionType.HIGHLIGHT,
                    PlannerActionType.MOVE,
                ]:
                    res_result: TargetResolutionResult = self.resolver.resolve(
                        target_ref=action.target_reference,
                        available_elements=current_snapshot["elements"],
                        target_description=action.target_description,
                        target_hwnd=hwnd,
                    )
                    if res_result.success:
                        resolved_el = res_result.element

                # Formulate Decision
                obs_age_ms = (time.time() - obs_start) * 1000.0
                decision: Decision = decision_engine.formulate_decision(
                    task_id=task_id,
                    action=action,
                    target_element=resolved_el,
                    active_window=w_info,
                    observation_id=obs_id,
                    observation_age_ms=obs_age_ms,
                    original_goal=goal,
                )

                emit(
                    "decision_formulated",
                    {
                        "decision_id": decision.decision_id,
                        "action": decision.action.value,
                        "target": decision.target_description,
                        "risk": decision.risk_level.value,
                        "confidence": decision.confidence.value,
                        "requires_confirmation": decision.requires_confirmation,
                        "explanation": decision.human_explanation,
                    },
                )

                # 4. Human Approval Gateway (Directive §9, §10, Addendum §6, §7)
                requires_approval = human_approval_controller.should_require_approval(
                    decision
                )
                approval_state = "NOT_REQUIRED"

                if requires_approval:
                    task_service.transition_state(
                        task_id,
                        TaskState.WAITING_CONFIRMATION,
                        reason="Awaiting user confirmation",
                    )
                    appr_req = human_approval_controller.create_approval_request(
                        decision=decision,
                        window_hwnd=hwnd,
                        application_name=w_info.get("title", ""),
                        target_bounds=resolved_el.get("bounds")
                        if resolved_el
                        else None,
                        timeout_seconds=confirmation_timeout_s,
                    )
                    emit(
                        "waiting_confirmation",
                        {
                            "decision_id": decision.decision_id,
                            "approval_id": appr_req.approval_id,
                            "risk_level": decision.risk_level.value,
                            "explanation": decision.human_explanation,
                            "action": decision.action.value,
                            "target": decision.target_description,
                        },
                    )

                    # Poll for user approval, timeout, or STOP
                    poll_start = time.time()
                    granted = False
                    rejected = False
                    while time.time() - poll_start < confirmation_timeout_s:
                        if stop_evt.is_set():
                            emit(
                                "task_stopped",
                                {
                                    "reason": "STOP asserted while waiting for confirmation"
                                },
                            )
                            return {
                                "success": False,
                                "status": "STOPPED",
                                "task_id": task_id,
                            }

                        status = human_approval_controller.get_approval_status(
                            task_id, decision.decision_id
                        )
                        if status:
                            if status.state == ApprovalState.GRANTED:
                                granted = True
                                break
                            elif status.state == ApprovalState.REJECTED:
                                rejected = True
                                break

                        time.sleep(0.1)

                    if not granted:
                        fail_reason = (
                            "Confirmation rejected by user"
                            if rejected
                            else "Confirmation timed out without approval"
                        )
                        logger.warning(
                            f"Task [{task_id}] decision [{decision.decision_id}]: {fail_reason}"
                        )
                        task_service.transition_state(
                            task_id, TaskState.BLOCKED, reason=fail_reason
                        )
                        emit(
                            "confirmation_failed",
                            {
                                "decision_id": decision.decision_id,
                                "reason": fail_reason,
                            },
                        )

                        # Record timeline entry
                        self.record_timeline_entry(
                            TimelineEntry(
                                task_id=task_id,
                                decision_id=decision.decision_id,
                                observation_id=obs_id,
                                action=decision.action.value,
                                target=decision.target_description,
                                confidence=decision.confidence.value,
                                risk=decision.risk_level.value,
                                approval_state="REJECTED" if rejected else "EXPIRED",
                                validation_result={"ok": False, "reason": fail_reason},
                                human_explanation=decision.human_explanation,
                            )
                        )
                        return {
                            "success": False,
                            "status": "BLOCKED",
                            "error": fail_reason,
                            "task_id": task_id,
                        }

                    # Anti-Bypass Check: Validate that state has not drifted since approval
                    appr_valid, appr_err = (
                        human_approval_controller.validate_approval_binding(
                            task_id=task_id,
                            decision_id=decision.decision_id,
                            current_action=decision.action,
                            current_target_identifier=decision.target_description,
                            current_hwnd=hwnd,
                            current_app=w_info.get("title", ""),
                            current_bounds=resolved_el.get("bounds")
                            if resolved_el
                            else None,
                        )
                    )
                    if not appr_valid:
                        logger.warning(f"Approval anti-bypass invalidation: {appr_err}")
                        emit("approval_invalidated", {"reason": appr_err})
                        task_service.transition_state(
                            task_id,
                            TaskState.REPLANNING,
                            reason=f"Approval invalidated: {appr_err}",
                        )
                        plan = None
                        continue

                    approval_state = "GRANTED"

                # 5. Pre-Dispatch Stale Observation Guard & Safety Validation
                task_service.transition_state(
                    task_id,
                    TaskState.VALIDATING,
                    reason=f"Validating action #{current_step_idx + 1}",
                )
                decision_time = getattr(decision, "created_at", None) or getattr(decision, "timestamp", None) or time.time()
                freshness = stale_guard.validate_freshness(
                    observation_timestamp=decision_time,
                    target_hwnd=hwnd,
                    expected_window_title=w_info.get("title"),
                    is_sensitive=(decision.risk_level == RiskLevel.HIGH),
                    custom_max_age_ms=(
                        2000.0 if decision.risk_level == RiskLevel.HIGH else 30000.0
                    ),
                    live_element_exists=(
                        resolved_el is not None if decision.target else None
                    ),
                )

                if not freshness.is_fresh:
                    logger.warning(
                        f"Pre-dispatch stale check failed: {freshness.stale_reason}"
                    )
                    emit("validation_failed", {"reason": freshness.stale_reason})

                    diagnosis = recovery_engine.diagnose_failure(
                        cause=RecoveryCause.USER_INTERVENTION,
                        task_id=task_id,
                        original_goal=goal,
                        total_steps=len(plan.steps),
                        failed_step_index=current_step_idx,
                        verified_step_indices=[
                            i for i, _ in enumerate(verified_completed_steps)
                        ],
                        details=freshness.stale_reason or "Stale observation",
                    )
                    task_service.transition_state(
                        task_id, TaskState.REPLANNING, reason=diagnosis.explanation
                    )
                    emit("replanning", {"reason": diagnosis.explanation})
                    plan = None
                    continue

                # Coordinate bounds validation (for mouse actions targeting coordinates)
                if action.action_type in [
                    PlannerActionType.CLICK,
                    PlannerActionType.DOUBLE_CLICK,
                    PlannerActionType.RIGHT_CLICK,
                ]:
                    if resolved_el and "bounds" in resolved_el:
                        b = resolved_el["bounds"]
                        cx = (b.get("left", 0) + b.get("right", 0)) // 2
                        cy = (b.get("top", 0) + b.get("bottom", 0)) // 2
                        coord_val = check_coordinates_safe(cx, cy, bounds=b, hwnd=hwnd)
                        if not coord_val.ok:
                            logger.warning(
                                f"Coordinate safety rejection: {coord_val.reason}"
                            )
                            emit("validation_failed", {"reason": coord_val.reason})
                            task_service.transition_state(
                                task_id, TaskState.FAILED, reason=coord_val.reason
                            )
                            return {
                                "success": False,
                                "status": "FAILED",
                                "error": coord_val.reason,
                                "task_id": task_id,
                            }

                # 6. STOP Check immediately prior to dispatch
                if stop_evt.is_set():
                    logger.info(
                        f"STOP intercepted immediately prior to dispatch for task [{task_id}]."
                    )
                    try:
                        db.update_task_state(
                            task_id,
                            TaskState.STOPPED.value,
                            reason="STOP intercepted pre-dispatch",
                        )
                    except Exception:  # noqa: BLE001, S110
                        pass
                    emit("task_stopped", {"reason": "STOP intercepted pre-dispatch"})
                    return {"success": False, "status": "STOPPED", "task_id": task_id}

                # 7. Action Budget & Approval Consumption (§4, §9, §16)
                total_dispatched_actions += 1
                budget_ok, budget_err = resource_governor.check_action_budget(
                    total_dispatched_actions
                )
                if not budget_ok:
                    logger.error(f"ExecutionEngine halted: {budget_err}")
                    task_service.transition_state(
                        task_id, TaskState.FAILED, reason=budget_err
                    )
                    emit("task_failed", {"reason": budget_err})
                    return {
                        "success": False,
                        "status": "FAILED",
                        "error": budget_err,
                        "task_id": task_id,
                    }

                if requires_approval and approval_state == "GRANTED":
                    human_approval_controller.consume_approval(
                        task_id, decision.decision_id
                    )

                # Dispatch Action
                task_service.transition_state(
                    task_id,
                    TaskState.ACTING,
                    reason=f"Executing action #{current_step_idx + 1}",
                )
                emit(
                    "action_started",
                    {
                        "step_index": current_step_idx,
                        "action": decision.action.value,
                        "target": decision.target_description,
                    },
                )

                dispatch_res = self._dispatch_single_action(
                    action, resolved_el, task_id
                )
                emit(
                    "action_completed",
                    {
                        "step_index": current_step_idx,
                        "success": dispatch_res.get("success", False),
                        "execution_method": dispatch_res.get("execution_method", ""),
                    },
                )

                if not dispatch_res.get("success", False):
                    err_msg = dispatch_res.get("error", "Action dispatch failed")
                    logger.warning(f"Action dispatch failed: {err_msg}")
                    if not decision.is_repeatable:
                        logger.warning(
                            f"Action #{current_step_idx + 1} is non-repeatable. Automatic retry prohibited."
                        )
                        task_service.transition_state(
                            task_id,
                            TaskState.FAILED,
                            reason=f"Non-repeatable action dispatch failed: {err_msg}. Automatic retry prohibited.",
                        )
                        emit(
                            "task_failed",
                            {
                                "reason": f"Non-repeatable action failed dispatch: {err_msg}"
                            },
                        )
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": f"Non-repeatable action dispatch failed: {err_msg}",
                            "task_id": task_id,
                        }

                    step_retries += 1
                    if step_retries >= self.max_retries_per_step:
                        task_service.transition_state(
                            task_id, TaskState.FAILED, reason=err_msg
                        )
                        emit("task_failed", {"reason": err_msg})
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": err_msg,
                            "task_id": task_id,
                        }

                    task_service.transition_state(
                        task_id, TaskState.REPLANNING, reason=err_msg
                    )
                    emit("replanning", {"attempt": step_retries, "reason": err_msg})
                    plan = None
                    time.sleep(0.5)
                    continue

                # 8. Post-Action Re-perception & Verification
                if stop_evt.is_set():
                    logger.info(
                        f"STOP asserted during action dispatch for task [{task_id}]."
                    )
                    emit(
                        "task_stopped",
                        {"reason": "STOP asserted during action dispatch"},
                    )
                    return {"success": False, "status": "STOPPED", "task_id": task_id}

                task_service.transition_state(
                    task_id,
                    TaskState.VERIFYING,
                    reason=f"Verifying action #{current_step_idx + 1}",
                )
                emit("verification_started", {"step_index": current_step_idx})
                time.sleep(0.2)

                # If action launched an app, poll briefly for the new window
                if action.action_type == PlannerActionType.LAUNCH_APP:
                    target_token = (
                        action.parameters.get("app")
                        or action.parameters.get("app_name")
                        or action.target_description
                        or ""
                    ).lower().replace(".exe", "").strip()
                    new_hwnd = None
                    for _ in range(15):  # poll up to 3.0s
                        time.sleep(0.2)
                        fw = uia_inspector.get_foreground_window()
                        fw_win = fw.get("window") or {}
                        fw_title = str(fw_win.get("title", "")).lower()
                        if target_token and target_token in fw_title:
                            new_hwnd = fw_win.get("hwnd")
                            break
                        # Check desktop top windows
                        if target_token:
                            found_win = uia_inspector.find_window_by_title_substring(
                                target_token, bring_to_front=True
                            )
                            if found_win:
                                new_hwnd, _ = found_win
                                break
                    if new_hwnd:
                        active_hwnd = new_hwnd
                        post_hwnd = new_hwnd
                        target_hwnd = new_hwnd

                post_hwnd = (
                    active_hwnd
                    if (active_hwnd and user32.IsWindow(active_hwnd))
                    else None
                )
                if not post_hwnd:
                    post_fw = uia_inspector.get_foreground_window()
                    post_w = post_fw.get("window") or {}
                    post_hwnd = post_w.get("hwnd")
                else:
                    post_fw = uia_inspector.get_foreground_window()
                    post_w = post_fw.get("window") or {}
                    if not post_w or post_w.get("hwnd") != post_hwnd:
                        post_w = {
                            "hwnd": post_hwnd,
                            "title": uia_inspector._get_window_title(post_hwnd),
                            "class_name": uia_inspector._get_window_class(post_hwnd),
                            "process_id": uia_inspector._get_window_pid(post_hwnd),
                        }

                if post_hwnd:
                    target_hwnd = post_hwnd

                post_tree = (
                    uia_inspector.get_element_tree(post_hwnd, depth=3, max_elements=80)
                    if post_hwnd
                    else {"elements": []}
                )
                post_snapshot = {
                    "window": post_w,
                    "elements": post_tree.get("elements", []),
                }

                verif_result = self.verifier.verify_action(
                    action=action,
                    post_snapshot=post_snapshot,
                    resolved_element=resolved_el,
                )

                emit(
                    "verification_completed",
                    {
                        "step_index": current_step_idx,
                        "status": verif_result.status.value,
                        "details": verif_result.details,
                        "duration_ms": verif_result.duration_ms,
                    },
                )

                # Record Timeline Entry
                self.record_timeline_entry(
                    TimelineEntry(
                        task_id=task_id,
                        decision_id=decision.decision_id,
                        observation_id=obs_id,
                        action=decision.action.value,
                        target=decision.target_description,
                        confidence=decision.confidence.value,
                        risk=decision.risk_level.value,
                        approval_state=approval_state,
                        validation_result={"ok": True},
                        execution_result=dispatch_res,
                        verification_result=verif_result.to_dict(),
                        human_explanation=decision.human_explanation,
                    )
                )

                # 9. Handle Verification Outcome & Adaptive Recovery
                if verif_result.status == VerificationStatus.VERIFIED:
                    logger.info(
                        f"Action #{current_step_idx + 1} successfully VERIFIED."
                    )
                    verified_completed_steps.append(action)
                    current_step_idx += 1
                    step_retries = 0

                elif verif_result.status == VerificationStatus.FAILED:
                    logger.warning(
                        f"Action #{current_step_idx + 1} verification FAILED: {verif_result.details}"
                    )
                    if not decision.is_repeatable:
                        logger.warning(
                            f"Action #{current_step_idx + 1} is non-repeatable. Blind retry prohibited."
                        )
                        task_service.transition_state(
                            task_id,
                            TaskState.BLOCKED,
                            reason=f"Non-repeatable action verification failed: {verif_result.details}. User intervention required.",
                        )
                        emit(
                            "task_blocked",
                            {
                                "reason": f"Non-repeatable action verification failed: {verif_result.details}"
                            },
                        )
                        return {
                            "success": False,
                            "status": "BLOCKED",
                            "error": f"Non-repeatable action verification failed: {verif_result.details}",
                            "task_id": task_id,
                        }

                    step_retries += 1
                    if step_retries >= self.max_retries_per_step:
                        task_service.transition_state(
                            task_id, TaskState.FAILED, reason=verif_result.details
                        )
                        emit(
                            "task_failed",
                            {
                                "reason": f"Verification failed after {self.max_retries_per_step} attempts."
                            },
                        )
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": verif_result.details,
                            "task_id": task_id,
                        }

                    diagnosis = recovery_engine.diagnose_failure(
                        cause=RecoveryCause.VERIFICATION_FAILED,
                        task_id=task_id,
                        original_goal=goal,
                        total_steps=len(plan.steps),
                        failed_step_index=current_step_idx,
                        verified_step_indices=[
                            i for i, _ in enumerate(verified_completed_steps)
                        ],
                        details=verif_result.details,
                    )
                    task_service.transition_state(
                        task_id, TaskState.REPLANNING, reason=diagnosis.explanation
                    )
                    emit(
                        "replanning",
                        {"attempt": step_retries, "reason": diagnosis.explanation},
                    )
                    plan = None
                    time.sleep(0.5)

                elif verif_result.status in (
                    VerificationStatus.UNCERTAIN,
                    VerificationStatus.UNVERIFIED,
                ):
                    logger.warning(
                        f"Action #{current_step_idx + 1} verification {verif_result.status.value}: {verif_result.details}"
                    )
                    step_retries += 1
                    if step_retries >= self.max_retries_per_step:
                        task_service.transition_state(
                            task_id, TaskState.FAILED, reason=verif_result.details
                        )
                        emit("task_failed", {"reason": verif_result.details})
                        return {
                            "success": False,
                            "status": "FAILED",
                            "error": verif_result.details,
                            "task_id": task_id,
                        }

                    task_service.transition_state(
                        task_id, TaskState.REPLANNING, reason=verif_result.details
                    )
                    emit(
                        "replanning",
                        {"attempt": step_retries, "reason": verif_result.details},
                    )
                    plan = None
                    time.sleep(0.5)

        except Exception as e:  # noqa: BLE001
            if stop_evt.is_set():
                logger.info(
                    f"ExecutionEngine: task [{task_id}] cleanly halted on STOP despite interruption exception: {e}"
                )
                return {"success": False, "status": "STOPPED", "task_id": task_id}
            logger.exception(
                f"Unexpected error in ExecutionEngine for task [{task_id}]: {e}"
            )
            try:
                task_service.transition_state(task_id, TaskState.FAILED, reason=str(e))
                emit("task_failed", {"reason": str(e)})
            except Exception:  # noqa: BLE001, S110
                pass
            return {
                "success": False,
                "status": "FAILED",
                "error": str(e),
                "task_id": task_id,
            }
        finally:
            if lock.locked():
                try:
                    lock.release()
                except Exception:  # noqa: BLE001, S110
                    pass
            self.cleanup_task_resources(task_id)

    def cleanup_task_resources(self, task_id: str) -> dict[str, Any]:
        """
        Phase 5 Resource Cleanup (§4).
        Cleans up in-flight plans, approvals, stop events, and guarantees terminal state.
        Ensures:
        - No orphan task
        - No stuck retry loop
        - No background execution after STOP
        - No stale RUNNING/transitional state
        - Releases task lock if held
        """
        logger.info(f"ExecutionEngine cleaning up resources for task [{task_id}]")

        # 1. Discard active plan
        removed_plan = self._active_plans.pop(task_id, None)

        # 2. Cleanup approvals
        cleaned_approvals = human_approval_controller.cleanup_task(task_id)

        # 3. Release lock if held
        lock = self._locks.get(task_id)
        lock_released = False
        if lock and lock.locked():
            try:
                lock.release()
                lock_released = True
            except RuntimeError:
                pass

        # 4. Guarantee terminal state in database if left in transitional state
        terminal_fixed = False
        try:
            task = task_service.get_task(task_id)
            current_state = task.get("state")
            terminal_values = {s.value for s in TERMINAL_STATES}
            if current_state not in terminal_values:
                target_state = (
                    TaskState.STOPPED.value
                    if self.is_stopped(task_id)
                    else TaskState.FAILED.value
                )
                cleanup_reason = (
                    "Task stopped by user request"
                    if self.is_stopped(task_id)
                    else "Task terminated by cleanup handler"
                )
                db.update_task_state(task_id, target_state, reason=cleanup_reason)
                terminal_fixed = True
        except Exception as ex:  # noqa: BLE001
            logger.debug(f"Cleanup state check error: {ex}")

        # 5. Log cleanup event
        try:
            db.log_task_event(
                task_id,
                "resources_cleaned",
                {
                    "had_active_plan": removed_plan is not None,
                    "cleaned_approvals": cleaned_approvals,
                    "lock_released": lock_released,
                    "terminal_state_enforced": terminal_fixed,
                    "timestamp": time.time(),
                },
            )
        except Exception:  # noqa: BLE001, S110
            pass

        return {
            "task_id": task_id,
            "had_active_plan": removed_plan is not None,
            "cleaned_approvals": cleaned_approvals,
            "terminal_state_enforced": terminal_fixed,
        }

    def _dispatch_single_action(
        self, action: PlannedAction, element: dict[str, Any] | None, task_id: str
    ) -> dict[str, Any]:
        """Dispatch single action through Phase 2/4 action_dispatcher."""
        atype = action.action_type

        if atype == PlannerActionType.WAIT:
            dur_ms = action.parameters.get("duration_ms", 500)
            time.sleep(min(max(dur_ms, 0), 5000) / 1000.0)
            return {"success": True, "action_type": "wait"}

        elif atype == PlannerActionType.OBSERVE:
            # COMPASS-AUDIT-003 fix: OBSERVE is strictly observational.
            # It must not silently interpret an 'app' parameter as an instruction to start processes.
            # Observation captures perception context without executing OS actions.
            target_filter = action.parameters.get("app") or action.parameters.get("target")
            return {
                "success": True,
                "action_type": "observe",
                "observed_target": target_filter,
                "details": "Observation completed safely without process dispatch",
            }

        elif atype == PlannerActionType.KEY_COMBINATION:
            combo = action.parameters.get("combination") or action.parameters.get(
                "keys", ""
            )
            res = action_dispatcher.send_key_combination(combo, task_id=task_id)
            return res.to_dict()

        elif atype == PlannerActionType.LAUNCH_APP:
            app_name = (
                action.parameters.get("app")
                or action.parameters.get("app_name")
                or action.parameters.get("name")
                or action.parameters.get("target", "")
            )
            path = action.parameters.get("path")
            args = action.parameters.get("args")
            res = action_dispatcher.launch_application(
                app_name=app_name, path=path, args=args, task_id=task_id
            )
            return res.to_dict()

        elif atype == PlannerActionType.OPEN_URL:
            url = action.parameters.get("url") or action.parameters.get("target", "")
            browser = action.parameters.get("browser")
            res = action_dispatcher.open_url(url=url, browser=browser, task_id=task_id)
            return res.to_dict()

        if not element:
            if atype in [PlannerActionType.KEY, PlannerActionType.KEY_PRESS]:
                key_name = action.parameters.get("key", "")
                res = action_dispatcher.send_key(key_name=key_name, task_id=task_id)
                return res.to_dict()
            elif atype == PlannerActionType.MOVE:
                x = action.parameters.get("x", 100)
                y = action.parameters.get("y", 100)
                res = action_dispatcher.move_cursor(x, y, task_id=task_id)
                return res.to_dict()
            elif atype == PlannerActionType.TYPE:
                text_to_type = action.parameters.get("text", "")
                res = action_dispatcher.type_text(text_to_type, task_id=task_id)
                return res.to_dict()
            return {
                "success": False,
                "error": f"Target element required for {atype.value} action",
            }

        if atype == PlannerActionType.CLICK:
            res = action_dispatcher.click_element(element, task_id=task_id)
            return res.to_dict()

        elif atype == PlannerActionType.DOUBLE_CLICK:
            res = action_dispatcher.double_click_element(element, task_id=task_id)
            return res.to_dict()

        elif atype == PlannerActionType.RIGHT_CLICK:
            res = action_dispatcher.right_click_element(element, task_id=task_id)
            return res.to_dict()

        elif atype == PlannerActionType.TYPE:
            text = action.parameters.get("text", "")
            res = action_dispatcher.type_text(element, text=text, task_id=task_id)
            return res.to_dict()

        elif atype == PlannerActionType.FOCUS:
            res = action_dispatcher.focus_element(element, task_id=task_id)
            return res.to_dict()

        elif atype in [PlannerActionType.KEY, PlannerActionType.KEY_PRESS]:
            key_name = action.parameters.get("key", "")
            res = action_dispatcher.send_key(key_name, task_id=task_id)
            return res.to_dict()

        elif atype == PlannerActionType.SCROLL:
            delta = action.parameters.get("delta", -120)
            res = action_dispatcher.scroll_element(
                element, delta=delta, task_id=task_id
            )
            return res.to_dict()

        elif atype == PlannerActionType.HIGHLIGHT:
            dur = action.parameters.get("duration_ms", 1000)
            res = action_dispatcher.highlight_element(
                element, duration_ms=dur, task_id=task_id
            )
            return res.to_dict()

        return {"success": False, "error": f"Unsupported action type: {atype}"}


execution_engine = ExecutionEngine()
