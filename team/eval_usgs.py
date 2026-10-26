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

from participant_module.adapter import _read_pages  # noqa: E402
from participant_module.trl import Decision, score_a  # noqa: E402
from participant_module.trl_usgs import decide_from_signals, inspect  # noqa: E402

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
    "confidence",
    "fold",
    "signals_7",
    "signals_5",
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
    pdf_path: Path,
) -> tuple[list[str], float, str | None]:
    started = time.monotonic()
    error: str | None = None
    pages: list[str] = []
    try:
        import pypdfium2

        pages = _read_pages(pypdfium2, str(pdf_path))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    return pages, time.monotonic() - started, error


def _predict(features: dict[str, Any], threshold_7: int, threshold_5: int) -> int | None:
    return decide_from_signals(
        features,
        threshold_7=threshold_7,
        threshold_5=threshold_5,
    )[0]


def _baseline_mean(rows: list[dict[str, Any]], prediction: int | None) -> float:
    if not rows:
        return 0.0
    abstained = prediction is None
    return sum(
        _score(prediction, abstained, row["estimated_trl"]) for row in rows
    ) / len(rows)


def _tune_thresholds(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    if not rows:
        raise RuntimeError("No tuning-fold cases are available.")
    threshold_7_options = sorted({1, *(row["features"]["score_7"] + 1 for row in rows)})
    threshold_5_options = sorted({1, *(row["features"]["score_5"] + 1 for row in rows)})
    best_key: tuple[float, int, int] | None = None
    best_thresholds: tuple[int, int] | None = None
    for threshold_7 in threshold_7_options:
        for threshold_5 in threshold_5_options:
            mean = sum(
                _score(
                    _predict(row["features"], threshold_7, threshold_5),
                    not row["features"]["has_text"],
                    row["estimated_trl"],
                )
                for row in rows
            ) / len(rows)
            # Prefer stricter thresholds if training-fold scores tie.
            key = (mean, threshold_7 + threshold_5, threshold_7)
            if best_key is None or key > best_key:
                best_key = key
                best_thresholds = (threshold_7, threshold_5)
    if best_key is None or best_thresholds is None:
        raise RuntimeError("Could not tune signal thresholds.")
    return best_thresholds[0], best_thresholds[1], best_key[0]


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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print the fired TRL 7 and TRL 5 signal groups for every case",
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

    pdf_cases = [
        case_id
        for case_id in sorted(labels)
        if (args.pdf_dir / f"{case_id}.pdf").is_file()
    ]
    skipped = len(labels) - len(pdf_cases)
    available = pdf_cases
    if args.limit is not None and args.limit < len(pdf_cases):
        available = sorted(random.Random(args.seed).sample(pdf_cases, args.limit))

    rows: list[dict[str, Any]] = []
    print(
        f"Evaluating {len(available)} cases from {len(pdf_cases)} available PDFs; "
        f"skipped without PDF: {skipped}"
    )
    for case_id in available:
        label = labels[case_id]
        case_meta = metadata.get(case_id, {})
        pages, elapsed, error = _run_case(
            args.pdf_dir / f"{case_id}.pdf",
        )
        features = inspect(pages)
        case_number = int(case_id.rsplit("-", 1)[1])
        estimated = label["estimated_trl"]
        rows.append(
            {
                "case_id": case_id,
                "title": case_meta.get("title", ""),
                "estimated_trl": estimated,
                "case_number": case_number,
                "fold": "odd" if case_number % 2 else "even",
                "features": features,
                "runtime_seconds": elapsed,
                "error": error,
            }
        )

    tuning_rows = [row for row in rows if row["fold"] == "odd"]
    heldout_rows = [row for row in rows if row["fold"] == "even"]
    if not tuning_rows or not heldout_rows:
        print(
            "Evaluation needs at least one available odd-numbered tuning case "
            "and one even-numbered held-out case.",
            file=sys.stderr,
        )
        return 2
    threshold_7, threshold_5, tuning_a = _tune_thresholds(tuning_rows)
    print(
        f"Tuning fold: odd cases (n={len(tuning_rows)}); held-out fold: "
        f"even cases (n={len(heldout_rows)})"
    )
    print(
        f"Selected thresholds from odd fold: TRL 7 >= {threshold_7:g} field "
        f"evidence score; TRL 5 >= {threshold_5:g} low-readiness signal groups "
        f"(training mean A={tuning_a:.3f})"
    )

    for row in rows:
        features = row["features"]
        prediction = _predict(features, threshold_7, threshold_5)
        abstained = not features["has_text"]
        row["predicted_trl"] = prediction
        row["status"] = "abstained" if abstained else "completed"
        row["abstention_reason"] = "insufficient evidence" if abstained else ""
        row["confidence"] = decide_from_signals(
            features,
            threshold_7=threshold_7,
            threshold_5=threshold_5,
        )[1]
        row["part_a"] = _score(prediction, abstained, row["estimated_trl"])
        row["signals_7"] = features["signals_7"]
        row["signals_5"] = features["signals_5"]
        row["decision_text"] = (
            "abstain (insufficient evidence)" if abstained else f"TRL {prediction}"
        )
        if args.verbose:
            print(
                f"{row['case_id']} signals: TRL7={row['signals_7'] or 'none'}; "
                f"TRL5={row['signals_5'] or 'none'}"
            )
        print(
            f"{row['case_id']}: predicted={row['decision_text']} "
            f"estimated=TRL {row['estimated_trl']} A={row['part_a']:.2f} "
            f"runtime={row['runtime_seconds']:.2f}s"
            + (f" error={row['error']}" if row["error"] else "")
        )

    count = len(heldout_rows)
    module_mean = (
        sum(row["part_a"] for row in heldout_rows) / count if count else 0.0
    )
    print("\nPart A mean on held-out even fold:")
    print(f"  trl_usgs:         {module_mean:.3f}")
    print(f"  always-6:         {_baseline_mean(heldout_rows, 6):.3f}")

    estimated_levels = sorted({row["estimated_trl"] for row in heldout_rows})
    prediction_levels = sorted(
        {
            row["predicted_trl"]
            for row in heldout_rows
            if row["predicted_trl"] is not None
        }
    )
    prediction_columns = [f"TRL {level}" for level in prediction_levels] + ["abstain"]
    print("\nHeld-out confusion table (rows=estimated, columns=predicted):")
    print(f"{'estimated':>12} " + " ".join(f"{column:>9}" for column in prediction_columns))
    for estimated in estimated_levels:
        counts = {
            level: sum(
                row["estimated_trl"] == estimated
                and row["predicted_trl"] == level
                for row in heldout_rows
            )
            for level in prediction_levels
        }
        abstentions = sum(
            row["estimated_trl"] == estimated and row["predicted_trl"] is None
            for row in heldout_rows
        )
        values = [counts[level] for level in prediction_levels] + [abstentions]
        print(f"{f'TRL {estimated}':>12} " + " ".join(f"{value:>9}" for value in values))

    abstentions = sum(row["predicted_trl"] is None for row in heldout_rows)
    slowest = max(heldout_rows, key=lambda row: row["runtime_seconds"], default=None)
    print(f"\nHeld-out abstentions: {abstentions}/{count}")
    if slowest:
        print(
            f"Slowest case: {slowest['case_id']} "
            f"({slowest['runtime_seconds']:.2f}s)"
        )

    worst = sorted(
        heldout_rows,
        key=lambda row: (
            row["part_a"],
            row["case_id"],
        ),
    )[:10]
    print("\n10 worst cases (id, predicted, estimated):")
    for row in worst:
        print(
            f"  {row['case_id']}, {row['decision_text']}, "
            f"TRL {row['estimated_trl']}"
        )

    _write_csv(
        [
            {
                **row,
                "signals_7": "; ".join(row["signals_7"]),
                "signals_5": "; ".join(row["signals_5"]),
            }
            for row in rows
        ]
    )
    print(f"\nWrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
