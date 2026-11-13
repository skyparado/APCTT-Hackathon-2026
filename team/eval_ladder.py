"""Does aligning criteria with the decided TRL raise Part B? Offline, without the server (dev-only).

    APCTT_MODEL_STORE=~/apctt-models ~/apctt-env/bin/python team/eval_ladder.py --pdf-dir ~/apctt-cases/pdf

The checklist has one criterion per TRL level, and the labels (USGS drafts and NASA) follow a ladder:
levels above the case's TRL are never met, levels at or below it mostly are. Policies compared, each
on the judge's verified candidates (the same quote check the module uses):
  base         judge.py thresholds, as shipped before this change
  cap          base, but a level above the decided TRL is never met
  cap+fill F   cap, and a level at or below the decided TRL is met when a verified candidate scores >= F
The decided TRL is what the module decides (trl.decide), not the label. B = (2 met + not) / 3, pooled.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team"))
from eval_judge import CHECKLIST, nasa_cases, public_cases  # noqa: E402
from participant_module import judge, pages, trl  # noqa: E402

LEVEL = re.compile(r"\(TRL (\d)\)")
FLOORS = (0.0, 0.02, 0.05, 0.1, 0.2, 0.3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf-dir", type=Path, default=Path.home() / "apctt-cases" / "pdf")
    args = parser.parse_args()
    model = judge.load_entailment()
    if model is None:
        print("no model: set APCTT_MODEL_STORE")
        return 2
    import json
    manifest = {c["case_id"]: c for c in json.loads((ROOT / "contracts" / "public-cases.json").read_text(encoding="utf-8"))["cases"]}
    rows = []  # (set, level or None, decided trl, gold, [(score, page)] verified, best first)
    cases = public_cases(args.pdf_dir, "odd") + public_cases(args.pdf_dir, "even") + nasa_cases()
    for case in cases:
        records = [r for doc, path in case["pdfs"] for r in pages.read_pages({"document_id": doc, "path": str(path)})]
        sentences = judge.sentences_of(records)
        if case["set"] == "usgs":
            target_type = manifest[case["id"]]["assessment_target"]["type"]
        else:
            target_type = json.loads((ROOT / "data" / "cases" / case["id"] / "case.json").read_text(encoding="utf-8"))["assessment_target"]["type"]
        decided = trl.decide([s.text for s in sentences], target_type).predicted_trl
        search = judge.SentenceSearch(sentences)
        for criterion in CHECKLIST["criteria"]:
            gold = case["gold"].get(criterion["criterion_id"])
            if gold is None:
                continue
            profile = judge.profile_for(criterion["description"], case["target"])
            candidates = search.candidates(judge.query_for(criterion["description"], profile))
            scores = model.score([c.text for c in candidates], profile.statement) if candidates else []
            verified = [(s, c.page) for s, c in sorted(zip(scores, candidates), key=lambda p: -p[0])
                        if judge._verified_span(c) is not None]
            level = LEVEL.search(criterion["description"])
            rows.append((case["set"], int(level.group(1)) if level else None, decided, gold, verified, profile.threshold))
        print(f"{case['id']:22} decided TRL {decided}", flush=True)

    def score(items, cap: bool, floor: float | None):
        met_hits = met_total = not_hits = not_total = claims = 0
        for _, level, decided, gold, verified, threshold in items:
            effective = threshold
            if level is not None and decided is not None:
                if cap and level > decided:
                    effective = float("inf")
                elif floor is not None and level <= decided:
                    effective = min(threshold, floor)
            said: list[int] = []
            for s, page in verified:
                if s >= effective and page not in said:
                    said.append(page)
            claims += bool(said)
            if gold["status"] == "met":
                met_total += 1
                met_hits += bool(said) and bool(set(said[:3]) & gold["pages"])
            else:
                not_total += 1
                not_hits += not said
        m = met_hits / met_total if met_total else 0.0
        n = not_hits / not_total if not_total else 0.0
        return (2 * m + n) / 3, m, met_total, n, not_total, claims

    for name in ("usgs", "nasa"):
        items = [r for r in rows if r[0] == name]
        print(f"\n{name}: policy -> B (met part of N, not-established part of N, met claims)")
        policies = [("base", False, None), ("cap", True, None)] + [(f"cap+fill {f}", True, f) for f in FLOORS]
        for label, cap, floor in policies:
            b, m, mt, n, nt, claims = score(items, cap, floor)
            print(f"  {label:14} B {b:.3f}  ({m:.2f} of {mt}, {n:.2f} of {nt}, {claims} claims)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
