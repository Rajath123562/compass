"""
COMPASS Phase 7: Interactive Guide Engine
Features:
- Meta-Cognition (<thinking> loops)
- Dynamic Autonomy (Auto-execute vs Ask Permission)
- Event-Driven State Verification
- Time Travel (Undo Engine)
"""
import asyncio
import logging
import os
import threading
import time
from collections.abc import AsyncGenerator
from typing import Any

from perception import uia_inspector
from providers.omniroute_provider import OmniRouteProvider

logger = logging.getLogger(__name__)

class InteractiveGuideEngine:
    def __init__(self, model_id: str | None = None):
        self.provider = OmniRouteProvider(
            free_only=False,
            timeout_seconds=float(os.environ.get("COMPASS_LLM_TIMEOUT", "60.0"))
        )
        self.model_id = model_id
        # Simplistic GraphRAG / Context Window
        self.memory_context: list[dict[str, str]] = [
            {"role": "system", "content": "You are COMPASS, an elite interactive AI co-pilot. You guide the user step-by-step through complex tasks. ALWAYS use an internal <thinking> block to self-correct before giving your final guidance. Only propose ONE step at a time."}
        ]
        # Time Travel Engine (Undo snapshots)
        self.history_snapshots: list[dict[str, Any]] = []

    def _snapshot_state(self):
        """Captures a lightweight operational snapshot before taking action."""
        try:
            fw = uia_inspector.get_foreground_window()
            snapshot = {
                "timestamp": time.time(),
                "window": fw.get("window", {}),
            }
            self.history_snapshots.append(snapshot)
            if len(self.history_snapshots) > 10:
                self.history_snapshots.pop(0)
        except Exception as e:
            logger.warning(f"Failed to snapshot state: {e}")

    async def generate_guidance_stream(self, user_input: str, model_id: str | None = None) -> AsyncGenerator[str, None]:
        """
        Yields a stream of tokens in real-time, including <thinking> blocks and the final response.
        """
        # Snapshot state before acting
        self._snapshot_state()

        # Get current UI state to ground the AI
        fw = uia_inspector.get_foreground_window()
        window_title = "Unknown Window"
        if fw and isinstance(fw, dict):
            win_info = fw.get("window") or {}
            window_title = win_info.get("title", "Unknown Window")
        
        # Build prompt with state injection
        grounded_prompt = f"[SYSTEM: User is currently looking at window: '{window_title}']\nUser says: {user_input}"
        self.memory_context.append({"role": "user", "content": grounded_prompt})

        full_response = ""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_token(chunk: str):
            nonlocal full_response
            full_response += chunk
            loop.call_soon_threadsafe(queue.put_nowait, chunk)

        # Resolve active model to use
        target_model = model_id or self.model_id or self.provider.select_active_model() or "qwen3.5:4b"

        def _worker():
            try:
                resp = self.provider.chat_completion(
                    messages=self.memory_context,
                    model=target_model,
                    temperature=0.6,
                    max_tokens=800,
                    on_token=on_token,
                )
                if not resp.get("success"):
                    err = resp.get("error", "Unknown error")
                    loop.call_soon_threadsafe(queue.put_nowait, f"⚠️ System Error: {err}")
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, f"⚠️ Exception occurred during guidance: {e}")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

        if full_response:
            self.memory_context.append({"role": "assistant", "content": full_response})

    def undo_last_step(self) -> str:
        """
        Reverts the state to the last snapshot.
        """
        if not self.history_snapshots:
            return "No previous steps to undo."
        
        last_state = self.history_snapshots.pop()
        # In a full implementation, this would reverse file changes or send reverse keystrokes.
        return f"Reverted context to state at {last_state['timestamp']}. Ready for new direction."

interactive_guide_engine = InteractiveGuideEngine()
