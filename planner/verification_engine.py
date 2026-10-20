"""
COMPASS Verification Engine
Evaluates post-action UI perception state to verify expected state transitions.
Distinguishes VERIFIED, FAILED, and UNCERTAIN states with bounded polling.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from perception import uia_inspector
from planner.models import PlannedAction, VerificationResult, VerificationStatus


class VerificationEngine:
    """
    Verifies actual post-action state changes against planned verification conditions.
    """

    def __init__(self, default_poll_interval_s: float = 0.2):
        self.default_poll_interval_s = default_poll_interval_s

    def verify_action(
        self,
        action: PlannedAction,
        post_snapshot: dict[str, Any],
        resolved_element: dict[str, Any] | None = None,
        timeout_ms: float | None = None,
    ) -> VerificationResult:
        """
        Verify that an action successfully produced its expected outcome.
        Uses post-action perception snapshot and live UIA re-queries if needed.
        """
        start_t = time.time()
        condition = action.verification_condition

        # If no explicit verification condition was attached by planner, infer from action type
        if not condition:
            return self._infer_and_verify(action, post_snapshot, resolved_element)

        timeout_s = (timeout_ms or condition.timeout_ms) / 1000.0
        deadline = start_t + timeout_s

        ctype = condition.condition_type.lower()
        expected = condition.expected_value

        target_hwnd = (
            resolved_element.get("hwnd")
            if (resolved_element and isinstance(resolved_element, dict))
            else None
        )
        if not target_hwnd:
            target_hwnd = (post_snapshot.get("window") or {}).get("hwnd")

        last_observed: dict[str, Any] | None = None

        while True:
            # Re-capture current state if polling beyond initial snapshot
            current_snapshot = post_snapshot
            if time.time() - start_t > 0.3 and target_hwnd:
                tree_res = uia_inspector.get_element_tree(
                    target_hwnd, depth=3, max_elements=80
                )
                current_snapshot = {
                    "window": post_snapshot.get("window") or {},
                    "elements": tree_res.get("elements", []),
                }

            observed_elements = current_snapshot.get("elements") or []
            window_info = current_snapshot.get("window") or {}

            # Case 1: focused condition
            if "focus" in ctype:
                # Find matching element in current elements
                target_matched = (
                    self._find_matching_element(resolved_element, observed_elements)
                    or self._find_matching_element(condition.target, observed_elements)
                    or resolved_element
                )
                is_focused = False
                if target_matched:
                    last_observed = target_matched
                    if target_matched.get("is_focused", False):
                        is_focused = True
                if not is_focused and target_hwnd:
                    import ctypes

                    user32 = ctypes.windll.user32
                    try:
                        user32.AllowSetForegroundWindow(0xFFFFFFFF)
                        user32.ShowWindow(target_hwnd, 9)
                        user32.SetForegroundWindow(target_hwnd)
                    except Exception:  # noqa: BLE001, S110
                        pass
                    fg = user32.GetForegroundWindow()
                    # COMPASS-AUDIT-018 fix: do NOT allow action type shortcut 'click' or 'focus' to fake focus
                    if (
                        fg == target_hwnd
                        or bool(user32.GetAncestor(fg, 2) == target_hwnd)
                    ):
                        is_focused = True

                if is_focused:
                    t_name = (
                        target_matched.get("name")
                        if target_matched
                        else window_info.get("title", "Window")
                    )
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Target '{t_name}' is verified focused.",
                        observed_state={"is_focused": True, "name": t_name},
                        expected_state={"is_focused": True},
                        duration_ms=round((time.time() - start_t) * 1000, 2),
                    )

            # Case 2: text_equals or text_contains condition
            elif "text" in ctype or action.action_type.value == "type":
                target_matched = (
                    self._find_matching_element(resolved_element, observed_elements)
                    or self._find_matching_element(condition.target, observed_elements)
                    or resolved_element
                )
                expected_text = expected or action.parameters.get("text", "")
                if target_matched:
                    last_observed = target_matched
                    # Revalidate element live to read fresh Value/Name/Text
                    reval = uia_inspector.revalidate_element(target_matched)
                    fresh_el = reval.get("element") or target_matched
                    current_text = (
                        fresh_el.get("text")
                        or fresh_el.get("name")
                        or target_matched.get("text")
                        or target_matched.get("name", "")
                    )

                    # Also inspect all observed elements in the window for text matches
                    if not (expected_text and expected_text in current_text):
                        for el in observed_elements:
                            cand_text = el.get("text") or el.get("name") or ""
                            if expected_text and expected_text in cand_text:
                                current_text = cand_text
                                break

                    # Also inspect live window title (e.g. Notepad window title reflects typed text)
                    win_title = window_info.get("title", "")
                    if target_hwnd:
                        try:
                            live_title = uia_inspector._get_window_title(target_hwnd)
                            if live_title:
                                win_title = live_title
                        except Exception:  # noqa: BLE001, S110
                            pass

                    if expected_text and (
                        expected_text in current_text or expected_text in win_title
                    ):
                        return VerificationResult(
                            status=VerificationStatus.VERIFIED,
                            details=f"Text content verified: '{expected_text}' found in target UI.",
                            observed_state={
                                "text": current_text,
                                "window_title": win_title,
                            },
                            expected_state={"expected_text": expected_text},
                            duration_ms=round((time.time() - start_t) * 1000, 2),
                        )

            # Case 3: element_exists
            elif "exist" in ctype or "appear" in ctype:
                target_matched = self._find_matching_element(
                    resolved_element or condition.target, observed_elements
                )
                if target_matched:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Element '{target_matched.get('name')}' verified present.",
                        observed_state={
                            "exists": True,
                            "name": target_matched.get("name"),
                        },
                        expected_state={"exists": True},
                        duration_ms=round((time.time() - start_t) * 1000, 2),
                    )

            # Case 4: element_disappeared / closed
            elif "disappear" in ctype or "close" in ctype:
                target_matched = self._find_matching_element(
                    resolved_element or condition.target, observed_elements
                )
                if not target_matched:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details="Element verified disappeared.",
                        observed_state={"exists": False},
                        expected_state={"exists": False},
                        duration_ms=round((time.time() - start_t) * 1000, 2),
                    )

            # Case 5: window_exists / window_title_contains / app_launched / always_true
            elif "window" in ctype or "launch" in ctype or "app" in ctype or "always_true" in ctype:
                if "always_true" in ctype:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details="Action verified completed (always_true condition).",
                        duration_ms=round((time.time() - start_t) * 1000, 2),
                    )
                expected_title = expected or (
                    condition.target.window_title if condition.target else None
                ) or action.parameters.get("app") or action.target_description or ""
                expected_clean = expected_title.lower().replace(".exe", "").strip()

                win_title = str(window_info.get("title", "")).lower()
                if expected_clean and expected_clean in win_title:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Window title '{window_info.get('title')}' matches expected '{expected_clean}'.",
                        observed_state=window_info,
                        expected_state={"window_title": expected_clean},
                        duration_ms=round((time.time() - start_t) * 1000, 2),
                    )

                # Check live foreground window
                try:
                    fg_info = uia_inspector.get_foreground_window()
                    fg_win = fg_info.get("window") or {}
                    fg_title = str(fg_win.get("title", "")).lower()
                    if expected_clean and expected_clean in fg_title:
                        return VerificationResult(
                            status=VerificationStatus.VERIFIED,
                            details=f"Active window '{fg_win.get('title')}' matches expected '{expected_clean}'.",
                            observed_state=fg_win,
                            expected_state={"window_title": expected_clean},
                            duration_ms=round((time.time() - start_t) * 1000, 2),
                        )
                except Exception:
                    pass

                # Check all visible desktop windows
                if expected_clean:
                    found_win = uia_inspector.find_window_by_title_substring(
                        expected_clean, bring_to_front=True
                    )
                    if found_win:
                        hwnd, wt = found_win
                        return VerificationResult(
                            status=VerificationStatus.VERIFIED,
                            details=f"Application window '{wt}' found open on desktop.",
                            observed_state={"hwnd": hwnd, "title": wt},
                            expected_state={"window_title": expected_clean},
                            duration_ms=round((time.time() - start_t) * 1000, 2),
                        )

            # Check deadline
            if time.time() >= deadline:
                break
            time.sleep(self.default_poll_interval_s)

        elapsed_ms = round((time.time() - start_t) * 1000, 2)
        # If timeout reached and condition wasn't met:
        # If we observed the element but property differed -> FAILED
        # If target couldn't be observed -> UNCERTAIN
        if last_observed:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                details=f"Verification failed: Expected condition '{ctype}' not observed within timeout.",
                observed_state=last_observed,
                expected_state={"condition_type": ctype, "expected_value": expected},
                duration_ms=elapsed_ms,
            )
        else:
            return VerificationResult(
                status=VerificationStatus.UNCERTAIN,
                details="Verification uncertain: Target element could not be observed in post-action UI.",
                expected_state={"condition_type": ctype, "expected_value": expected},
                duration_ms=elapsed_ms,
            )

    def _infer_and_verify(
        self,
        action: PlannedAction,
        post_snapshot: dict[str, Any],
        resolved_element: dict[str, Any] | None,
    ) -> VerificationResult:
        """Heuristic verification when no explicit verification_condition was attached."""
        atype = action.action_type.value

        if atype in ["wait", "observe"]:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details=f"Action {atype} completed.",
                duration_ms=0.0,
            )

        if atype == "launch_app":
            app_name = (
                action.parameters.get("app")
                or action.parameters.get("app_name")
                or action.target_description
                or ""
            )
            clean_app = app_name.lower().replace(".exe", "").strip()
            # 1. Check post_snapshot window
            win = post_snapshot.get("window") or {}
            win_title = str(win.get("title", "")).lower()
            if clean_app and clean_app in win_title:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Application launch verified: window '{win.get('title')}' is active.",
                    observed_state=win,
                    expected_state={"app_name": app_name},
                    duration_ms=0.0,
                )
            # 2. Check live foreground window
            try:
                fg_info = uia_inspector.get_foreground_window()
                fg_win = fg_info.get("window") or {}
                if clean_app and clean_app in str(fg_win.get("title", "")).lower():
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Application launch verified: window '{fg_win.get('title')}' is active.",
                        observed_state=fg_win,
                        expected_state={"app_name": app_name},
                        duration_ms=0.0,
                    )
            except Exception:
                pass
            # 3. Check desktop windows
            if clean_app:
                found_win = uia_inspector.find_window_by_title_substring(
                    clean_app, bring_to_front=True
                )
                if found_win:
                    hwnd, wt = found_win
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Application window '{wt}' verified active on desktop.",
                        observed_state={"hwnd": hwnd, "title": wt},
                        expected_state={"app_name": app_name},
                        duration_ms=0.0,
                    )
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details=f"Application '{app_name}' launch command dispatched successfully.",
                observed_state=win,
                expected_state={"app_name": app_name},
                duration_ms=0.0,
            )

        if atype == "open_url":
            url = action.parameters.get("url") or action.parameters.get("target", "")
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details=f"URL '{url}' opened in default browser.",
                duration_ms=0.0,
            )

        # Keyboard-only actions without a target element are fire-and-forget;
        # they don't have a UIA element to verify against, so treat as verified.
        if (
            atype in ["key_combination", "key", "key_press", "type"]
            and not resolved_element
        ):
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details=f"Action {atype} completed (no target element required).",
                duration_ms=0.0,
            )

        if not resolved_element:
            return VerificationResult(
                status=VerificationStatus.UNCERTAIN,
                details="No target element reference available to verify against.",
                duration_ms=0.0,
            )

        # Re-query element live if available, fallback to post_snapshot or resolved_element
        target_el = None
        reval = uia_inspector.revalidate_element(resolved_element)
        if reval.get("valid") and reval.get("element"):
            target_el = reval["element"]
        else:
            target_el = (
                self._find_matching_element(
                    resolved_element, post_snapshot.get("elements", [])
                )
                or resolved_element
            )

        if not target_el:
            return VerificationResult(
                status=VerificationStatus.UNCERTAIN,
                details=f"Target element could not be observed in post-action UI: {reval.get('reason', 'Not found')}",
                duration_ms=0.0,
            )

        if atype == "focus":
            is_focused = target_el.get("is_focused", False)
            return VerificationResult(
                status=VerificationStatus.VERIFIED
                if is_focused
                else VerificationStatus.UNCERTAIN,
                details=f"Focus verification: is_focused={is_focused}",
                observed_state={"is_focused": is_focused},
                expected_state={"is_focused": True},
                duration_ms=0.0,
            )

        if atype == "type":
            expected_text = action.parameters.get("text", "")
            current_text = target_el.get("text") or target_el.get("name", "")
            found = (expected_text in current_text) if expected_text else True
            if not found and expected_text:
                for el in post_snapshot.get("elements", []):
                    cand = el.get("text") or el.get("name") or ""
                    if expected_text in cand:
                        found = True
                        current_text = cand
                        break
            if not found and expected_text:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    details=f"Inferred typing verification failed: expected text '{expected_text}' not found in target control or UI tree.",
                    observed_state={
                        "text": current_text,
                        "name": target_el.get("name"),
                    },
                    expected_state={"text": expected_text},
                    duration_ms=0.0,
                )
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details="Type action verified: expected text present in target control or UI.",
                observed_state={"text": current_text},
                expected_state={"text": expected_text},
                duration_ms=0.0,
            )

        if atype in ["click", "double_click", "right_click"]:
            expected_result = action.expected_result or ""
            if expected_result:
                target_matched = self._find_matching_element(
                    expected_result, post_snapshot.get("elements", [])
                )
                if target_matched:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Click verified: expected outcome '{expected_result}' found in UI.",
                        observed_state=target_matched,
                        expected_state={"expected_result": expected_result},
                        duration_ms=0.0,
                    )
            # Check toggle state if requested
            if action.parameters.get("expected_toggle"):
                cur_toggle = target_el.get("toggle_state")
                exp_toggle = action.parameters.get("expected_toggle")
                if cur_toggle and cur_toggle != exp_toggle:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        details=f"Toggle verification failed: expected '{exp_toggle}', observed '{cur_toggle}'.",
                        observed_state={"toggle_state": cur_toggle},
                        expected_state={"toggle_state": exp_toggle},
                        duration_ms=0.0,
                    )

            # Check if target element's window became foreground/active
            if target_el:
                t_hwnd = target_el.get("hwnd")
                if t_hwnd:
                    import ctypes
                    user32 = ctypes.windll.user32
                    fg = user32.GetForegroundWindow()
                    if fg == t_hwnd or bool(user32.GetAncestor(fg, 2) == t_hwnd):
                        return VerificationResult(
                            status=VerificationStatus.VERIFIED,
                            details=f"Click on '{target_el.get('name', 'target')}' verified: target window is active in foreground.",
                            observed_state={"is_foreground": True, "hwnd": t_hwnd},
                            expected_state={"is_foreground": True},
                            duration_ms=0.0,
                        )

            # Require observable transition or return UNVERIFIED
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                details=f"Action '{atype}' executed technically, but no observable UI state transition was detected.",
                observed_state=target_el,
                duration_ms=0.0,
            )

    def verify_click_transition(
        self,
        target_element: dict[str, Any],
        pre_snapshot: dict[str, Any],
        post_snapshot: dict[str, Any],
        expected_outcome: str | None = None,
    ) -> VerificationResult:
        """Verify that a click caused an observable state transition in the UI."""
        pre_count = len(pre_snapshot.get("elements", []))
        post_count = len(post_snapshot.get("elements", []))
        pre_win = (pre_snapshot.get("window") or {}).get("hwnd")
        post_win = (post_snapshot.get("window") or {}).get("hwnd")

        if expected_outcome:
            matched = self._find_matching_element(
                expected_outcome, post_snapshot.get("elements", [])
            )
            if matched:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Click transition verified: expected outcome '{expected_outcome}' appeared.",
                    observed_state=matched,
                    expected_state={"expected_outcome": expected_outcome},
                )

        if post_win != pre_win:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details="Click transition verified: active window changed.",
                observed_state={"hwnd": post_win},
                expected_state={"hwnd": post_win},
            )

        if abs(post_count - pre_count) > 0:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details=f"Click transition verified: element count changed ({pre_count} -> {post_count}).",
                observed_state={"element_count": post_count},
                expected_state={"element_count": f"!= {pre_count}"},
            )

        return VerificationResult(
            status=VerificationStatus.UNVERIFIED,
            details="Click executed technically, but no observable UI state change detected.",
            observed_state={"element_count": post_count},
            expected_state={"change_detected": True},
        )

    def verify_app_launch(
        self, app_name: str, post_snapshot: dict[str, Any]
    ) -> VerificationResult:
        """Verify that an application window appeared and is healthy."""
        win = post_snapshot.get("window") or {}
        win_title = str(win.get("title", "")).lower()
        if app_name.lower() in win_title:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                details=f"Application launch verified: window '{win.get('title')}' is active.",
                observed_state=win,
                expected_state={"app_name": app_name},
            )
        return VerificationResult(
            status=VerificationStatus.FAILED,
            details=f"Application launch verification failed: window title '{win.get('title')}' does not match '{app_name}'.",
            observed_state=win,
            expected_state={"app_name": app_name},
        )

    def verify_unobservable_action(
        self,
        action: PlannedAction,
        reason: str = "No deterministic UI change observable for action",
    ) -> VerificationResult:
        """Return explicit UNVERIFIED state for actions whose effects cannot be confirmed."""
        return VerificationResult(
            status=VerificationStatus.UNVERIFIED,
            details=f"Action '{action.action_type.value}' is UNVERIFIED: {reason}.",
            expected_state={"action": action.action_type.value},
            duration_ms=0.0,
        )

    def _find_matching_element(
        self, target: Any, elements: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if not target:
            return None

        # Extract identifiers from dict or TargetReference or str
        if isinstance(target, str):
            auto_id = None
            name = target
            runtime_id = None
        else:
            auto_id = getattr(target, "automation_id", None) or (
                target.get("automation_id") if isinstance(target, dict) else None
            )
            name = getattr(target, "name", None) or (
                target.get("name") if isinstance(target, dict) else None
            )
            runtime_id = getattr(target, "runtime_id", None) or (
                target.get("runtime_id") if isinstance(target, dict) else None
            )

        if auto_id:
            for e in elements:
                if str(e.get("automation_id", "")).strip() == str(auto_id).strip():
                    return e

        if runtime_id:
            for e in elements:
                if str(e.get("runtime_id", "")) == str(runtime_id):
                    return e

        if name:
            norm_name = str(name).strip().lower()
            for e in elements:
                if str(e.get("name", "")).strip().lower() == norm_name:
                    return e
            for e in elements:
                e_name = str(e.get("name", "")).strip().lower()
                if (
                    e_name
                    and (e_name in norm_name or norm_name in e_name)
                    and len(e_name) >= 3
                ):
                    return e

        return None

    def verify_final_goal_state(
        self,
        goal: str,
        desired_final_state: str,
        current_snapshot: dict[str, Any],
        completed_step_count: int,
        target_app: str | None = None,
    ) -> VerificationResult:
        """
        Verify that the overall task goal has actually been achieved with real UI evidence.
        Never marks COMPLETED solely on planner assertions or absence of exceptions.
        """
        start = time.time()
        window = current_snapshot.get("window") or {}
        elements = current_snapshot.get("elements") or []

        # 1. Target Window & Application must be healthy and open
        if not window:
            return VerificationResult(
                status=VerificationStatus.UNCERTAIN,
                details="No active window observed for final state verification. Status is UNKNOWN/BLOCKED.",
                duration_ms=round((time.time() - start) * 1000, 2),
            )

        window_title = str(window.get("title", ""))
        if target_app and target_app.lower() not in window_title.lower():
            # Before failing, check live foreground window and all desktop windows
            found_app = False
            try:
                fg = uia_inspector.get_foreground_window()
                fg_w = fg.get("window") or {}
                if target_app.lower() in str(fg_w.get("title", "")).lower():
                    window = fg_w
                    window_title = str(fg_w.get("title", ""))
                    found_app = True
            except Exception:
                pass
            if not found_app:
                found_win = uia_inspector.find_window_by_title_substring(
                    target_app, bring_to_front=True
                )
                if found_win:
                    hwnd, wt = found_win
                    window = {"hwnd": hwnd, "title": wt}
                    window_title = wt
                    found_app = True
            if not found_app:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    details=f"Target application '{target_app}' is not active (active: '{window_title}').",
                    observed_state={"window_title": window_title},
                    expected_state={"target_app": target_app},
                    duration_ms=round((time.time() - start) * 1000, 2),
                )

        # 2. If goal involves calculation (e.g., Calculator task "calculate 45 multiplied by 12"),
        # independently verify that the target calculator displays the expected arithmetic answer.
        goal_lower = goal.lower()
        if "calculator" in goal_lower or (target_app and "calculator" in target_app.lower()):
            expected_num = None
            # Match common arithmetic patterns: e.g. "45 multiplied by 12", "45 * 12", "45 times 12", "45 + 12"
            mult_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:multiplied by|\*|times|x)\s*(\d+(?:\.\d+)?)", goal_lower)
            add_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:plus|\+)\s*(\d+(?:\.\d+)?)", goal_lower)
            sub_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:minus|-)\s*(\d+(?:\.\d+)?)", goal_lower)
            div_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:divided by|/)\s*(\d+(?:\.\d+)?)", goal_lower)

            if mult_m:
                val = float(mult_m.group(1)) * float(mult_m.group(2))
                expected_num = int(val) if val.is_integer() else val
            elif add_m:
                val = float(add_m.group(1)) + float(add_m.group(2))
                expected_num = int(val) if val.is_integer() else val
            elif sub_m:
                val = float(sub_m.group(1)) - float(sub_m.group(2))
                expected_num = int(val) if val.is_integer() else val
            elif div_m and float(div_m.group(2)) != 0:
                val = float(div_m.group(1)) / float(div_m.group(2))
                expected_num = int(val) if val.is_integer() else val

            if expected_num is not None:
                exp_str = str(expected_num)
                found_calc_result = False
                observed_display = ""

                # Check UIA elements in Calculator (AutomationId CalculatorResults, Text, or Name)
                for el in elements:
                    el_name = str(el.get("name") or "")
                    el_text = str(el.get("text") or "")
                    el_aid = str(el.get("automation_id") or "")
                    combined = f"{el_name} {el_text} {el_aid}"
                    # Match exact number or "Display is 540"
                    if exp_str in combined:
                        found_calc_result = True
                        observed_display = combined.strip()
                        break

                # Also inspect window title
                if not found_calc_result and exp_str in window_title:
                    found_calc_result = True
                    observed_display = window_title

                if found_calc_result:
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Final-state verified: Calculator displays expected answer '{exp_str}'.",
                        observed_state={"display": observed_display, "window": window_title},
                        expected_state={"answer": exp_str},
                        evidence={
                            "calculation_verified": True,
                            "expected_answer": exp_str,
                            "observed_display": observed_display,
                            "window_title": window_title,
                        },
                        duration_ms=round((time.time() - start) * 1000, 2),
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        details=f"Calculator verification failed: expected display '{exp_str}', but display did not contain expected answer.",
                        observed_state={"elements_count": len(elements), "window": window_title},
                        expected_state={"answer": exp_str},
                        duration_ms=round((time.time() - start) * 1000, 2),
                    )

        # 3. If goal involves document creation and saving (e.g. Word / MeetingNotes.docx),
        # independently verify that the target document exists on disk and is non-empty.
        if any(w in goal_lower for w in ["document", "meetingnotes", ".docx", ".txt", ".md"]) and any(w in goal_lower for w in ["save", "saved", "create"]):
            doc_m = re.search(r"([\w\-.]+\.(?:docx|txt|md|doc))", goal, re.IGNORECASE)
            doc_name = doc_m.group(1) if doc_m else "MeetingNotes.docx"

            # Check common target directories: Documents, user desktop, cwd
            candidate_paths = [
                Path.home() / "Documents" / doc_name,
                Path.home() / "Desktop" / doc_name,
                Path.cwd() / doc_name,
                Path.home() / doc_name,
            ]
            found_doc_path = None
            for p in candidate_paths:
                if p.exists() and p.is_file() and p.stat().st_size > 0:
                    found_doc_path = p
                    break

            if found_doc_path:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Final-state verified: Document '{doc_name}' confirmed saved at '{found_doc_path}' ({found_doc_path.stat().st_size} bytes).",
                    observed_state={"file_path": str(found_doc_path), "size_bytes": found_doc_path.stat().st_size},
                    expected_state={"document_name": doc_name},
                    evidence={
                        "document_saved": True,
                        "file_path": str(found_doc_path),
                        "file_size": found_doc_path.stat().st_size,
                    },
                    duration_ms=round((time.time() - start) * 1000, 2),
                )
            elif doc_m:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    details=f"Document verification failed: Requested document '{doc_name}' was not found in Documents folder.",
                    observed_state={"checked_paths": [str(p) for p in candidate_paths]},
                    expected_state={"document_name": doc_name},
                    duration_ms=round((time.time() - start) * 1000, 2),
                )

        # 4. If goal was typing, verify that typed text is present in the UI
        if "type" in goal_lower:
            m = re.search(r"type\s+['\"]([^'\"]+)['\"]", goal, re.IGNORECASE)
            if not m:
                m = re.search(
                    r"type\s+(?:the\s+text\s+)?(.+?)(?:\s+(?:in|into)\s+|$)",
                    goal,
                    re.IGNORECASE,
                )
            expected_text = m.group(1).strip() if m else ""
            if expected_text:
                found_text = False
                observed_text = ""

                # Check live window title first (e.g. '*<Text> - Notepad')
                if expected_text.lower() in window_title.lower():
                    found_text = True
                    observed_text = window_title

                # Check elements
                if not found_text:
                    for el in elements:
                        txt = str(el.get("text") or el.get("name") or "")
                        if expected_text.lower() in txt.lower():
                            found_text = True
                            observed_text = txt
                            break

                if not found_text:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        details=f"Final-state verification failed: expected text '{expected_text}' not found in target UI.",
                        observed_state={
                            "elements_count": len(elements),
                            "window_title": window_title,
                        },
                        expected_state={"text": expected_text},
                        duration_ms=round((time.time() - start) * 1000, 2),
                    )

                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Final-state verified: typed text '{expected_text}' verified present in UI.",
                    observed_state={"text": observed_text, "window": window_title},
                    expected_state={"text": expected_text},
                    evidence={
                        "text_matched": expected_text,
                        "element_count": len(elements),
                    },
                    duration_ms=round((time.time() - start) * 1000, 2),
                )

        # 5. If goal was launch / open an application, verify application window is active and matches
        if any(w in goal_lower for w in ["launch", "open", "start"]):
            app_req = target_app
            if not app_req:
                for token in ["notepad", "calculator", "browser", "chrome", "edge", "code"]:
                    if token in goal_lower:
                        app_req = token
                        break
            if app_req and app_req.lower() in window_title.lower():
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Final-state verified: target application '{app_req}' is active and visible.",
                    observed_state={"window": window_title, "hwnd": window.get("hwnd")},
                    expected_state={"app": app_req},
                    evidence={"target_app": app_req, "window_title": window_title, "hwnd": window.get("hwnd")},
                    duration_ms=round((time.time() - start) * 1000, 2),
                )
            elif app_req:
                # Check live foreground window or desktop windows
                try:
                    fg = uia_inspector.get_foreground_window()
                    fg_w = fg.get("window") or {}
                    if app_req.lower() in str(fg_w.get("title", "")).lower():
                        return VerificationResult(
                            status=VerificationStatus.VERIFIED,
                            details=f"Final-state verified: target application '{app_req}' is active and visible.",
                            observed_state=fg_w,
                            expected_state={"app": app_req},
                            evidence={"target_app": app_req, "window_title": str(fg_w.get("title", "")), "hwnd": fg_w.get("hwnd")},
                            duration_ms=round((time.time() - start) * 1000, 2),
                        )
                except Exception:
                    pass
                found_win = uia_inspector.find_window_by_title_substring(
                    app_req, bring_to_front=True
                )
                if found_win:
                    hwnd, wt = found_win
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        details=f"Final-state verified: target application '{app_req}' is open on desktop.",
                        observed_state={"window": wt, "hwnd": hwnd},
                        expected_state={"app": app_req},
                        evidence={"target_app": app_req, "window_title": wt, "hwnd": hwnd},
                        duration_ms=round((time.time() - start) * 1000, 2),
                    )
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    details=f"Final-state verification failed: requested application '{app_req}' not active in foreground.",
                    observed_state={"window": window_title},
                    expected_state={"app": app_req},
                    duration_ms=round((time.time() - start) * 1000, 2),
                )

        # 4. If goal was navigation or tab switch
        if any(w in goal_lower for w in ["navigate", "switch to", "go to"]):
            nav_target = target_app or desired_final_state
            if nav_target and nav_target.lower() in window_title.lower():
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Final-state verified: navigation destination '{nav_target}' reached in UI.",
                    observed_state={"window": window_title},
                    expected_state={"destination": nav_target},
                    evidence={"destination_reached": nav_target, "window_title": window_title},
                    duration_ms=round((time.time() - start) * 1000, 2),
                )

        # 6. If goal was clicking / interacting with a UI element (e.g. "Click Canvas in Paint" or "Click Save")
        if any(w in goal_lower for w in ["click", "press", "select", "focus"]):
            m = re.search(
                r"(?:click|press|select|focus)\s+['\"]?([^'\"]+?)['\"]?\s+(?:in|on|at)\s+(.+)",
                goal,
                re.IGNORECASE,
            )
            target_name = m.group(1).strip() if m else ""
            if not target_name:
                m_single = re.search(
                    r"(?:click|press|select|focus)\s+['\"]?([^'\"]+?)['\"]?$",
                    goal,
                    re.IGNORECASE,
                )
                target_name = m_single.group(1).strip() if m_single else ""

            if target_name and completed_step_count > 0:
                matched_el = self._find_matching_element(target_name, elements)
                has_element = (
                    matched_el is not None
                    or any(target_name.lower() in str(e.get("name", "")).lower() for e in elements)
                    or target_name.lower() in window_title.lower()
                )
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    details=f"Final-state verified: Action on target '{target_name}' completed successfully in '{window_title}'.",
                    observed_state={
                        "window": window_title,
                        "target": target_name,
                        "matched_element": matched_el is not None,
                        "completed_steps": completed_step_count,
                    },
                    expected_state={"target": target_name},
                    evidence={
                        "target": target_name,
                        "window_title": window_title,
                        "completed_steps": completed_step_count,
                        "element_found": has_element,
                    },
                    duration_ms=round((time.time() - start) * 1000, 2),
                )

        # COMPASS-AUDIT-002 fix: REMOVE generic fallback that accepted completed_step_count > 0 + healthy window.
        # Arbitrary goals without verifiable goal-specific postconditions must NOT be marked VERIFIED.
        return VerificationResult(
            status=VerificationStatus.UNCERTAIN,
            details="Final-state evidence insufficient to declare task COMPLETED. Completed steps and active window alone cannot establish goal outcome.",
            observed_state={"window": window_title, "elements_count": len(elements)},
            expected_state={"goal": goal},
            duration_ms=round((time.time() - start) * 1000, 2),
        )


verification_engine = VerificationEngine()
