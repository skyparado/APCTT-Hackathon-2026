"""End-to-end regression run (Task 16): every labelled case through the kit server.

    python team/regress.py                       # all data/cases, server on 127.0.0.1:8000
    python team/regress.py NTRS-20080012738      # some cases
    python team/regress.py --save run.json       # also keep the numbers to compare later

Needs a running server pointed at our module (team/HOW_TO_RUN.md) and the request.json files
from `python data/build_cases.py`. For each case it submits the request (fresh request_id per
run, retrying on 503 BUSY), waits for the job, and scores the result against labels.json:

  * A  - TRL decision, official rule: exact 1.0, off by one 0.5, abstain 0.25 (13.2);
  * B  - criteria: met part (we say met and a gold page is in our first 3 distinct pages) and
         not-established part (we do not say met), B = (2*met + not) / 3, pooled (13.3);
  * quotes - share of supporting_span texts found on their cited page (needs pypdfium2);
  * timings - the server's timings_ms.total and our wall time; failures with error codes.

Standard library only (pypdfium2 optional). Dev-only, never shipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from participant_module.trl import score_a  # noqa: E402

CASES = ROOT / "data" / "cases"


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict, dict]:
    """(status, headers, JSON body), as in API_REFERENCE's python client."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), json.loads(error.read())


