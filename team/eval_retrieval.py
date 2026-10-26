"""Evaluate BM25 page retrieval and quote validity against bundled labels.

Run from the repository root with ``python team/eval_retrieval.py``.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from participant_module.pages import read_pages  # noqa: E402
from participant_module.quotes import pick_quote, verify_quote  # noqa: E402
from participant_module.retrieval import BM25Index, rank_pages  # noqa: E402

DATA_DIRS = (ROOT / "data" / "cases", ROOT / "data" / "heldout")
CHECKLIST_PATH = ROOT / "contracts" / "checklist.demo.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _criterion_text(criterion_id: str, descriptions: dict[str, str]) -> str:
    return descriptions.get(criterion_id, criterion_id.replace("-", " "))


def evaluate_case(
    case_dir: Path,
    descriptions: dict[str, str],
) -> tuple[int, int, int, int, int, float]:
    start = time.monotonic()
    case = _load_json(case_dir / "case.json")
    labels = _load_json(case_dir / "labels.json")
    pages: list[dict[str, Any]] = []
    deadline = lambda: max(0.0, (start + 180.0 - time.monotonic()) * 1000.0)
    for document in case.get("documents", []):
        path = case_dir / str(document.get("file", ""))
        pages.extend(
            read_pages(
                {"document_id": document.get("document_id"), "path": str(path)},
                deadline=deadline,
            )
        )

    index = BM25Index(pages)
    print(f"  extracted_pages={len(pages)}")
    met_count = top1_hits = top3_hits = quote_valid = quote_total = 0
    for criterion_id, gold in (labels.get("criteria") or {}).items():
        if gold.get("status") != "met":
            continue
        criterion_text = _criterion_text(criterion_id, descriptions)
        ranked = rank_pages(criterion_text, index, k=5)
        gold_pages = {
            (item.get("document_id"), item.get("page"))
            for item in gold.get("pages", [])
        }
        ranked_pages = [(item["document_id"], item["page"]) for item in ranked]
        hit1 = bool(ranked_pages[:1] and set(ranked_pages[:1]).intersection(gold_pages))
        hit3 = bool(set(ranked_pages[:3]).intersection(gold_pages))
        met_count += 1
        top1_hits += int(hit1)
        top3_hits += int(hit3)

        quote = None
        source_page = ""
        if ranked:
            source_page = next(
                (
                    page["text"]
                    for page in pages
                    if (page["document_id"], page["page"])
                    == (ranked[0]["document_id"], ranked[0]["page"])
                ),
                "",
            )
            quote = pick_quote(source_page, criterion_text)
        quote_total += 1
        quote_is_valid = quote is not None and verify_quote(quote, source_page)
        quote_valid += int(quote_is_valid)

        print(
            f"  {criterion_id}: top1={'hit' if hit1 else 'miss'} "
            f"top3={'hit' if hit3 else 'miss'} quote="
            f"{'valid' if quote_is_valid else 'none/invalid'}"
        )

    elapsed = time.monotonic() - start
    return met_count, top1_hits, top3_hits, quote_valid, quote_total, elapsed


def main() -> int:
    checklist = _load_json(CHECKLIST_PATH)
    descriptions = {
        item["criterion_id"]: item["description"]
        for item in checklist.get("criteria", [])
        if item.get("criterion_id") and item.get("description")
    }
    total_met = total_top1 = total_top3 = total_quote_valid = total_quote = 0
    case_count = 0
    total_runtime = 0.0

    for data_dir in DATA_DIRS:
        for case_dir in sorted(path for path in data_dir.iterdir() if path.is_dir()):
            case_path, labels_path = case_dir / "case.json", case_dir / "labels.json"
            if not case_path.is_file() or not labels_path.is_file():
                continue
            case_count += 1
            print(f"{case_dir.parent.name}/{case_dir.name}")
            met, top1, top3, quote_valid, quote_total, elapsed = evaluate_case(
                case_dir, descriptions
            )
            total_met += met
            total_top1 += top1
            total_top3 += top3
            total_quote_valid += quote_valid
            total_quote += quote_total
            total_runtime += elapsed
            print(f"  runtime={elapsed:.2f}s")

    top1_rate = total_top1 / total_met if total_met else 0.0
    top3_rate = total_top3 / total_met if total_met else 0.0
    quote_rate = total_quote_valid / total_quote if total_quote else 0.0
    print(
        f"Overall: cases={case_count} gold_met={total_met} "
        f"top1={total_top1}/{total_met} ({top1_rate:.1%}) "
        f"top3={total_top3}/{total_met} ({top3_rate:.1%}) "
        f"quote_validity={total_quote_valid}/{total_quote} ({quote_rate:.1%}) "
        f"runtime={total_runtime:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
