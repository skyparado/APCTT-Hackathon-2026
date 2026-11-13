"""Run the public USGS cases through the kit server and check every result (dev-only, never shipped).

    ~/apctt-env/bin/python team/run_public.py --req ~/apctt-cases/req --pdf ~/apctt-cases/pdf --out ~/apctt-run
    ~/apctt-env/bin/python team/run_public.py ... USGS-SDG-012 USGS-SDG-040 USGS-SDG-061   # the smoke cases
    ~/apctt-env/bin/python team/run_public.py --summary ~/apctt-run                        # re-read saved results

Needs a running server on our module (team/HOW_TO_RUN.md) and request files from
`tools/get_public_cases.py --make-requests`. Per case it saves the full job envelope to OUT/<case>.json
and prints status, origin, TRL vs the organizer's estimate, server time, criteria met, and quote checks:
every supporting_span must be on its cited page (pypdfium2 text, pdfium hyphen U+FFFE read as "-") and
must not contain U+FFFE itself. The summary adds Part A against the estimates (not expert labels) and
Part B against data/public_criteria_labels.json (unreviewed drafts) where a case has them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "team"))
from regress import run_case  # noqa: E402

HYPHEN = chr(0xFFFE)
MANIFEST = {c["case_id"]: c for c in json.loads((ROOT / "contracts" / "public-cases.json").read_text(encoding="utf-8"))["cases"]}
DRAFT = json.loads((ROOT / "data" / "public_criteria_labels.json").read_text(encoding="utf-8"))["cases"]


def _norm(text: str) -> str:
    return " ".join(text.replace(HYPHEN, "-").split())


def quote_problems(result: dict, pdf: Path) -> tuple[int, list[str]]:
    """(spans checked, problems) for every supporting_span of the result.

    A multi-document case keeps each document as <case>.<document_id>.pdf next to <case>.pdf."""
    spans = [(cid, item["document_id"], item["page"], item.get("supporting_span", ""))
             for cid, items in result.get("evidence_reference", {}).items() for item in items]
    problems: list[str] = []
    for doc_id in sorted({s[1] for s in spans}):
        path = pdf.with_name(f"{pdf.stem}.{doc_id}.pdf")
        problems += _check_document(path if path.exists() else pdf, [s for s in spans if s[1] == doc_id])
    return len(spans), problems


def _check_document(pdf: Path, spans: list[tuple[str, str, int, str]]) -> list[str]:
    import pypdfium2 as pdfium

    problems: list[str] = []
    document = pdfium.PdfDocument(str(pdf))
    try:
        for cid, doc_id, page, span in spans:
            cid = f"{cid} {doc_id}"
            if not span:
                problems.append(f"{cid} p{page}: no supporting_span")
                continue
            if HYPHEN in span:
                problems.append(f"{cid} p{page}: span contains U+FFFE")
            if not 1 <= page <= len(document):
                problems.append(f"{cid} p{page}: page out of range")
                continue
            textpage = document[page - 1].get_textpage()
            try:
                text = textpage.get_text_range() or ""
            finally:
                textpage.close()
            # OCR pages have no text layer, so a missing span there is expected, not fabrication.
            if len(text.strip()) >= 20 and _norm(span) not in _norm(text):
                problems.append(f"{cid} p{page}: span not on page: {span[:80]!r}")
    finally:
        document.close()
    return problems


def part_a(result: dict, estimate: int) -> float:
    if result.get("assessment_status") == "abstained":
        return 0.25
    trl = result.get("predicted_trl")
    if result.get("assessment_status") != "completed" or trl is None:
        return 0.0
    return {0: 1.0, 1: 0.5}.get(abs(trl - estimate), 0.0)


def part_b(result: dict, draft: dict) -> tuple[list[int], list[int]]:
    met_part, not_part = [], []
    status = result.get("criterion_status", {})
    for short, gold_pages in draft.get("met", {}).items():
        cid = f"APCTT-{short}"
        first3: list[int] = []
        for item in result.get("evidence_reference", {}).get(cid, []):
            if item["page"] not in first3:
                first3.append(item["page"])
        met_part.append(int(status.get(cid) == "met" and bool(set(first3[:3]) & set(gold_pages))))
    for short in draft.get("insufficient", []):
        not_part.append(int(status.get(f"APCTT-{short}") != "met"))
    return met_part, not_part


def summarize(rows: list[dict]) -> None:
    done = [r for r in rows if "status" in r]
    failed = [r for r in done if r["status"] not in ("completed", "abstained") or r["origin"] != "module"]
    print(f"\ncases {len(done)}  failed/replaced {len(failed)}: {[r['case'] for r in failed]}")
    if not done:
        return
    times = sorted(r["ms"] for r in done if r["ms"] is not None)
    if times:
        print(f"server time: median {times[len(times) // 2] / 1000:.1f} s, max {times[-1] / 1000:.1f} s "
              f"({max(done, key=lambda r: r['ms'] or 0)['case']})")
    scored = [r["a"] for r in done if r["a"] is not None]
    if scored:
        print(f"A vs organizer estimates: {sum(scored) / len(scored):.3f}")
    met = [h for r in done for h in r["b_met"]]
    nots = [h for r in done for h in r["b_not"]]
    if met or nots:
        m = sum(met) / len(met) if met else 0.0
        n = sum(nots) / len(nots) if nots else 0.0
        b = (2 * m + n) / 3 if met and nots else (m if met else n)
        print(f"B vs draft labels ({len([r for r in done if r['b_met'] or r['b_not']])} cases): {b:.3f} "
              f"(met part {m:.2f} of {len(met)}, not-established {n:.2f} of {len(nots)})")
    spans = sum(r["spans"] for r in done)
    bad = [p for r in done for p in r["problems"]]
    print(f"quotes: {spans} spans, {len(bad)} problems")
    for r in done:
        for p in r["problems"]:
            print(f"  {r['case']} {p}")
    no_met = [r["case"] for r in done if r["met"] == 0]
    print(f"cases with no criterion met (judge model missing or too slow?): {no_met}")
    counts: dict[str, int] = {}
    for r in done:
        for cid in r["met_ids"]:
            counts[cid] = counts.get(cid, 0) + 1
    print("met per criterion:", " ".join(f"{c[-3:]}:{counts[c]}" for c in sorted(counts)))


def row_for(case_id: str, envelope: dict, pdf_dir: Path) -> dict:
    result = envelope.get("result") or {}
    timings = (envelope.get("diagnostics") or {}).get("timings_ms") or {}
    met_ids = [cid for cid, s in result.get("criterion_status", {}).items() if s == "met"]
    spans, problems = quote_problems(result, pdf_dir / f"{case_id}.pdf")
    b_met, b_not = part_b(result, DRAFT.get(case_id, {}))
    estimate = MANIFEST[case_id]["reference_labels"]["estimated_trl"] if case_id in MANIFEST else None  # hard cases have none
    return {"case": case_id, "status": result.get("assessment_status"), "origin": envelope.get("result_origin"),
            "error": result.get("error_code"), "trl": result.get("predicted_trl"),
            "estimate": estimate, "a": None if estimate is None else part_a(result, estimate),
            "ms": timings.get("total"), "met": len(met_ids), "met_ids": met_ids,
            "spans": spans, "problems": problems, "b_met": b_met, "b_not": b_not}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", nargs="*", help="case IDs (default: every request file)")
    parser.add_argument("--req", type=Path, default=Path.home() / "apctt-cases" / "req")
    parser.add_argument("--pdf", type=Path, default=Path.home() / "apctt-cases" / "pdf")
    parser.add_argument("--out", type=Path, default=Path.home() / "apctt-run")
    parser.add_argument("--summary", type=Path, help="only summarize saved envelopes in this folder")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    if args.summary:
        rows = [row_for(p.stem, json.loads(p.read_text(encoding="utf-8")), args.pdf)
                for p in sorted(args.summary.glob("*.json"))]
        summarize(rows)
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    ids = args.cases or sorted(p.stem for p in args.req.glob("*.json"))
    rows = []
    for case_id in ids:
        body = json.loads((args.req / f"{case_id}.json").read_text(encoding="utf-8"))
        body["request_id"] = f"pub-{case_id}-{time.time_ns() % 10**9}"
        try:
            envelope = run_case(args.base, body, timeout_s=600.0)
        except Exception as exc:  # noqa: BLE001 - one bad case must not stop the run
            print(f"{case_id}: run error {exc}", flush=True)
            rows.append({"case": case_id})
            continue
        (args.out / f"{case_id}.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=1), encoding="utf-8")
        row = row_for(case_id, envelope, args.pdf)
        rows.append(row)
        print(f"{case_id} {row['status']:9} {row['origin']:10} TRL {row['trl']} (est {row['estimate']}) "
              f"{(row['ms'] or 0) / 1000:6.1f} s  met {row['met']:2}  spans {row['spans']:2}  "
              f"problems {len(row['problems'])} {row['error'] or ''}", flush=True)
    summarize(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
