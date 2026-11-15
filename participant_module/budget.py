from __future__ import annotations

import time
from typing import Any

DEFAULT_SAFETY_MS = 15_000.0


class BudgetExceeded(RuntimeError):

    def __init__(self, label: str, remaining_ms: float) -> None:
        super().__init__(f"time budget exhausted at {label!r}: {remaining_ms:.0f} ms left")
        self.label = label
        self.remaining_ms = remaining_ms


class TimeGuard:

    def __init__(self, context: Any, *, safety_ms: float = DEFAULT_SAFETY_MS) -> None:
        self._context = context
        self._safety_ms = max(0.0, float(safety_ms))
        self._start = time.monotonic()
        budget = getattr(context, "time_budget_ms", None)
        self._fallback_budget_ms = float(budget) if isinstance(budget, (int, float)) else None

    def remaining_ms(self) -> float:
        remaining = getattr(self._context, "remaining_ms", None)
        if callable(remaining):
            try:
                return float(remaining())
            except Exception:
                pass
        if self._fallback_budget_ms is not None:
            elapsed_ms = (time.monotonic() - self._start) * 1000.0
            return self._fallback_budget_ms - elapsed_ms
        return float("inf")

    def exhausted(self) -> bool:
        return self.remaining_ms() <= self._safety_ms

    def have_ms(self, needed_ms: float) -> bool:
        return self.remaining_ms() - self._safety_ms >= float(needed_ms)

    def checkpoint(self, label: str) -> None:
        remaining = self.remaining_ms()
        if remaining <= self._safety_ms:
            raise BudgetExceeded(label, remaining)