def run_case(base: str, body: dict, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        status, headers, envelope = call(base, "POST", "/v1/assessments", body)
        if status == 202:
            break
        error = envelope.get("error", {})
        if status == 503 and error.get("retryable") and time.monotonic() < deadline:
            time.sleep(float(headers.get("Retry-After", "1")))
            continue
        raise RuntimeError(f"{status} {error.get('code')}: {error.get('field_errors')}")
    location = headers.get("Location") or headers.get("location")
    while envelope.get("job_status") != "finished":
        if time.monotonic() > deadline:
            raise TimeoutError(f"job {location} not finished after {timeout_s:.0f} s")
        time.sleep(0.5)
        _, _, envelope = call(base, "GET", location)
    return envelope


def criteria_hits(result: dict, label: dict) -> tuple[list[int], list[int]]:
    """Per labelled criterion: met-part hits and not-established-part hits (0/1 each)."""
    met_part, not_part = [], []
    ours = result.get("criterion_status", {})
    for cid, gold in (label.get("criteria") or {}).items():
        if cid not in ours:
            continue
        we_say_met = ours[cid] == "met"
        if gold["status"] == "met":
            gold_pages = {(p["document_id"], p["page"]) for p in gold.get("pages", [])}
            first3: list[tuple[str, int]] = []
            for item in result.get("evidence_reference", {}).get(cid, []):
                key = (item["document_id"], item["page"])
                if key not in first3:
                    first3.append(key)
            met_part.append(int(we_say_met and bool(set(first3[:3]) & gold_pages)))
        else:
            not_part.append(int(not we_say_met))
    return met_part, not_part


def quote_checks(result: dict, case: dict, case_dir: Path) -> tuple[int, int]:
    """(valid, total) supporting spans; total 0 when pypdfium2 is missing or no spans."""
    spans = [(item["document_id"], item["page"], item["supporting_span"])
             for items in result.get("evidence_reference", {}).values()
             for item in items if item.get("supporting_span")]
    if not spans:
        return 0, 0
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return 0, 0
    files = {d["document_id"]: case_dir / d["file"] for d in case["documents"]}
    norm = lambda s: " ".join(s.split()).lower()  # noqa: E731
    valid = 0
    for doc_id, page, span in spans:
        pdf = pdfium.PdfDocument(str(files[doc_id]))
        try:
            text = pdf[page - 1].get_textpage().get_text_range()
        finally:
            pdf.close()
        valid += norm(span) in norm(text)
    return valid, len(spans)


def _self_test() -> None:
    label = {"criteria": {
        "C1": {"status": "met", "pages": [{"document_id": "D001", "page": 4}]},
        "C2": {"status": "not met"},
        "C3": {"status": "met", "pages": [{"document_id": "D001", "page": 9}]},
    }}
    ev = lambda *pages: [{"document_id": "D001", "page": p} for p in pages]  # noqa: E731
    result = {"criterion_status": {"C1": "met", "C2": "insufficient evidence", "C3": "met"},
              # C1: gold page 4 is the 3rd distinct page (1 repeats) -> hit; C3: gold 9 is 4th -> miss
              "evidence_reference": {"C1": ev(1, 1, 2, 4), "C3": ev(1, 2, 3, 9)}}
    assert criteria_hits(result, label) == ([1, 0], [1]), criteria_hits(result, label)
    result["criterion_status"]["C2"] = "met"
    assert criteria_hits(result, label)[1] == [0]
    print("regress self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", nargs="*", help="case folders under --dir (default: all)")
    parser.add_argument("--dir", type=Path, default=CASES, help="folder of case folders (data/heldout for the held-out set)")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds per case, including queueing")
    parser.add_argument("--save", type=Path, help="write the per-case numbers to this JSON file")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        return 0

    try:
        status, _, ready = call(args.base, "GET", "/health/ready")
    except urllib.error.URLError as exc:
        print(f"no server at {args.base} ({exc.reason}); start it first (team/HOW_TO_RUN.md)")
        return 2
    if status != 200 or not ready.get("ready"):
        print(f"server at {args.base} is not ready: {status} {ready}")
        return 2

    run_tag = time.strftime("r%Y%m%d%H%M%S")
    dirs = [args.dir / c for c in args.cases] or sorted(p for p in args.dir.iterdir() if p.is_dir())
    rows, met_all, not_all, q_valid, q_total, failures = [], [], [], 0, 0, 0
    print(f"{'case':18} {'label':10} {'ours':22} {'A':>4}  {'origin':10} {'server ms':>9} {'wall s':>7}  notes")
    for case_dir in dirs:
        if not (case_dir / "request.json").is_file():
            failures += 1
            print(f"{case_dir.name:18} SKIPPED: no request.json (run data/build_cases.py and fix its issues)")
            rows.append({"case": case_dir.name, "error": "no request.json"})
            continue
        body = json.loads((case_dir / "request.json").read_text(encoding="utf-8"))
        label = json.loads((case_dir / "labels.json").read_text(encoding="utf-8"))
        case_meta = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        body["request_id"] = f"{body['request_id']}-{run_tag}"[:128]
        start = time.monotonic()
        try:
            envelope = run_case(args.base, body, args.timeout)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            failures += 1
            print(f"{case_dir.name:18} ERROR {exc}")
            rows.append({"case": case_dir.name, "error": str(exc)})
            continue
        wall = time.monotonic() - start
        result = envelope.get("result") or {}
        diag = envelope.get("diagnostics") or {}
        origin = envelope.get("result_origin")
        res_status = result.get("assessment_status")
        decision = SimpleNamespace(status=res_status, predicted_trl=result.get("predicted_trl"),
                                   abstention_reason=result.get("abstention_reason"))
        a = 0.0 if res_status == "failed" else score_a(decision, label)
        met_part, not_part = criteria_hits(result, label)
        met_all += met_part
        not_all += not_part
        valid, total = quote_checks(result, case_meta, case_dir)
        q_valid += valid
        q_total += total
        notes = []
        if res_status == "failed":
            failures += 1
            notes.append(f"error_code={result.get('error_code')}")
        if diag.get("output_issues"):
            notes.append(f"output_issues={diag['output_issues']}")
        if diag.get("warning_codes"):
            notes.append(f"warnings={diag['warning_codes']}")
        ours = (f"TRL {result.get('predicted_trl')}" if res_status == "completed"
                else f"{res_status} ({result.get('abstention_reason') or result.get('error_code')})")
        want = f"TRL {label['trl']}" if label.get("trl") is not None else "abstain"
        total_ms = (diag.get("timings_ms") or {}).get("total")
        print(f"{case_dir.name:18} {want:10} {ours[:22]:22} {a:4.2f}  {str(origin):10} "
              f"{str(total_ms):>9} {wall:7.1f}  {'; '.join(notes)}")
        rows.append({"case": case_dir.name, "label_trl": label.get("trl"), "status": res_status,
                     "predicted_trl": result.get("predicted_trl"), "abstention_reason": result.get("abstention_reason"),
                     "A": a, "origin": origin, "server_total_ms": total_ms, "wall_s": round(wall, 1),
                     "met_part": met_part, "not_part": not_part, "notes": notes})

    scored = [r for r in rows if "A" in r]
    mean_a = sum(r["A"] for r in scored) / len(scored) if scored else 0.0
    m = sum(met_all) / len(met_all) if met_all else None
    n = sum(not_all) / len(not_all) if not_all else None
    b = (2 * m + n) / 3 if m is not None and n is not None else (m if n is None else n)
    slowest = max((r["server_total_ms"] or 0 for r in scored), default=0)
    print(f"\ncases {len(dirs)}  failed {failures}  mean A {mean_a:.3f}  "
          f"B {'n/a' if b is None else f'{b:.3f}'} (met part {m if m is None else f'{m:.2f}'}, "
          f"not-established part {n if n is None else f'{n:.2f}'})  "
          f"quotes {q_valid}/{q_total}  slowest server total {slowest} ms")
    if args.save:
        args.save.write_text(json.dumps({"run": run_tag, "mean_A": mean_a, "B": b, "quotes": [q_valid, q_total],
                                         "cases": rows}, indent=2) + "\n", encoding="utf-8")
        print(f"saved {args.save}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
