"""participant_module/adapter.py — the team's AssessmentModule (SPEC-09).

Current behaviour: an always-abstaining module that is contract-valid for any case and any
checklist, so the server accepts it with no INVALID_OUTPUT. The scaffolding for a real
assessment is already wired in:

  * result construction and local enforcement — `participant_module/output.py` (Task 14);
  * a time budget guard that returns before the 180 s limit — `participant_module/budget.py`
    (Task 15).

Later tasks replace `_assess_case` with real retrieval (Task 10), a criterion judge
(Task 11), a quote extractor (Task 12) and TRL logic (Task 13); everything they produce goes
through `output.build_result`, which keeps the output contract-valid.

Entry point: participant_module.adapter:AssessmentModule

Design notes for whoever extends this:
  * Criterion IDs come only from `load()`'s checklist. Never hard-code the DEMO IDs; the
    official checklist uses different ones.
  * Build every result with `output.build_result` / `output.abstained` — do not assemble the
    dict by hand, so the contract rules stay in one place.
  * Check `guard.exhausted()` / `guard.have_ms(...)` before any expensive step and abstain
    rather than risk a TIMEOUT.
"""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participant_module import budget, output


class AssessmentModule:
    def __init__(self) -> None:
        self._checklist_version: str = ""
        self._criterion_ids: list[str] = []
        self._settings: Mapping[str, Any] = {}

    def load(self, config: Mapping[str, Any], asset_root: Path) -> None:
        """Read the checklist and settings. Load rules/weights from `asset_root` here.

        The checklist is the only source of criterion IDs (DATA_CONTRACT §1.4). Nothing is
        downloaded; `asset_root` is treated as read-only.
        """
        checklist = config["checklist"]
        self._checklist_version = checklist["version"]
        self._criterion_ids = [c["criterion_id"] for c in checklist["criteria"]]
        self._settings = config.get("module", {}).get("settings", {})

    def assess(self, case: Mapping[str, Any], context: Any) -> dict[str, Any]:
        """Assess one case. Never raises on a normal case: any unexpected error becomes a
        clean `failed` result, and running out of time becomes an abstained result."""
        return output.safe_result(
            lambda: self._assess_case(case, context),
            case,
            self._checklist_version,
            error_code="TEAM_MODULE_ASSESS_ERROR",
            on_error=lambda exc: traceback.print_exc(),
        )

    def _assess_case(self, case: Mapping[str, Any], context: Any) -> dict[str, Any]:
        guard = budget.TimeGuard(context)
        try:
            # --- real assessment goes here (Tasks 10-13) ---------------------
            # Build per-criterion decisions, guarding each expensive step, e.g.:
            #     guard.checkpoint("retrieval")
            #     decisions = judge(retrieve(case, self._criterion_ids), ...)
            #     return output.build_result(case, self._checklist_version,
            #                                self._criterion_ids, status=..., ...)
            # Until then, abstain on every criterion.
            guard.checkpoint("assess-start")
            return output.abstained(case, self._checklist_version, self._criterion_ids)
        except budget.BudgetExceeded:
            # Prefer a scientific abstention over a server-side TIMEOUT.
            return output.abstained(
                case,
                self._checklist_version,
                self._criterion_ids,
                reason="insufficient evidence",
                missing_note="Assessment stopped before the time limit; no judgment was reached.",
            )

    def reset_case(self) -> None:
        """No per-case state is kept; each case runs in a fresh cold process."""

    def close(self) -> None:
        """Nothing to release in the skeleton."""
