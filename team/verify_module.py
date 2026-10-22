"""Check participant_module against the kit's own result validator (Task 3/5 helper).

Run from the kit's top-level directory:

    python -I team/verify_module.py

It validates our module's output with `apctt_contracts.results.validate_result` — the same
rules the server applies — on the DEMO checklist and on a synthetic checklist with different
IDs (to prove criterion IDs are read from load(), not hard-coded). An abstaining result carries
no evidence, so no PDF read is needed. Exit code is non-zero if any issue is found.

This does NOT replace a real server run: a direct call skips the time limit, the separate base
environment and process isolation (MODULE_GUIDE §6). Always finish with the server.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "src"))
sys.path.insert(0, str(KIT))

from apctt_contracts.config import Checklist  # noqa: E402
from apctt_contracts.results import validate_result  # noqa: E402
from participant_module import output  # noqa: E402
from participant_module.adapter import AssessmentModule  # noqa: E402


def check(checklist_json: dict, case: dict, label: str) -> int:
    config = {
        "checklist": {"version": checklist_json["version"], "criteria": checklist_json["criteria"]},
        "module": {"settings": {}},
        "compute": {"device": "cpu", "seed": 42},
    }
    module = AssessmentModule()
    module.load(config, KIT / "assets")
    context = SimpleNamespace(
        run_id="local", seed=42, time_budget_ms=180000,
        scratch_dir=KIT, remaining_ms=lambda: 180000.0,
    )
    result = module.assess(case, context)
    module.reset_case()
    module.close()

    issues = validate_result(result, case=case, checklist=Checklist.model_validate(checklist_json))
    print(f"\n=== {label} ===")
    print(f"assessment_status = {result['assessment_status']}")
    print(f"criterion_status  = {result['criterion_status']}")
    for issue in issues:
        print("  ISSUE:", issue.path, issue.rule)
    print(f"{len(issues)} issue(s)")
    return len(issues)


def main() -> int:
    request = json.loads((KIT / "docs/EXAMPLE_REQUEST.json").read_text())
    demo = json.loads((KIT / "contracts/checklist.demo.json").read_text())

    total = check(demo, copy.deepcopy(request["case"]), "DEMO checklist")

    alt = {
        "version": "OFFICIAL-TEST-1",
        "criteria": [
            {"criterion_id": "OFF-A1", "description": "Synthetic criterion A1."},
            {"criterion_id": "OFF-A2", "description": "Synthetic criterion A2."},
            {"criterion_id": "OFF-A3", "description": "Synthetic criterion A3."},
        ],
    }
    case_alt = copy.deepcopy(request["case"])
    case_alt["checklist_version"] = alt["version"]
    total += check(alt, case_alt, "Non-DEMO checklist (different IDs)")

    # Cross-check a COMPLETED result built by output.build_result against the kit's own
    # validate_result, so Task 14's builder is proven to emit server-valid non-abstain output.
    demo_ids = [c["criterion_id"] for c in demo["criteria"]]
    case_done = copy.deepcopy(request["case"])
    first_doc = case_done["documents"][0]["document_id"]
    completed = output.build_result(
        case_done, demo["version"], demo_ids, status="completed", predicted_trl=4,
        criterion_status={demo_ids[0]: "met", demo_ids[1]: "not met"},
        evidence_reference={
            demo_ids[0]: [{"document_id": first_doc, "page": 1, "supporting_span": "tested"}],
            demo_ids[1]: [],
        },
        trl_rationale="A laboratory test is reported.",
        confidence=0.6,
    )
    issues = validate_result(completed, case=case_done, checklist=Checklist.model_validate(demo))
    print("\n=== output.build_result -> completed (kit validator) ===")
    print(f"predicted_trl = {completed['predicted_trl']}, status = {completed['assessment_status']}")
    for issue in issues:
        print("  ISSUE:", issue.path, issue.rule)
    print(f"{len(issues)} issue(s)")
    total += len(issues)

    print(f"\nTOTAL ISSUES: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
