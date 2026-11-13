"""Part B of participant_module/judge.py against the labels we have (Task 11), without the server.

    APCTT_MODEL_STORE=~/models ~/apctt-env/base/bin/python team/eval_judge.py              # odd USGS and NASA dev
    APCTT_MODEL_STORE=~/models ~/apctt-env/base/bin/python team/eval_judge.py --fold even  # check only, never tune on it

Scores every criterion once, then sweeps the threshold. Label sets: `data/public_criteria_labels.json`
(USGS-type, draft) and `data/cases` (NASA, partial). B = (2 * met part + not-established part) / 3,
pooled (PROBLEM_DESCRIPTION 13.3). Only labelled criteria count. Dev-only, never shipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from participant_module import judge, pages  # noqa: E402

CHECKLIST = json.loads((ROOT / "contracts" / "checklist.official.json").read_text(encoding="utf-8"))
SWEEP = (0.0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99)


def public_cases(pdf_dir: Path, fold: str) -> list[dict]:
    labels = json.loads((ROOT / "data" / "public_criteria_labels.json").read_text(encoding="utf-8"))["cases"]
    manifest = {c["case_id"]: c for c in json.loads((ROOT / "contracts" / "public-cases.json").read_text(encoding="utf-8"))["cases"]}
    cases = []
    for case_id, label in labels.items():
        if int(case_id[-3:]) % 2 != (fold == "odd"):
            continue
        gold = {f"APCTT-{c}": {"status": "met", "pages": set(p)} for c, p in label["met"].items()}
        gold.update({f"APCTT-{c}": {"status": "insufficient evidence"} for c in label["insufficient"]})
        cases.append({"id": case_id, "set": "usgs", "pdfs": [("D001", pdf_dir / f"{case_id}.pdf")],
                      "target": manifest[case_id]["assessment_target"]["description"], "gold": gold})
    return cases


def nasa_cases() -> list[dict]:
    cases = []
    for folder in sorted((ROOT / "data" / "cases").iterdir()):
        label = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
        meta = json.loads((folder / "case.json").read_text(encoding="utf-8"))
        gold = {cid: {"status": crit["status"], "pages": {p["page"] for p in crit.get("pages", [])}}
                for cid, crit in (label.get("criteria") or {}).items()}
        cases.append({"id": folder.name, "set": "nasa", "pdfs": [(d["document_id"], folder / d["file"]) for d in meta["documents"]],
                      "target": meta["assessment_target"]["description"], "gold": gold})
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf-dir", type=Path, default=Path.home() / "public_cases" / "pdf")
    parser.add_argument("--fold", choices=("odd", "even"), default="odd")
    parser.add_argument("--show", action="store_true", help="print the evidence chosen at each criterion's own threshold")
    args = parser.parse_args()

    start = time.monotonic()
    model = judge.load_entailment()
    if model is None:
        print("no model: set APCTT_MODEL_STORE (tools/get_models.py)")
        return 2
    print(f"model loaded in {time.monotonic() - start:.1f} s")

    rows = []  # (set, criterion, gold, [(score, page)] ranked)
    own: dict[str, float] = {}  # the threshold judge.py uses for each criterion
    for case in public_cases(args.pdf_dir, args.fold) + (nasa_cases() if args.fold == "odd" else []):
        start = time.monotonic()
        records = [r for doc, path in case["pdfs"] for r in pages.read_pages({"document_id": doc, "path": str(path)})]
        search = judge.SentenceSearch(judge.sentences_of(records))
        for criterion in CHECKLIST["criteria"]:
            gold = case["gold"].get(criterion["criterion_id"])
            if gold is None:
                continue
            profile = judge.profile_for(criterion["description"], case["target"])
            candidates = search.candidates(judge.query_for(criterion["description"], profile))
            scores = model.score([c.text for c in candidates], profile.statement) if candidates else []
            ranked = sorted(zip(scores, candidates), key=lambda pair: -pair[0])
            rows.append((case["set"], criterion["criterion_id"], gold, ranked, case["id"]))
            own[criterion["criterion_id"]] = profile.threshold
        print(f"{case['id']:18} {time.monotonic() - start:5.1f} s, {len(search.sentences)} sentences", flush=True)

    def report(items, threshold_of):
        met_hits, met_total, not_hits, not_total = 0, 0, 0, 0
        for _, cid, gold, ranked, _ in items:
            threshold = threshold_of(cid)
            pages_said = []
            for score, sentence in ranked:
                if score >= threshold and sentence.page not in pages_said:
                    pages_said.append(sentence.page)
            said_met = bool(pages_said)
            if gold["status"] == "met":
                met_total += 1
                met_hits += said_met and bool(set(pages_said[:3]) & gold["pages"])
            else:
                not_total += 1
                not_hits += not said_met
        m = met_hits / met_total if met_total else 0.0
        n = not_hits / not_total if not_total else 0.0
        return (2 * m + n) / 3, m, n, met_total, not_total

    for name in ("usgs", "nasa"):
        items = [r for r in rows if r[0] == name]
        if not items:
            continue
        b, m, n, met_total, not_total = report(items, own.__getitem__)
        print(f"\n{name}: judge.py thresholds -> B {b:.3f}  ({m:.2f} of {met_total}, {n:.2f} of {not_total})")
        print(f"{name}: one threshold -> B (met part, not part)")
        for threshold in SWEEP:
            b, m, n, met_total, not_total = report(items, lambda _c, t=threshold: t)
            print(f"  {threshold:4.2f}  B {b:.3f}  ({m:.2f} of {met_total}, {n:.2f} of {not_total})")
        print("  per criterion, best score when gold met / not:")
        for criterion in CHECKLIST["criteria"]:
            cid = criterion["criterion_id"]
            yes = [round(r[3][0][0], 2) for r in items if r[1] == cid and r[2]["status"] == "met" and r[3]]
            no = [round(r[3][0][0], 2) for r in items if r[1] == cid and r[2]["status"] != "met" and r[3]]
            print(f"  {cid[-3:]}  met {sorted(yes)}  not {sorted(no)}")
    if args.show:
        for name, cid, gold, ranked, case_id in rows:
            if name == "usgs" and ranked:
                print(f"{case_id} {cid[-3:]} {gold['status'][:5]} gold {sorted(gold.get('pages', []))}: "
                      + " | ".join(f"{s:.2f} p{c.page}" for s, c in ranked[:3]) + f" :: {ranked[0][1].text[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
