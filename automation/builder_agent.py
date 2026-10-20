"""
COMPASS Autonomous Builder Agent
Equipped with workspace file operations and sandboxed terminal management.
Executes an autonomous self-healing loop: generates code -> writes files -> runs tests ->
analyzes tracebacks/stderr -> self-heals up to 3 attempts until 100% working.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from automation.terminal_manager import CommandResult, TerminalManager

logger = logging.getLogger(__name__)


class BuilderAgent:
    """Autonomous coding agent with self-healing test-and-repair loop."""

    def __init__(
        self,
        workspace_root: str | Path,
        api_key: str | None = None,
        model_name: str = "gemini-3.8-flash",
        terminal_manager: TerminalManager | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.terminal = terminal_manager or TerminalManager()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        except Exception as e:
            logger.warning("Could not instantiate GenAI client in BuilderAgent: %s", e)
            return None

    # ─── Workspace File Sandbox ───────────────────────────────────────────────

    def _safe_resolve(self, rel_path: str) -> Path:
        """Resolve path ensuring it stays safely within the workspace root."""
        clean_rel = rel_path.lstrip("/\\")
        target = (self.workspace_root / clean_rel).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(f"Access denied: path '{rel_path}' escapes workspace sandbox.")
        return target

    def _invalidate_pycache(self, dest: Path) -> None:
        if dest.suffix == ".py":
            pycache_dir = dest.parent / "__pycache__"
            if pycache_dir.is_dir():
                stem = dest.stem
                for pyc in pycache_dir.glob(f"{stem}*.pyc"):
                    try:
                        pyc.unlink(missing_ok=True)
                    except Exception:
                        pass

    def write_file(self, rel_path: str, content: str) -> dict[str, Any]:
        """Create or overwrite a file within workspace sandbox."""
        dest = self._safe_resolve(rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        self._invalidate_pycache(dest)
        return {"status": "created", "path": str(dest), "bytes": len(content)}

    def read_file(self, rel_path: str) -> str:
        """Read text from a workspace file."""
        dest = self._safe_resolve(rel_path)
        if not dest.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        return dest.read_text(encoding="utf-8")

    def edit_file(self, rel_path: str, find_str: str, replace_str: str) -> dict[str, Any]:
        """Replace target string in an existing workspace file."""
        dest = self._safe_resolve(rel_path)
        if not dest.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        content = dest.read_text(encoding="utf-8")
        if find_str not in content:
            return {"status": "not_found", "path": str(dest), "replaced": False}
        updated = content.replace(find_str, replace_str, 1)
        dest.write_text(updated, encoding="utf-8")
        self._invalidate_pycache(dest)
        return {"status": "updated", "path": str(dest), "replaced": True}

    def run_command(self, cmd: str, timeout_sec: float = 60.0) -> CommandResult:
        """Run terminal command in workspace root."""
        return self.terminal.execute(
            command=cmd,
            cwd=str(self.workspace_root),
            timeout_sec=timeout_sec,
        )

    # ─── Self-Healing Build Loop ──────────────────────────────────────────────

    def build_and_verify(
        self,
        goal: str,
        test_command: str | None = None,
        max_attempts: int = 3,
        mock_generator_fn: Any | None = None,
    ) -> dict[str, Any]:
        """
        Self-healing autonomous loop:
        1. Formulate code/files to achieve goal.
        2. Write files into workspace.
        3. If test_command given, execute and verify.
        4. If failure detected, feed error back into model and repair (up to max_attempts).
        5. Return structured audit report.
        """
        attempts = 0
        modified_files: list[str] = []
        last_result: CommandResult | None = None
        error_history: list[str] = []

        while attempts < max_attempts:
            attempts += 1
            logger.info("Builder Agent attempt %d of %d for goal: %s", attempts, max_attempts, goal)

            # Generate solution (via injected generator or Gemini client)
            repair_context = "\n".join(error_history) if error_history else ""
            actions = self._generate_actions(goal, repair_context, mock_generator_fn)

            # Apply file modifications
            for act in actions:
                action_type = act.get("action")
                if action_type == "write_file":
                    p = act.get("path", "")
                    c = act.get("content", "")
                    self.write_file(p, c)
                    if p not in modified_files:
                        modified_files.append(p)
                elif action_type == "edit_file":
                    p = act.get("path", "")
                    f = act.get("find", "")
                    r = act.get("replace", "")
                    self.edit_file(p, f, r)
                    if p not in modified_files:
                        modified_files.append(p)

            # If no test command requested, job is complete after generating files
            if not test_command:
                return {
                    "status": "success",
                    "attempts": attempts,
                    "modified_files": modified_files,
                    "final_test_result": None,
                }

            # Run verification test
            res = self.run_command(test_command)
            last_result = res

            if res.returncode == 0 and not res.has_error:
                return {
                    "status": "success",
                    "attempts": attempts,
                    "modified_files": modified_files,
                    "final_test_result": res,
                }

            # Failure detected: capture error context for next iteration
            err_msg = (
                f"Attempt {attempts} test failure (Exit code: {res.returncode}, Category: {res.detected_error_category}).\n"
                f"Stderr: {res.stderr}\nStdout: {res.stdout}"
            )
            error_history.append(err_msg)
            logger.warning("Builder attempt %d failed: %s", attempts, res.detected_error_category)

        return {
            "status": "max_retries_exceeded",
            "attempts": attempts,
            "modified_files": modified_files,
            "final_test_result": last_result,
            "error_history": error_history,
        }

    def _generate_actions(
        self,
        goal: str,
        error_context: str,
        mock_fn: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Query Gemini or mock function to obtain structured file write/edit actions."""
        if mock_fn is not None:
            return mock_fn(goal, error_context)

        client = self._get_client()
        if not client:
            return []

        try:
            import json

            prompt = (
                f"Goal: {goal}\n"
                f"Error Context from previous attempt (if any):\n{error_context}\n\n"
                "Provide the necessary files as a JSON array of objects with schema:\n"
                '[{"action": "write_file", "path": "relative/path.py", "content": "file content here"}]\n'
                "Output strictly valid JSON with no conversational prefix or markdown tags."
            )

            resp = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            text = resp.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            parsed = json.loads(text.strip())
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception as e:
            logger.warning("Builder action generation failed: %s", e)
            return []
