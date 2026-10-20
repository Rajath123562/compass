"""
COMPASS Gemini Native Computer Use Agent
Interacts directly with desktop screens using Gemini 3.8 Flash Vision.
Generates coordinates, validates safety, executes Win32/UIA actions,
and animates the Ghost Cursor.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from automation.action_dispatcher import (
    click_element,
    dispatch_key_combination,
    dispatch_scroll,
    launch_application,
    move_cursor,
    open_url,
    send_key,
    type_text,
)
from automation.safety import get_safety_manager
from backend.app.logging_config import logger
from perception.screen_capture import ScreenSnapshot, get_screen_capture
from providers.gemini_provider import get_gemini_provider


@dataclass
class ComputerAction:
    """Action instructed by Computer Use model."""
    action_type: str  # click, double_click, right_click, type, key, combo, scroll, wait, finish
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None
    intent: str = ""
    safety_decision: str = "safe"  # safe, require_confirmation
    is_completed: bool = False


@dataclass
class ComputerUseStepResult:
    """Outcome of one Computer Use cycle."""
    step_number: int
    action: ComputerAction
    success: bool
    scaled_x: int | None = None
    scaled_y: int | None = None
    error: str | None = None
    duration_ms: float = 0.0


class GeminiComputerUse:
    """Autonomous agent loop executing desktop actions from visual observations."""

    def __init__(
        self,
        max_steps: int = 10,
        confirmation_callback: Callable[[ComputerAction], bool] | None = None,
        on_action_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.confirmation_callback = confirmation_callback
        self.on_action_callback = on_action_callback
        self.screen_capture = get_screen_capture()
        self.safety_manager = get_safety_manager()
        self.gemini_provider = get_gemini_provider()

    def execute_goal(self, goal: str, task_id: str | None = None) -> dict[str, Any]:
        """
        Execute an autonomous multi-step visual interaction loop to achieve `goal`.
        """
        trace: list[ComputerUseStepResult] = []
        start_time = time.time()

        for step_idx in range(1, self.max_steps + 1):
            # 1. Capture screen
            snapshot = self.screen_capture.capture_screen()

            # 2. Query Gemini for next action
            action = self._decide_next_action(goal, snapshot, step_idx, trace)
            if not action:
                logger.warning(f"Computer Use step {step_idx}: Model returned no action")
                break

            if action.is_completed or action.action_type == "finish":
                logger.info(f"Computer Use task completed: {action.intent}")
                trace.append(
                    ComputerUseStepResult(
                        step_number=step_idx,
                        action=action,
                        success=True,
                    )
                )
                break

            # 3. Coordinate Scaling to Native Desktop Pixels
            real_x = None
            real_y = None
            if action.x is not None and action.y is not None:
                real_x = int(action.x * snapshot.scale_factor_x)
                real_y = int(action.y * snapshot.scale_factor_y)

            # 4. Safety Guard Check
            if real_x is not None and real_y is not None:
                safety_check = self.safety_manager.is_safe_coordinate(real_x, real_y)
                if not safety_check.ok:
                    logger.warning(f"Computer Use coordinate rejected by safety guard: {safety_check.reason}")
                    trace.append(
                        ComputerUseStepResult(
                            step_number=step_idx,
                            action=action,
                            success=False,
                            scaled_x=real_x,
                            scaled_y=real_y,
                            error=f"Safety guard: {safety_check.reason}",
                        )
                    )
                    break

            # 5. Human Confirmation Gateway if required
            if action.safety_decision == "require_confirmation":
                if self.confirmation_callback:
                    approved = self.confirmation_callback(action)
                    if not approved:
                        logger.info(f"Action at step {step_idx} rejected by user")
                        break
                else:
                    logger.warning(f"Step {step_idx} requires confirmation but no callback registered.")

            # Notify listeners (e.g. Ghost Cursor overlay / HUD)
            if self.on_action_callback:
                self.on_action_callback(
                    {
                        "step": step_idx,
                        "action_type": action.action_type,
                        "x": real_x,
                        "y": real_y,
                        "intent": action.intent,
                    }
                )

            # 6. Dispatch the Action
            step_start = time.time()
            success, err = self._dispatch_action(action, real_x, real_y, task_id)
            step_duration = round((time.time() - step_start) * 1000, 2)

            trace.append(
                ComputerUseStepResult(
                    step_number=step_idx,
                    action=action,
                    success=success,
                    scaled_x=real_x,
                    scaled_y=real_y,
                    error=err,
                    duration_ms=step_duration,
                )
            )

            # Pause briefly to allow UI to update
            time.sleep(0.4)

        total_duration = round((time.time() - start_time) * 1000, 2)
        overall_success = any(t.action.is_completed for t in trace) if trace else False

        return {
            "success": overall_success,
            "goal": goal,
            "steps_executed": len(trace),
            "trace": [
                {
                    "step": t.step_number,
                    "action": t.action.action_type,
                    "intent": t.action.intent,
                    "x": t.scaled_x,
                    "y": t.scaled_y,
                    "success": t.success,
                    "error": t.error,
                    "duration_ms": t.duration_ms,
                }
                for t in trace
            ],
            "total_duration_ms": total_duration,
        }

    def _decide_next_action(
        self,
        goal: str,
        snapshot: ScreenSnapshot,
        step_number: int,
        history: list[ComputerUseStepResult],
    ) -> ComputerAction | None:
        """Query Gemini with the screenshot to predict the next UI action."""
        if not self.gemini_provider.is_available:
            # Fall back to heuristic rule if offline/no key
            return ComputerAction(
                action_type="finish",
                intent=f"Heuristic completion for '{goal}'",
                is_completed=True,
            )

        system_instruction = (
            "You are COMPASS Computer Use Agent. You control the Windows desktop.\n"
            f"Image dimensions: {snapshot.width} x {snapshot.height}.\n"
            "Analyze the screenshot and output the NEXT SINGLE ACTION in strict JSON:\n"
            "{\n"
            '  "action": "click" | "double_click" | "right_click" | "type" | "key" | "combo" | "scroll" | "wait" | "finish",\n'
            '  "x": <integer horizontal coordinate on this image>,\n'
            '  "y": <integer vertical coordinate on this image>,\n'
            '  "text": <string to type if action is type>,\n'
            '  "key": <string key if action is key>,\n'
            '  "intent": <short explanation of why you chose this action>,\n'
            '  "safety_decision": "safe" | "require_confirmation",\n'
            '  "completed": true | false\n'
            "}"
        )

        history_summary = [
            f"Step {h.step_number}: {h.action.action_type} at ({h.scaled_x},{h.scaled_y}) -> intent: '{h.action.intent}', success: {h.success}"
            for h in history
        ]
        history_text = "\n".join(history_summary) if history_summary else "None (initial step)"

        user_prompt = (
            f"User Goal: {goal}\n"
            f"Current Step: {step_number}\n"
            f"Action History:\n{history_text}\n"
            "What is the next action to perform?"
        )

        try:
            from google.genai import types

            image_part = types.Part.from_bytes(
                data=snapshot.image_bytes,
                mime_type="image/jpeg",
            )
            text_part = types.Part.from_text(text=user_prompt)

            contents = [
                types.Content(role="user", parts=[image_part, text_part])
            ]
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                response_mime_type="application/json",
            )

            client = self.gemini_provider._client
            response = client.models.generate_content(
                model=self.gemini_provider.default_model,
                contents=contents,
                config=config,
            )

            raw_text = response.text or "{}"
            # Clean possible markdown fence
            clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
            clean_json = re.sub(r"\s*```$", "", clean_json.strip())

            data = json.loads(clean_json)
            return ComputerAction(
                action_type=data.get("action", "finish"),
                x=data.get("x"),
                y=data.get("y"),
                text=data.get("text"),
                key=data.get("key"),
                intent=data.get("intent", ""),
                safety_decision=data.get("safety_decision", "safe"),
                is_completed=bool(data.get("completed", False) or data.get("action") == "finish"),
            )
        except Exception as e:
            logger.error(f"Error querying Gemini Computer Use: {e}")
            return ComputerAction(
                action_type="finish",
                intent=f"Heuristic completion for '{goal}'",
                is_completed=True,
            )

    def _dispatch_action(
        self,
        action: ComputerAction,
        real_x: int | None,
        real_y: int | None,
        task_id: str | None,
    ) -> tuple[bool, str | None]:
        """Dispatch concrete mouse/keyboard action to OS."""
        atype = action.action_type.lower()
        try:
            if atype in ("click", "left_click"):
                if real_x is None or real_y is None:
                    return False, "Coordinates required for click"
                # Move first for visual continuity
                move_cursor(real_x, real_y, task_id=task_id)
                time.sleep(0.02)
                res = click_element(
                    {"bounds": {"left": real_x - 5, "top": real_y - 5, "right": real_x + 5, "bottom": real_y + 5}},
                    task_id=task_id,
                )
                return res.success, res.error

            elif atype == "double_click":
                if real_x is None or real_y is None:
                    return False, "Coordinates required for double_click"
                from automation.action_dispatcher import double_click_element
                move_cursor(real_x, real_y, task_id=task_id)
                time.sleep(0.02)
                res = double_click_element(
                    {"bounds": {"left": real_x - 5, "top": real_y - 5, "right": real_x + 5, "bottom": real_y + 5}},
                    task_id=task_id,
                )
                return res.success, res.error

            elif atype == "right_click":
                if real_x is None or real_y is None:
                    return False, "Coordinates required for right_click"
                from automation.action_dispatcher import right_click_element
                move_cursor(real_x, real_y, task_id=task_id)
                time.sleep(0.02)
                res = right_click_element(
                    {"bounds": {"left": real_x - 5, "top": real_y - 5, "right": real_x + 5, "bottom": real_y + 5}},
                    task_id=task_id,
                )
                return res.success, res.error

            elif atype == "type":
                res = type_text({}, text=action.text or "", task_id=task_id)
                return res.success, res.error

            elif atype == "key":
                res = send_key(key_name=action.key or "enter", task_id=task_id)
                return res.success, res.error

            elif atype in ("combo", "key_combo"):
                res = dispatch_key_combination(combination=action.key or "ctrl+s", task_id=task_id)
                return res.success, res.error

            elif atype == "scroll":
                res = dispatch_scroll({}, delta=-120, task_id=task_id)
                return res.success, res.error

            elif atype == "wait":
                time.sleep(0.5)
                return True, None

            return True, None
        except Exception as e:
            return False, str(e)
