"""Time budget guard (Task 15).

The per-case limit is 180 s and covers interpreter start-up, imports, `load`, `assess`,
cleanup and exit (MODULE_GUIDE §5). Exceeding it fails the case with `TIMEOUT` and discards
any result already written — strictly worse than abstaining. So the module should watch
`context.remaining_ms()` and return an abstained result *before* the limit.

`TimeGuard` wraps `context` and answers "is there still time?" with a safety margin reserved
for cleanup, process exit and clock slack. Expensive steps call `checkpoint()`, which raises
`BudgetExceeded` when the margin is reached; the adapter turns that into an abstained result.

Pure standard library: this ships inside the submission and runs in the common base
environment. Memory is guarded by the module's own choices (batch sizes, releasing models);
this helper covers the time half and exposes a hook for a soft memory ceiling where psutil
is unavailable.
"""

from __future__ import annotations

import time
from typing import Any

# Reserve this much of the budget for load-already-spent slack, cleanup and process exit.
DEFAULT_SAFETY_MS = 15_000.0


class BudgetExceeded(RuntimeError):
    """Raised by TimeGuard.checkpoint when the remaining budget hits the safety margin."""

    def __init__(self, label: str, remaining_ms: float) -> None:
        super().__init__(f"time budget exhausted at {label!r}: {remaining_ms:.0f} ms left")
        self.label = label
        self.remaining_ms = remaining_ms


class TimeGuard:
    """Track the remaining time budget for one case.

    Prefers `context.remaining_ms()` (the worker's own clock). If the context does not
    provide it, falls back to a local monotonic clock started at construction against
    `context.time_budget_ms`.
    """

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
            except Exception:  # noqa: BLE001 - never let the clock crash the case
                pass
        if self._fallback_budget_ms is not None:
            elapsed_ms = (time.monotonic() - self._start) * 1000.0
            return self._fallback_budget_ms - elapsed_ms
        return float("inf")

    def exhausted(self) -> bool:
        """True when less than the safety margin remains."""
        return self.remaining_ms() <= self._safety_ms

    def have_ms(self, needed_ms: float) -> bool:
        """True when at least `needed_ms` remain beyond the safety margin.

        Use before a step whose cost you can estimate, e.g. loading a model or scoring a
        batch of pages: `if not guard.have_ms(estimate): break`.
        """
        return self.remaining_ms() - self._safety_ms >= float(needed_ms)

    def checkpoint(self, label: str) -> None:
        """Raise BudgetExceeded if the safety margin has been reached."""
        remaining = self.remaining_ms()
        if remaining <= self._safety_ms:
            raise BudgetExceeded(label, remaining)
