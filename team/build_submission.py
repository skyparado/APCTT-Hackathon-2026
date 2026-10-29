"""Build the Stage 1 submission folder and check it with the kit tools (Task 20, feeds Task 6).

    python3 team/build_submission.py                 # refresh declaration.json, assemble, licence check
    python3 team/build_submission.py --pack          # ...and pack the zip with make_submission.py
    python3 team/build_submission.py --kit ../kit05  # use the tools of another kit checkout

Steps:
  1. Regenerate `submission/declaration.json` from `submission/submission.json` (identity) and
     `data/sources.csv` (one data source per document) plus the fixed sources below. Never edit
     its `data_sources` by hand: add a row to `data/sources.csv` instead.
  2. Assemble `team/out/submission/` with exactly the five entries make_submission.py takes:
     participant_module/, assets/, submission.json, declaration.json, README.md.
  3. Run the kit's `tools/check_licenses.py --bundle` on it, and with --pack also
     `tools/make_submission.py`, which writes `team/out/<team>_submission.zip`.

Standard library only, so plain python3 works (no base environment needed).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMISSION = ROOT / "submission"
OUT = ROOT / "team" / "out"
BUNDLE = OUT / "submission"
CSV_FIELDS = ("source", "url", "version", "date", "role", "label_origin", "linked_project", "license")

# Sources that are not one row of data/sources.csv. Keep each entry true to what the team did.
FIXED_SOURCES = [
    {
        "source": "APCTT public sample cases (contracts/public-cases.json, USGS reports)",
        "version": "kit 0.5.0",
        "date": "2026-10-26",
        "role": "evaluation: TRL accuracy check of the module (team/eval_usgs.py); not used for training",
        "label_origin": "organizer's estimated TRL per report; not expert labels",
        "linked_project": "",
        "license": "U.S. public domain (USGS); some figures third-party, see the manifest's licence_note",
    },
    {
        "source": "NASA NPR 7123.1 and EU Horizon TRL definitions (TRL 1-9 descriptions)",
        "version": "as published",
        "date": "2026-10-24",
        "role": "rules: definitions behind team/TRL_CHEATSHEET.md and the keyword cues in participant_module/trl.py",
        "label_origin": "not applicable (no labels)",
        "linked_project": "",
        "license": "U.S. public domain (NASA); European Union, reuse authorised (Commission Decision 2011/833/EU)",
    },
]


def data_sources() -> list[dict[str, str]]:
    with (ROOT / "data" / "sources.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    sources = [{key: row[key] for key in CSV_FIELDS if row.get(key)} for row in rows]
    return sources + FIXED_SOURCES


def write_declaration(submission: dict) -> dict:
    declaration = {
        "declaration_version": "cache-kita-declaration-v1",
        "example_only": False,
        "team": submission["team"],
        "package_id": submission["package_id"],
        "package_version": submission["package_version"],
        "declared_package_sha256": None,
        "team_training": "no_team_training",
        "training": None,
        "data_sources": data_sources(),
        "inference_assets": {
            "source_code": "participant_module/ (package hash in declared_package_sha256)",
            "weights": [],
            "prompts_or_rules": [
                "participant_module/trl.py (TRL keyword cues, written by the team from team/TRL_CHEATSHEET.md)"
            ],
            "reference_assets": [],
            "dependency_declarations": [
                f"the common base environment ({submission['base_id']})",
                "no catalogue models (submission.json models[] is empty)",
            ],
        },
        "notes": (
            "No data is shipped in the package and nothing was trained: the NTRS reports and the public "
            "sample cases were only used to develop and check the rule-based module. Labels marked "
            "'draft by assistant, pending review' were drafted with an AI assistant and are reviewed by "
            "the team before they are relied on."
        ),
    }
    path = SUBMISSION / "declaration.json"
    path.write_text(json.dumps(declaration, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return declaration


def assemble() -> None:
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    BUNDLE.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "participant_module", BUNDLE / "participant_module", ignore=ignore)
    if (ROOT / "assets").is_dir():
        shutil.copytree(ROOT / "assets", BUNDLE / "assets", ignore=ignore)
    else:
        (BUNDLE / "assets").mkdir()
    for name in ("submission.json", "declaration.json", "README.md"):
        shutil.copy2(SUBMISSION / name, BUNDLE / name)


def run(kit: Path, *args: str) -> int:
    command = [sys.executable, *args]
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, cwd=kit).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kit", type=Path, default=ROOT, help="kit checkout whose tools/ to run")
    parser.add_argument("--pack", action="store_true", help="also pack the zip with make_submission.py")
    args = parser.parse_args()
    kit = args.kit.resolve()

    submission = json.loads((SUBMISSION / "submission.json").read_text(encoding="utf-8"))
    declaration = write_declaration(submission)
    print(f"declaration.json: {len(declaration['data_sources'])} data sources")
    assemble()
    print(f"assembled {BUNDLE.relative_to(ROOT)}")

    code = run(kit, "tools/check_licenses.py", "--bundle", str(BUNDLE))
    if args.pack:
        code = run(kit, "tools/make_submission.py", str(BUNDLE), "--output", str(OUT))
    return code


if __name__ == "__main__":
    sys.exit(main())
