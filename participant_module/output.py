from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

ASSESSMENT_STATUSES = ("completed", "abstained", "failed")
CRITERION_STATUSES = ("met", "not met", "insufficient evidence")
ABSTENTION_REASONS = (
    "insufficient evidence",
    "conflicting evidence",
    "ambiguous scope",
    "out of scope",
)
OPTIONAL_FIELDS = ("confidence", "uncertainty", "trl_rationale", "criterion_rationale")


class ResultContractError(ValueError):
    pass


def _is_nonblank(text: Any) -> bool:
    return isinstance(text, str) and text.strip() != ""


def _page_counts(case: Mapping[str, Any]) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for document in case.get("documents", []):
        doc_id = document.get("document_id")
        if isinstance(doc_id, str):
            pages = document.get("page_count")
            counts[doc_id] = pages if isinstance(pages, int) and not isinstance(pages, bool) else None
    return counts


def base_identity(case: Mapping[str, Any], checklist_version: str) -> dict[str, Any]:
    return {
        "schema_version": case["schema_version"],
        "checklist_version": checklist_version,
        "case_id": case["case_id"],
        "assessment_target": dict(case["assessment_target"]),
    }


def _clean_evidence(
    items: Any,
    page_counts: Mapping[str, int | None],
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return cleaned
    for item in items:
        if not isinstance(item, Mapping):
            continue
        doc_id = item.get("document_id")
        page = item.get("page")
        if not isinstance(doc_id, str) or doc_id not in page_counts:
            continue
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            continue
        pages = page_counts[doc_id]
        if pages is not None and page > pages:
            continue
        evidence: dict[str, Any] = {"document_id": doc_id, "page": page}
        span = item.get("supporting_span")
        if _is_nonblank(span):
            evidence["supporting_span"] = span
        cleaned.append(evidence)
    return cleaned


def build_result(
    case: Mapping[str, Any],
    checklist_version: str,
    criterion_ids: Sequence[str],
    *,
    status: str,
    predicted_trl: int | None = None,
    criterion_status: Mapping[str, str] | None = None,
    evidence_reference: Mapping[str, Any] | None = None,
    missing_evidence: Mapping[str, str] | None = None,
    abstention_reason: str | None = None,
    error_code: str | None = None,
    confidence: float | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    trl_rationale: str | None = None,
    criterion_rationale: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if status not in ASSESSMENT_STATUSES:
        raise ResultContractError(f"unknown assessment_status: {status!r}")
    ids = list(criterion_ids)

    if status == "failed":
        if not _is_nonblank(error_code):
            raise ResultContractError("a failed result needs a non-blank error_code")
        result = base_identity(case, checklist_version)
        result.update(
            assessment_status="failed",
            predicted_trl=None,
            criterion_status={},
            evidence_reference={},
            missing_evidence={},
            abstention_reason=None,
            error_code=error_code,
        )
        return result

    status_in = dict(criterion_status or {})
    evidence_in = dict(evidence_reference or {})
    missing_in = dict(missing_evidence or {})
    page_counts = _page_counts(case)

    out_status: dict[str, str] = {}
    out_evidence: dict[str, list[dict[str, Any]]] = {}
    out_missing: dict[str, str] = {}

    for cid in ids:
        cstatus = status_in.get(cid, "insufficient evidence")
        if cstatus not in CRITERION_STATUSES:
            raise ResultContractError(f"bad status {cstatus!r} for criterion {cid!r}")
        evidence = _clean_evidence(evidence_in.get(cid, []), page_counts)
        if cstatus == "met" and not evidence:
            cstatus = "insufficient evidence"
        out_status[cid] = cstatus
        out_evidence[cid] = evidence
        if cstatus == "insufficient evidence":
            note = missing_in.get(cid)
            out_missing[cid] = note if _is_nonblank(note) else "No sufficient evidence was found."

    result = base_identity(case, checklist_version)
    result.update(
        assessment_status=status,
        criterion_status=out_status,
        evidence_reference=out_evidence,
        missing_evidence=out_missing,
        error_code=None,
    )

    if status == "completed":
        if not (isinstance(predicted_trl, int) and not isinstance(predicted_trl, bool) and 1 <= predicted_trl <= 9):
            raise ResultContractError("a completed result needs an integer TRL 1-9")
        result["predicted_trl"] = predicted_trl
        result["abstention_reason"] = None
    else:
        reason = abstention_reason if abstention_reason in ABSTENTION_REASONS else "insufficient evidence"
        result["predicted_trl"] = None
        result["abstention_reason"] = reason

    if confidence is not None and isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        if 0 <= float(confidence) <= 1:
            result["confidence"] = confidence
    if uncertainty is not None:
        result["uncertainty"] = dict(uncertainty)
    if status == "completed" and _is_nonblank(trl_rationale):
        result["trl_rationale"] = trl_rationale
    if criterion_rationale:
        rationale = {cid: text for cid, text in criterion_rationale.items() if cid in out_status and _is_nonblank(text)}
        if rationale:
            result["criterion_rationale"] = rationale

    return result


def abstained(
    case: Mapping[str, Any],
    checklist_version: str,
    criterion_ids: Sequence[str],
    *,
    reason: str = "insufficient evidence",
    missing_note: str = "No sufficient evidence was found.",
) -> dict[str, Any]:
    return build_result(
        case,
        checklist_version,
        criterion_ids,
        status="abstained",
        abstention_reason=reason,
        missing_evidence={cid: missing_note for cid in criterion_ids},
    )


def failed(
    case: Mapping[str, Any],
    checklist_version: str,
    error_code: str,
) -> dict[str, Any]:
    return build_result(
        case,
        checklist_version,
        (),
        status="failed",
        error_code=error_code,
    )


def safe_result(
    assess: Callable[[], dict[str, Any]],
    case: Mapping[str, Any],
    checklist_version: str,
    *,
    error_code: str = "TEAM_MODULE_ASSESS_ERROR",
    on_error: Callable[[BaseException], None] | None = None,
) -> dict[str, Any]:
    try:
        return assess()
    except BaseException as error:
        if on_error is not None:
            on_error(error)
        return failed(case, checklist_version, error_code)


def validate_local(
    result: Any,
    case: Mapping[str, Any],
    criterion_ids: Sequence[str],
) -> list[str]:
    problems: list[str] = []
    if not isinstance(result, Mapping):
        return ["result is not a JSON object"]

    ids = set(criterion_ids)
    status = result.get("assessment_status")
    if status not in ASSESSMENT_STATUSES:
        problems.append(f"assessment_status {status!r} not allowed")

    for field, expected in base_identity(case, result.get("checklist_version", "")).items():
        if field == "checklist_version":
            continue
        if result.get(field) != expected:
            problems.append(f"{field} does not match the case")

    if status == "failed":
        if not _is_nonblank(result.get("error_code")):
            problems.append("failed result needs a non-blank error_code")
        for field in OPTIONAL_FIELDS:
            if field in result:
                problems.append(f"{field} is not allowed on a failed result")
        return problems

    if status == "completed":
        trl = result.get("predicted_trl")
        if not (isinstance(trl, int) and not isinstance(trl, bool) and 1 <= trl <= 9):
            problems.append("completed result needs an integer TRL 1-9")
        if result.get("abstention_reason") is not None:
            problems.append("completed result must have abstention_reason null")
    elif status == "abstained":
        if result.get("predicted_trl") is not None:
            problems.append("abstained result must have predicted_trl null")
        if result.get("abstention_reason") not in ABSTENTION_REASONS:
            problems.append("abstained result needs one of the four abstention reasons")

    if result.get("error_code") is not None:
        problems.append("error_code must be null unless failed")

    cstatus = result.get("criterion_status", {})
    evidence = result.get("evidence_reference", {})
    missing = result.get("missing_evidence", {})
    page_counts = _page_counts(case)

    if set(cstatus) != ids:
        problems.append("criterion_status keys must match the checklist exactly")
    if set(evidence) != ids:
        problems.append("evidence_reference keys must match the checklist exactly")

    for cid in ids:
        st = cstatus.get(cid)
        if st not in CRITERION_STATUSES:
            problems.append(f"criterion {cid}: bad status {st!r}")
        items = evidence.get(cid, [])
        if not isinstance(items, list):
            problems.append(f"criterion {cid}: evidence must be a list")
            items = []
        if st == "met" and not items:
            problems.append(f"criterion {cid}: met with no evidence")
        if st == "insufficient evidence" and not _is_nonblank(missing.get(cid)):
            problems.append(f"criterion {cid}: insufficient evidence with no missing_evidence note")
        for item in items:
            if not isinstance(item, Mapping) or "document_id" not in item or "page" not in item:
                problems.append(f"criterion {cid}: malformed evidence item")
                continue
            doc_id, page = item.get("document_id"), item.get("page")
            if doc_id not in page_counts:
                problems.append(f"criterion {cid}: evidence document {doc_id!r} not in case")
            else:
                pages = page_counts[doc_id]
                if not isinstance(page, int) or isinstance(page, bool) or page < 1 or (pages is not None and page > pages):
                    problems.append(f"criterion {cid}: evidence page {page!r} out of range")
            if "supporting_span" in item and not _is_nonblank(item["supporting_span"]):
                problems.append(f"criterion {cid}: blank supporting_span")

    for key in missing:
        if key not in ids:
            problems.append(f"missing_evidence has unknown criterion {key!r}")
    return problems
