"""Part A of participant_module/trl.py on the public USGS cases (Task 13).

    ~/apctt-env/base/bin/python team/eval_public.py                  # odd cases: free to tune on
    ~/apctt-env/base/bin/python team/eval_public.py --fold even      # check only, never tune on it

The PDFs come from `tools/get_public_cases.py --download --all --dir ~/public_cases/pdf`. The labels
are the organizer's estimates, not expert labels (PROBLEM_DESCRIPTION 5.2): a sanity check. Runs
trl.decide directly, without the server. Dev-only, never shipped.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from participant_module import pages, trl  # noqa: E402
from participant_module.adapter import _sentences  # noqa: E402


def always(level: int, label: dict) -> float:
    return trl.score_a(SimpleNamespace(status="completed", predicted_trl=level), label)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fold", choices=("odd", "even", "all"), default="odd")
    parser.add_argument("--pdf-dir", type=Path, default=Path.home() / "public_cases" / "pdf")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "contracts" / "public-cases.json").read_text(encoding="utf-8"))
    remainder = {"odd": {1}, "even": {0}, "all": {0, 1}}[args.fold]
    rows = []
    for case in manifest["cases"]:
        case_id = case["case_id"]
        if int(case_id.rsplit("-", 1)[1]) % 2 not in remainder:
            continue
        start = time.monotonic()
        records = pages.read_pages({"document_id": "D001", "path": str(args.pdf_dir / f"{case_id}.pdf")})
        sentences = [s for record in records for s in _sentences(record["text"])]
        decision = trl.decide(sentences, case["assessment_target"]["type"])
        label = {"assessment_status": "completed", "trl": case["reference_labels"]["estimated_trl"]}
        rows.append((case_id, label, decision, trl.score_a(decision, label), time.monotonic() - start))

    count = len(rows)
    print(f"{args.fold} fold: {count} cases")
    print(f"  module    A = {sum(r[3] for r in rows) / count:.3f}")
    for level in (5, 6, 7):
        print(f"  always-{level}  A = {sum(always(level, r[1]) for r in rows) / count:.3f}")
    print(f"  exact     {sum(r[3] == 1.0 for r in rows)}/{count}, slowest {max(r[4] for r in rows):.1f} s")
    table = collections.Counter((r[1]["trl"], r[2].predicted_trl) for r in rows)
    print("  (estimated, predicted): " + ", ".join(f"{k}: {v}" for k, v in sorted(table.items(), key=str)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
