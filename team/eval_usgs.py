"""Evaluate module TRL decisions against public USGS estimated TRLs.

Run from the repository root with ``~/apctt-env/bin/python team/eval_usgs.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from participant_module.adapter import _read_pages, _sentences  # noqa: E402
from participant_module.trl import Decision, decide, score_a  # noqa: E402

DEFAULT_PDF_DIR = Path.home() / "public_cases" / "pdf"
PUBLIC_CASES_TOOL = (
    Path.home()
    / "kit05"
    / "apctt-participant-kit-0.5.0-cpu"
    / "tools"
    / "get_public_cases.py"
)
LABEL_LINE = re.compile(r"^(USGS-SDG-\d{3})\s+TRL\s+([1-9])\s+(.+?)\s*$")
CSV_PATH = ROOT / "team" / "out" / "usgs_results.csv"
CSV_FIELDS = (
    "case_id",
    "title",
    "estimated_trl",
    "predicted_trl",
    "status",
    "abstention_reason",
    "part_a",
    "runtime_seconds",
    "error",
)


def _run_public_cases(*args: str) -> str:
    python = Path.home() / "apctt-env" / "bin" / "python"
    completed = subprocess.run(
        [str(python), str(PUBLIC_CASES_TOOL), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _load_labels() -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    for line in _run_public_cases("--labels").splitlines():
        match = LABEL_LINE.match(line)
        if match:
            case_id, estimated, rationale = match.groups()
            labels[case_id] = {
                "estimated_trl": int(estimated),
                "rationale": rationale,
            }
    if not labels:
        raise RuntimeError("The public-case tool returned no parseable TRL labels.")
    return labels


def _load_case_metadata() -> dict[str, dict[str, Any]]:
    payload = json.loads(_run_public_cases("--list", "--json"))
    cases = payload.get("cases", [])
    metadata = {
        case["case_id"]: case
        for case in cases
        if isinstance(case, dict) and case.get("case_id")
    }
    if not metadata:
        raise RuntimeError("The public-case tool returned no case metadata.")
    return metadata


def _score(prediction: int | None, abstained: bool, estimated: int) -> float:
    decision = (
        Decision("abstained", None, "insufficient evidence", "")
        if abstained
        else Decision("completed", prediction, None, "")
    )
    return score_a(
        decision,
        {"assessment_status": "completed", "trl": estimated},
    )


def _run_case(
    case_id: str,
    metadata: dict[str, Any],
    pdf_path: Path,
) -> tuple[Decision, float, str | None]:
    started = time.monotonic()
    pages_by_sentence: dict[str, tuple[str, int]] = {}
    error: str | None = None
    try:
        import pypdfium2

        pages = _read_pages(pypdfium2, str(pdf_path))
        for page_number, page_text in enumerate(pages, start=1):
            for sentence in _sentences(page_text):
                pages_by_sentence.setdefault(sentence, ("D001", page_number))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    target_type = str(metadata.get("type", ""))
    decision = decide(pages_by_sentence, target_type)
    return decision, time.monotonic() - started, error


def _format_prediction(decision: Decision) -> str:
    if decision.status == "completed":
        return f"TRL {decision.predicted_trl}"
    return f"abstain ({decision.abstention_reason})"


def _baseline_mean(rows: list[dict[str, Any]], prediction: int | None) -> float:
    if not rows:
        return 0.0
    abstained = prediction is None
    return sum(
        _score(prediction, abstained, row["estimated_trl"]) for row in rows
    ) / len(rows)


def _write_csv(rows: list[dict[str, Any]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help=f"directory containing USGS-SDG-*.pdf files (default: {DEFAULT_PDF_DIR})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="evaluate a random sample of at most N available PDFs",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="random seed used with --limit (default: 42)",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    try:
        labels = _load_labels()
        metadata = _load_case_metadata()
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"Unable to load USGS labels or case metadata: {exc}", file=sys.stderr)
        return 2

    available = [
        case_id
        for case_id in sorted(labels)
        if (args.pdf_dir / f"{case_id}.pdf").is_file()
    ]
    if args.limit is not None and args.limit < len(available):
        available = sorted(random.Random(args.seed).sample(available, args.limit))
    skipped = len(labels) - len(available)

    rows: list[dict[str, Any]] = []
    print(f"Evaluating {len(available)} cases; skipped without PDF: {skipped}")
    for case_id in available:
        label = labels[case_id]
        case_meta = metadata.get(case_id, {})
        decision, elapsed, error = _run_case(
            case_id,
            case_meta,
            args.pdf_dir / f"{case_id}.pdf",
        )
        prediction = decision.predicted_trl if decision.status == "completed" else None
        estimated = label["estimated_trl"]
        part_a = _score(prediction, decision.status != "completed", estimated)
        rows.append(
            {
                "case_id": case_id,
                "title": case_meta.get("title", ""),
                "estimated_trl": estimated,
                "predicted_trl": prediction,
                "status": decision.status,
                "abstention_reason": decision.abstention_reason,
                "part_a": part_a,
                "runtime_seconds": elapsed,
                "error": error,
                "decision": decision,
            }
        )
        print(
            f"{case_id}: predicted={_format_prediction(decision)} "
            f"estimated=TRL {estimated} A={part_a:.2f} runtime={elapsed:.2f}s"
            + (f" error={error}" if error else "")
        )

    count = len(rows)
    module_mean = sum(row["part_a"] for row in rows) / count if count else 0.0
    print("\nPart A mean:")
    print(f"  our module:       {module_mean:.3f}")
    print(f"  always-6:         {_baseline_mean(rows, 6):.3f}")
    print(f"  always-7:         {_baseline_mean(rows, 7):.3f}")
    print(f"  always-abstain:   {_baseline_mean(rows, None):.3f}")

    estimated_levels = sorted({row["estimated_trl"] for row in rows})
    prediction_levels = sorted(
        {row["predicted_trl"] for row in rows if row["predicted_trl"] is not None}
    )
    prediction_columns = [f"TRL {level}" for level in prediction_levels] + ["abstain"]
    print("\nConfusion table (rows=estimated, columns=predicted):")
    print(f"{'estimated':>12} " + " ".join(f"{column:>9}" for column in prediction_columns))
    for estimated in estimated_levels:
        counts = {
            level: sum(
                row["estimated_trl"] == estimated and row["predicted_trl"] == level
                for row in rows
            )
            for level in prediction_levels
        }
        abstentions = sum(
            row["estimated_trl"] == estimated and row["predicted_trl"] is None
            for row in rows
        )
        values = [counts[level] for level in prediction_levels] + [abstentions]
        print(f"{f'TRL {estimated}':>12} " + " ".join(f"{value:>9}" for value in values))

    abstentions = sum(row["predicted_trl"] is None for row in rows)
    slowest = max(rows, key=lambda row: row["runtime_seconds"], default=None)
    print(f"\nAbstentions: {abstentions}/{count}")
    if slowest:
        print(
            f"Slowest case: {slowest['case_id']} "
            f"({slowest['runtime_seconds']:.2f}s)"
        )

    worst = sorted(
        rows,
        key=lambda row: (
            row["part_a"],
            row["case_id"],
        ),
    )[:10]
    print("\n10 worst cases (id, predicted, estimated):")
    for row in worst:
        print(
            f"  {row['case_id']}, {_format_prediction(row['decision'])}, "
            f"TRL {row['estimated_trl']}"
        )

    _write_csv(rows)
    print(f"\nWrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
