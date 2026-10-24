"""Check every labelled case and build its request.json (Task 8).

    python -I data/build_cases.py              # all cases under data/cases/
    python -I data/build_cases.py EX-001       # one case
    python -I data/build_cases.py --self-test

For each data/cases/<case_id>/ it reads case.json (the kit's case fields, with `file` in place of
the PDF bytes) and labels.json (our expert-style answer), checks both, and writes request.json
ready to POST to /v1/assessments. Exit code 1 if any case has issues.

Standard library only. If pypdfium2 or pypdf is importable (WSL base env), it also checks that
label pages exist and that every quote really appears on its page; otherwise those two checks
are skipped with a note.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_request import build_request  # noqa: E402  (the kit's own base64 + sha256 logic)

CASES = ROOT / "data" / "cases"
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
CASE_REQUIRED = {
    "schema_version", "input_profile", "checklist_version", "case_id", "assessment_as_of",
    "assessment_target", "intended_application", "intended_environment", "title", "documents",
}
CASE_OPTIONAL = {"description", "benefits", "sdg_targets", "sdg_rationale"}
TARGET_TYPES = {"component", "subsystem", "system", "technology"}
ABSTENTION_REASONS = {"insufficient evidence", "conflicting evidence", "ambiguous scope", "out of scope"}
CRITERION_STATUSES = {"met", "not met", "insufficient evidence"}
# A quote that is mostly a TRL claim is never evidence (PROBLEM_DESCRIPTION 13.4).
TRL_ONLY = re.compile(r"^\W*(\w+\W+){0,8}TRL[\s-]*\d(\W+\w+){0,3}\W*$", re.IGNORECASE)


def check_case(case: dict, case_dir: Path) -> list[str]:
    issues = []
    keys = set(case)
    for k in CASE_REQUIRED - keys:
        issues.append(f"case.json: missing `{k}`")
    for k in keys - CASE_REQUIRED - CASE_OPTIONAL:
        issues.append(f"case.json: unknown field `{k}` (the server rejects it; labels go in labels.json)")
    for k in CASE_OPTIONAL & keys:
        if case[k] is None:
            issues.append(f"case.json: omit `{k}` instead of null")
    if not IDENT.fullmatch(str(case.get("case_id", ""))):
        issues.append("case.json: case_id is not an identifier")
    elif case["case_id"] != case_dir.name:
        issues.append(f"case.json: case_id {case['case_id']!r} != folder name {case_dir.name!r}")
    target = case.get("assessment_target") or {}
    if target.get("type") not in TARGET_TYPES:
        issues.append(f"case.json: assessment_target.type must be one of {sorted(TARGET_TYPES)}")
    if not IDENT.fullmatch(str(target.get("target_id", ""))):
        issues.append("case.json: assessment_target.target_id is not an identifier")
    docs = case.get("documents") or []
    if not 1 <= len(docs) <= 20:
        issues.append("case.json: needs 1 to 20 documents")
    ids = [d.get("document_id") for d in docs]
    if len(set(ids)) != len(ids):
        issues.append("case.json: duplicate document_id")
    for d in docs:
        if not IDENT.fullmatch(str(d.get("document_id", ""))):
            issues.append(f"case.json: document_id {d.get('document_id')!r} is not an identifier")
        if not (case_dir / str(d.get("file", ""))).is_file():
            issues.append(f"case.json: file {d.get('file')!r} not found in {case_dir.name}/")
    return issues


def check_labels(labels: dict, case: dict, page_texts: dict[str, list[str]] | None) -> list[str]:
    issues = []
    if labels.get("case_id") != case.get("case_id"):
        issues.append("labels.json: case_id does not match case.json")
    for k in ("labelled_by", "labelled_on", "label_origin"):
        if not labels.get(k):
            issues.append(f"labels.json: `{k}` is required (needed for declaration.json)")
    status, trl, reason = labels.get("assessment_status"), labels.get("trl"), labels.get("abstention_reason")
    if status == "completed":
        if not (isinstance(trl, int) and not isinstance(trl, bool) and 1 <= trl <= 9):
            issues.append("labels.json: completed needs an integer trl 1-9")
        if reason is not None:
            issues.append("labels.json: completed needs abstention_reason null")
    elif status == "abstained":
        if trl is not None:
            issues.append("labels.json: abstained needs trl null")
        if reason not in ABSTENTION_REASONS:
            issues.append(f"labels.json: abstention_reason must be one of {sorted(ABSTENTION_REASONS)}")
    else:
        issues.append("labels.json: assessment_status must be completed or abstained")

    doc_ids = {d.get("document_id") for d in case.get("documents", [])}

    def check_ref(where: str, doc_id: object, page: object, quote: str | None = None) -> None:
        if doc_id not in doc_ids:
            issues.append(f"labels.json: {where}: unknown document_id {doc_id!r}")
            return
        if not (isinstance(page, int) and not isinstance(page, bool) and page >= 1):
            issues.append(f"labels.json: {where}: page must be an integer >= 1")
            return
        if page_texts is None:
            return
        pages = page_texts[doc_id]
        if page > len(pages):
            issues.append(f"labels.json: {where}: page {page} > {len(pages)} pages in {doc_id}")
        elif quote is not None and _norm(quote) not in _norm(pages[page - 1]):
            issues.append(f"labels.json: {where}: quote not found on {doc_id} p.{page}")

    for i, ev in enumerate(labels.get("evidence", [])):
        where = f"evidence[{i}]"
        quote = ev.get("quote", "")
        if not str(quote).strip():
            issues.append(f"labels.json: {where}: quote is required")
        elif TRL_ONLY.match(quote):
            issues.append(f"labels.json: {where}: quote only states a TRL; that is never evidence")
        check_ref(where, ev.get("document_id"), ev.get("page"), quote)
    if status == "completed" and not labels.get("evidence"):
        issues.append("labels.json: completed needs at least one evidence item")

    for cid, crit in (labels.get("criteria") or {}).items():
        if crit.get("status") not in CRITERION_STATUSES:
            issues.append(f"labels.json: criteria.{cid}: status must be one of {sorted(CRITERION_STATUSES)}")
        if crit.get("status") == "met" and not crit.get("pages"):
            issues.append(f"labels.json: criteria.{cid}: met needs at least one gold page")
        for p in crit.get("pages", []):
            check_ref(f"criteria.{cid}", p.get("document_id"), p.get("page"))
    return issues


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def read_pages(pdf: Path) -> list[str] | None:
    """Text per page, or None when no PDF library is importable here."""
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(pdf))
        return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    except ImportError:
        pass
    try:
        from pypdf import PdfReader

        return [p.extract_text() or "" for p in PdfReader(str(pdf)).pages]
    except ImportError:
        return None


def build_one(case_dir: Path) -> list[str]:
    try:
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        labels = json.loads((case_dir / "labels.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read case.json/labels.json: {exc}"]
    issues = check_case(case, case_dir)
    if issues:
        return issues

    docs_meta = case["documents"]
    pdfs = [case_dir / d["file"] for d in docs_meta]
    texts: dict[str, list[str]] | None = {}
    for d, pdf in zip(docs_meta, pdfs):
        pages = read_pages(pdf)
        if pages is None:
            texts = None
            break
        texts[d["document_id"]] = pages
    issues = check_labels(labels, case, texts)
    if texts is None:
        print(f"  note: no pypdfium2/pypdf here; page and quote checks skipped for {case_dir.name}")
    if issues:
        return issues

    template = {"case": {k: v for k, v in case.items() if k != "documents"}}
    try:
        body = build_request(template, pdfs, "pending")
    except SystemExit as exc:  # make_request exits on a non-PDF file
        return [str(exc)]
    for out_doc, meta in zip(body["case"]["documents"], docs_meta):
        out_doc.update(document_id=meta["document_id"], title=meta["title"],
                       document_date=meta.get("document_date"))
    # Content-derived request_id: changing a PDF or case field gives a new id, so the server
    # never answers 409 REQUEST_ID_CONFLICT for edited cases. Task 16 should still add a run
    # suffix, because the server also binds the id to our package hash.
    digest = hashlib.sha256(json.dumps(body["case"], sort_keys=True).encode()).hexdigest()[:10]
    body["request_id"] = f"{case['case_id']}-{digest}".replace(".", "-").replace(":", "-")
    (case_dir / "request.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return []


def self_test() -> None:
    case = {"case_id": "X", "documents": [{"document_id": "D001"}]}
    good = {"case_id": "X", "labelled_by": "a", "labelled_on": "2026-01-01", "label_origin": "o",
            "assessment_status": "completed", "trl": 4, "abstention_reason": None,
            "evidence": [{"document_id": "D001", "page": 1, "quote": "The rig was tested at 5 bar."}]}
    texts = {"D001": ["Intro.  The rig was tested\nat 5 bar. More."]}
    assert check_labels(good, case, texts) == [], check_labels(good, case, texts)
    bad = dict(good, trl=None, evidence=[{"document_id": "D001", "page": 2, "quote": "It reached TRL 6."}])
    msgs = " ".join(check_labels(bad, case, texts))
    for expected in ("integer trl", "only states a TRL", "page 2 > 1"):
        assert expected in msgs, (expected, msgs)
    fake = dict(good, evidence=[{"document_id": "D001", "page": 1, "quote": "Invented sentence."}])
    assert "quote not found" in " ".join(check_labels(fake, case, texts))
    abst = dict(good, assessment_status="abstained", trl=None, abstention_reason="maybe")
    assert "abstention_reason must be" in " ".join(check_labels(abst, case, texts))
    print("self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", nargs="*", help="case_id folders under --dir (default: all)")
    parser.add_argument("--dir", type=Path, default=CASES, help="folder of case folders (default: data/cases; data/heldout for the held-out set)")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    dirs = [args.dir / c for c in args.cases] or sorted(p for p in args.dir.iterdir() if p.is_dir())
    failed = 0
    for case_dir in dirs:
        issues = build_one(case_dir)
        if issues:
            failed += 1
            print(f"FAIL {case_dir.name}")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"ok   {case_dir.name} -> {case_dir.name}/request.json")
    print(f"{len(dirs) - failed}/{len(dirs)} cases ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
