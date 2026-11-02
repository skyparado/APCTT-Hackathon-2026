"""Evaluate BM25 page retrieval and quote validity against bundled labels.

Run from the repository root with ``python team/eval_retrieval.py``.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from participant_module.pages import read_pages  # noqa: E402
from participant_module.quotes import pick_quote, verify_quote  # noqa: E402
from participant_module.retrieval import BM25Index, rank_pages  # noqa: E402

DEV_DIR = ROOT / "data" / "cases"
HELDOUT_DIR = ROOT / "data" / "heldout"
CHECKLIST_PATH = ROOT / "contracts" / "checklist.demo.json"
_FRONT_MATTER_TERMS = re.compile(r"\b(?:references|bibliography|table\s+of\s+contents)\b", re.I)
_REFERENCE_LINE = re.compile(r"^\s*(?:\[\d+\]|\(?\d{4}[a-z]?\)?(?:[.,:)]|\s))", re.I)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _criterion_text(criterion_id: str, descriptions: dict[str, str]) -> str:
    return descriptions.get(criterion_id, criterion_id.replace("-", " "))


def _looks_like_references(page_text: str) -> bool:
    """Heuristically identify references, bibliography, contents, or citation pages."""
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return False

    if _FRONT_MATTER_TERMS.match(page_text.lstrip()):
        return True
    marked_lines = sum(bool(_FRONT_MATTER_TERMS.search(line)) for line in lines)
    if marked_lines / len(lines) > 0.4:
        return True
    reference_lines = sum(bool(_REFERENCE_LINE.match(line)) for line in lines)
    return reference_lines / len(lines) > 0.4


def _page_text(pages: Sequence[dict[str, Any]], document_id: Any, page_number: Any) -> str:
    return next(
        (
            str(page.get("text", ""))
            for page in pages
            if page.get("document_id") == document_id and page.get("page") == page_number
        ),
        "",
    )


def evaluate_case(
    case_dir: Path,
    descriptions: dict[str, str],
    verbose: bool = False,
) -> tuple[int, int, int, int, int, int, int, int, float]:
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
    misses_ranked_4_10 = misses_not_top10 = misses_ref_dominated = 0
    for criterion_id, gold in (labels.get("criteria") or {}).items():
        if gold.get("status") != "met":
            continue
        criterion_text = _criterion_text(criterion_id, descriptions)
        ranked = rank_pages(criterion_text, index, k=10)
        gold_pages = [
            (item.get("document_id"), item.get("page"))
            for item in gold.get("pages", [])
        ]
        ranked_pages = [(item["document_id"], item["page"]) for item in ranked]
        hit1 = bool(ranked_pages[:1] and set(ranked_pages[:1]).intersection(gold_pages))
        hit3 = bool(set(ranked_pages[:3]).intersection(gold_pages))
        met_count += 1
        top1_hits += int(hit1)
        top3_hits += int(hit3)
        if not hit3:
            gold_ranks = [
                (doc_id, page_no, ranked_pages.index((doc_id, page_no)) + 1
                 if (doc_id, page_no) in ranked_pages else None)
                for doc_id, page_no in gold_pages
            ]
            if any(rank is not None and 4 <= rank <= 10 for _, _, rank in gold_ranks):
                misses_ranked_4_10 += 1
            else:
                misses_not_top10 += 1

            top3 = ranked[:3]
            top3_reference_count = sum(
                _looks_like_references(_page_text(pages, item["document_id"], item["page"]))
                for item in top3
            )
            if top3 and top3_reference_count > len(top3) / 2:
                misses_ref_dominated += 1

            if verbose:
                print(f"    MISS {criterion_id}:")
                for doc_id, page_no, rank in gold_ranks:
                    rank_text = str(rank) if rank is not None else "not in top 10"
                    print(f"      gold page {doc_id} p.{page_no}: rank {rank_text}")
                    print(f"        text: {_page_text(pages, doc_id, page_no)[:150]!r}")
                rendered_top3 = ", ".join(
                    f"{item['document_id']} p.{item['page']} (score={item['score']:.4f})"
                    for item in top3
                ) or "(none)"
                print(f"      top-3: {rendered_top3}")
                print(
                    f"      reference/front-matter pages in top-3: "
                    f"{top3_reference_count}/{len(top3)}"
                )
                top1_text = (
                    _page_text(pages, ranked[0]["document_id"], ranked[0]["page"])
                    if ranked else ""
                )
                print(f"      top-1 text: {top1_text[:150]!r}")

        quote = None
        source_page = ""
        if ranked:
            source_page = _page_text(pages, ranked[0]["document_id"], ranked[0]["page"])
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
    return (
        met_count,
        top1_hits,
        top3_hits,
        quote_valid,
        quote_total,
        misses_ranked_4_10,
        misses_not_top10,
        misses_ref_dominated,
        elapsed,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--heldout",
        action="store_true",
        help="also evaluate data/heldout (dev cases are always evaluated)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print detailed diagnostics for every gold-met top-3 miss",
    )
    args = parser.parse_args()

    checklist = _load_json(CHECKLIST_PATH)
    descriptions = {
        item["criterion_id"]: item["description"]
        for item in checklist.get("criteria", [])
        if item.get("criterion_id") and item.get("description")
    }
    total_met = total_top1 = total_top3 = total_quote_valid = total_quote = 0
    total_misses_ranked_4_10 = total_misses_not_top10 = total_misses_ref_dominated = 0
    case_count = 0
    total_runtime = 0.0

    data_dirs = (DEV_DIR, HELDOUT_DIR) if args.heldout else (DEV_DIR,)
    for data_dir in data_dirs:
        for case_dir in sorted(path for path in data_dir.iterdir() if path.is_dir()):
            case_path, labels_path = case_dir / "case.json", case_dir / "labels.json"
            if not case_path.is_file() or not labels_path.is_file():
                continue
            case_count += 1
            print(f"{case_dir.parent.name}/{case_dir.name}")
            (
                met, top1, top3, quote_valid, quote_total,
                misses_ranked_4_10, misses_not_top10, misses_ref_dominated, elapsed,
            ) = evaluate_case(
                case_dir, descriptions, verbose=args.verbose
            )
            total_met += met
            total_top1 += top1
            total_top3 += top3
            total_quote_valid += quote_valid
            total_quote += quote_total
            total_misses_ranked_4_10 += misses_ranked_4_10
            total_misses_not_top10 += misses_not_top10
            total_misses_ref_dominated += misses_ref_dominated
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
    print(
        f"Top-3 misses: gold page ranked 4-10={total_misses_ranked_4_10}, "
        f"not in top 10={total_misses_not_top10}, "
        f"top-3 reference/front-matter dominated={total_misses_ref_dominated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
