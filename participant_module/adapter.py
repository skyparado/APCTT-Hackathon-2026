"""participant_module/adapter.py — the team's AssessmentModule (SPEC-09).

Current behaviour: reads every page, splits it into sentences and lets the TRL logic
(`participant_module/trl.py`, Task 13) pick a TRL or abstain. Every checklist criterion stays
`insufficient evidence` until the criterion judge exists, because a wrong `met` costs both the
evidence and the quote-review score. Pieces already wired in:

  * result construction and local enforcement — `participant_module/output.py` (Task 14);
  * a time budget guard that returns before the 180 s limit — `participant_module/budget.py`
    (Task 15).

Later tasks slot into `_assess_case`: retrieval (Task 10) narrows the sentences, the criterion
judge (Task 11) fills `criterion_status`, the quote extractor (Task 12) adds supporting spans;
everything still goes through `output.build_result`, which keeps the output contract-valid.

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

from participant_module import budget, output, trl

# Sentence boundary: end punctuation, whitespace, then a capital or digit. Good enough for
# report prose; abbreviations like "Fig. 3" split early, which only costs a weaker sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_NO_JUDGE_NOTE = "No criterion-level judgement was made; the criterion judge is not enabled."


def _read_pages(pdfium: Any, path: str) -> list[str]:
    """Text of every page, in file order (page 1 first)."""
    # ponytail: plain pypdfium2 text, no OCR for scanned pages; Rei's page reader (Task 7) replaces this.
    doc = pdfium.PdfDocument(path)
    try:
        pages = []
        for index in range(len(doc)):
            page = doc[index]
            try:
                textpage = page.get_textpage()
                pages.append(textpage.get_text_range())
                textpage.close()
            finally:
                page.close()
        return pages
    finally:
        doc.close()


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
        self._pdfium: Any = None

    def load(self, config: Mapping[str, Any], asset_root: Path) -> None:
        """Read the checklist and settings. Load rules/weights from `asset_root` here.

        The checklist is the only source of criterion IDs (DATA_CONTRACT §1.4). Nothing is
        downloaded; `asset_root` is treated as read-only.
        """
        checklist = config["checklist"]
        self._checklist_version = checklist["version"]
        self._criterion_ids = [c["criterion_id"] for c in checklist["criteria"]]
        self._settings = config.get("module", {}).get("settings", {})
        try:
            import pypdfium2  # in the common base env; absent on a bare dev machine

            self._pdfium = pypdfium2
        except ImportError:
            self._pdfium = None

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
            if self._pdfium is None:
                return output.abstained(
                    case, self._checklist_version, self._criterion_ids,
                    missing_note="PDF text extraction is not available in this environment.",
                )

            # Read every document; a broken or encrypted PDF is skipped, not fatal. Running low
            # on time stops reading and decides on what was read so far.
            where: dict[str, tuple[str, int]] = {}  # sentence -> (document_id, page)
            for document in case.get("documents", []):
                if guard.exhausted():
                    break
                try:
                    pages = _read_pages(self._pdfium, document["path"])
                except Exception:  # noqa: BLE001 - pdfium raises its own error types
                    traceback.print_exc()
                    continue
                for page_no, text in enumerate(pages, start=1):
                    for sentence in _sentences(text):
                        where.setdefault(sentence, (document["document_id"], page_no))

            target_type = case.get("assessment_target", {}).get("type", "")
            decision = trl.decide(where, target_type)
            kwargs = decision.result_kwargs()
            if decision.status == "completed":
                best = decision.support[decision.predicted_trl][0]
                doc_id, page_no = where[best]
                kwargs["trl_rationale"] += f' Strongest: {doc_id} p.{page_no}: "{best[:240]}"'
            return output.build_result(
                case, self._checklist_version, self._criterion_ids,
                missing_evidence={cid: _NO_JUDGE_NOTE for cid in self._criterion_ids},
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
