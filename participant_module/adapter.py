"""participant_module/adapter.py — the team's AssessmentModule (SPEC-09).

Reads every page (`pages.py`), judges each checklist criterion with evidence and quotes
(`judge.py`, `retrieval.py`), and decides the TRL (`trl.py`). `output.py` keeps the result
contract-valid and `budget.py` returns before the 180 s limit. Without the model in the store, or
short of time, criteria stay `insufficient evidence` and the TRL logic still runs.

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

import re
import traceback
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from participant_module import budget, judge, output, pages, trl

# Sentence boundary: end punctuation, whitespace, then a capital or digit. Good enough for
# report prose; abbreviations like "Fig. 3" split early, which only costs a weaker sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_NOT_FOUND_NOTE = "No candidate sentence supported this criterion strongly enough."
_NOT_JUDGED_NOTE = "No criterion-level judgement was made: the model was unavailable or time ran short."


def _sentences(text: str) -> Iterator[str]:
    flat = " ".join(text.split())
    for sentence in _SENTENCE_END.split(flat):
        if len(sentence) >= 20:  # drop headers, page numbers, figure labels
            yield sentence


class AssessmentModule:
    def __init__(self) -> None:
        self._checklist_version: str = ""
        self._criterion_ids: list[str] = []
        self._settings: Mapping[str, Any] = {}
        self._criteria: list[Mapping[str, str]] = []
        self._model: judge.Entailment | None = None

    def load(self, config: Mapping[str, Any], asset_root: Path) -> None:
        """Read the checklist and settings. Load rules/weights from `asset_root` here.

        The checklist is the only source of criterion IDs (DATA_CONTRACT §1.4). Nothing is
        downloaded; `asset_root` is treated as read-only.
        """
        checklist = config["checklist"]
        self._checklist_version = checklist["version"]
        self._criteria = list(checklist["criteria"])
        self._criterion_ids = [c["criterion_id"] for c in self._criteria]
        self._settings = config.get("module", {}).get("settings", {})
        try:
            self._model = judge.load_entailment()
        except Exception:  # noqa: BLE001 - judge nothing rather than fail every case
            traceback.print_exc()
            self._model = None

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
            guard.checkpoint("assess-start")
            # Read every document; a broken or encrypted PDF gives no pages, not a failure. Running
            # low on time stops reading and decides on what was read so far.
            records: list[dict[str, Any]] = []
            for document in case.get("documents", []):
                if guard.exhausted():
                    break
                records += pages.read_pages(document, guard.remaining_ms)
            where: dict[str, tuple[str, int]] = {}  # sentence -> (document_id, page)
            for record in records:
                for sentence in _sentences(record["text"]):
                    where.setdefault(sentence, (record["document_id"], record["page"]))

            judgements: dict[str, judge.Judgement] = {}
            target = case.get("assessment_target", {})
            if self._model is not None and records:
                # Each step must fit twice over, so a slow machine stops before the limit.
                judgements = judge.judge_case(records, self._criteria, self._model, target.get("description", ""),
                                              lambda last: guard.have_ms(2000.0 * last))

            decision = trl.decide(where, target.get("type", ""))
            kwargs = decision.result_kwargs()
            if decision.support.get(decision.predicted_trl):
                best = decision.support[decision.predicted_trl][0]
                doc_id, page_no = where[best]
                kwargs["trl_rationale"] += f' Strongest: {doc_id} p.{page_no}: "{best[:240]}"'
            return output.build_result(
                case, self._checklist_version, self._criterion_ids,
                criterion_status={cid: j.status for cid, j in judgements.items()},
                evidence_reference={cid: j.evidence for cid, j in judgements.items()},
                missing_evidence={cid: _NOT_FOUND_NOTE if cid in judgements else _NOT_JUDGED_NOTE
                                  for cid in self._criterion_ids},
                **kwargs,
            )
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
        """Nothing to release: every PDF is closed as soon as it is read."""
