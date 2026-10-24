"""Score the TRL decision logic (Task 13) against our labelled cases (Task 8).

    python team/eval_trl.py          # from the repo root

For every data/cases/*/labels.json it runs participant_module.trl.decide twice:

  * gold    - only the label's own evidence quotes, i.e. perfect retrieval;
  * +traps  - the same quotes plus the trap sentences quoted in review_notes
              ("will be tested", "reached a TRL of 6", ...), which must not change the answer.

and prints the official part-A score (exact 1.0, off by one 0.5, abstain 0.25) next to the
always-abstain baseline. This measures the decision logic only; retrieval and the criterion
judge (Tasks 10-11) will lower it on real pages. Dev-only, never shipped.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from participant_module.trl import Decision, decide, score_a  # noqa: E402

TRAP_QUOTE = re.compile(r"'([^']{12,})'")


def show(d: Decision) -> str:
    return f"TRL {d.predicted_trl}" if d.status == "completed" else f"abstain ({d.abstention_reason})"


def main() -> int:
    rows = []
    for labels_path in sorted((ROOT / "data" / "cases").glob("*/labels.json")):
        label = json.loads(labels_path.read_text(encoding="utf-8"))
        case = json.loads((labels_path.parent / "case.json").read_text(encoding="utf-8"))
        target_type = case["assessment_target"]["type"]
        gold = [e["quote"] for e in label.get("evidence", [])]
        traps = TRAP_QUOTE.findall(label.get("review_notes", ""))
        d_gold = decide(gold, target_type)
        d_trap = decide(gold + traps, target_type)
        baseline = 1.0 if label["assessment_status"] == "abstained" else 0.25
        want = f"TRL {label['trl']}" if label["trl"] is not None else f"abstain ({label['abstention_reason']})"
        rows.append((label["case_id"], want, d_gold, score_a(d_gold, label), d_trap, score_a(d_trap, label),
                     baseline, len(traps)))

    print(f"{'case':18} {'label':28} {'gold':26} {'A':>4}  {'+traps':26} {'A':>4}  traps")
    for cid, want, dg, sg, dt, st, _, n in rows:
        flag = "" if sg == st else "  <- traps changed the answer"
        print(f"{cid:18} {want:28} {show(dg):26} {sg:4.2f}  {show(dt):26} {st:4.2f}  {n}{flag}")
    n = len(rows)
    mean = lambda i: sum(r[i] for r in rows) / n  # noqa: E731
    print(f"\nmean part A over {n} cases:  gold {mean(3):.3f}   +traps {mean(5):.3f}   "
          f"always-abstain baseline {mean(6):.3f}")
    exact = sum(1 for r in rows if r[3] == 1.0)
    print(f"exact matches (gold): {exact}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
