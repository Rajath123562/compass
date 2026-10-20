"""
COMPASS Smart Token Budget Manager
Monitors API token usage, tracks costs, enforces daily limits,
and warns before reaching free tier limits.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.logging_config import logger


# Pricing table per 1M tokens ($0 for Free tier, nominal for paid Tier 1)
PRICING_PER_MILLION = {
    "gemini-3.8-flash": {"input": 0.75, "output": 3.00, "free_tier": True},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30, "free_tier": True},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "free_tier": True},
    "gemini-3.8-flash-tts": {"input": 0.0, "output": 0.0, "free_tier": True},
}


@dataclass
class UsageRecord:
    timestamp: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    estimated_cost_usd: float = 0.0


class TokenBudgetManager:
    """Thread-safe token usage governor and budget tracking."""

    def __init__(
        self,
        daily_token_limit: int = 1_000_000,
        daily_request_limit: int = 1500,
        warning_threshold_ratio: float = 0.80,
    ) -> None:
        self.daily_token_limit = daily_token_limit
        self.daily_request_limit = daily_request_limit
        self.warning_threshold_ratio = warning_threshold_ratio

        self._lock = threading.Lock()
        self._records: list[UsageRecord] = []
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_cached_tokens: int = 0
        self._total_estimated_cost_usd: float = 0.0

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        """
        Record a token consumption event. Returns estimated cost in USD.
        """
        pricing = PRICING_PER_MILLION.get(
            model, {"input": 0.0, "output": 0.0, "free_tier": True}
        )
        # Cost is 0 if on free tier
        cost = 0.0
        if not pricing.get("free_tier", False):
            cost = (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000.0

        record = UsageRecord(
            timestamp=time.time(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            estimated_cost_usd=cost,
        )

        with self._lock:
            self._records.append(record)
            self._total_prompt_tokens += prompt_tokens
            self._total_completion_tokens += completion_tokens
            self._total_cached_tokens += cached_tokens
            self._total_estimated_cost_usd += cost

            total_tokens = self._total_prompt_tokens + self._total_completion_tokens
            if total_tokens >= (self.daily_token_limit * self.warning_threshold_ratio):
                logger.warning(
                    f"Token Budget Warning: Used {total_tokens:,} tokens "
                    f"({(total_tokens / self.daily_token_limit) * 100:.1f}% of daily limit)"
                )

        return cost

    def can_execute(self) -> tuple[bool, str | None]:
        """Verify if current usage is within daily safety thresholds."""
        with self._lock:
            total_tokens = self._total_prompt_tokens + self._total_completion_tokens
            if total_tokens >= self.daily_token_limit:
                return (
                    False,
                    f"Daily token budget exceeded: {total_tokens:,}/{self.daily_token_limit:,} tokens used.",
                )

            if len(self._records) >= self.daily_request_limit:
                return (
                    False,
                    f"Daily request limit exceeded: {len(self._records)}/{self.daily_request_limit} requests.",
                )

        return True, None

    def get_metrics(self) -> dict[str, Any]:
        """Return usage telemetry snapshot."""
        with self._lock:
            total_tokens = self._total_prompt_tokens + self._total_completion_tokens
            usage_ratio = (
                total_tokens / self.daily_token_limit
                if self.daily_token_limit > 0
                else 0.0
            )
            return {
                "total_requests": len(self._records),
                "total_prompt_tokens": self._total_prompt_tokens,
                "total_completion_tokens": self._total_completion_tokens,
                "total_tokens": total_tokens,
                "total_cached_tokens": self._total_cached_tokens,
                "total_estimated_cost_usd": round(self._total_estimated_cost_usd, 4),
                "daily_token_limit": self.daily_token_limit,
                "remaining_daily_tokens": max(0, self.daily_token_limit - total_tokens),
                "usage_ratio": round(usage_ratio, 4),
                "is_warning_level": usage_ratio >= self.warning_threshold_ratio,
            }

    def get_summary(self) -> dict[str, Any]:
        """Alias for get_metrics."""
        return self.get_metrics()

    def reset(self) -> None:
        """Reset budget counters (e.g. for new day or testing)."""
        with self._lock:
            self._records.clear()
            self._total_prompt_tokens = 0
            self._total_completion_tokens = 0
            self._total_cached_tokens = 0
            self._total_estimated_cost_usd = 0.0


# Global singleton instance
_budget_instance: TokenBudgetManager | None = None
_budget_lock = threading.Lock()


def get_token_budget_manager() -> TokenBudgetManager:
    global _budget_instance
    if _budget_instance is None:
        with _budget_lock:
            if _budget_instance is None:
                _budget_instance = TokenBudgetManager()
    return _budget_instance
