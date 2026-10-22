"""Unit tests for the output builder (Task 14) and time guard (Task 15).

Standard library only (unittest), so it runs anywhere the module runs, including the common
base environment. Run:  python -I team/test_module.py   (or: pytest team/test_module.py)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from participant_module import budget, output  # noqa: E402

CASE = {
    "schema_version": "apctt-pdf-example-v1",
    "checklist_version": "DEMO-CHECKLIST-NOT-OFFICIAL",
    "case_id": "DEMO-001",
    "assessment_target": {"target_id": "T001", "type": "component", "description": "x"},
    "documents": [{"document_id": "D001", "page_count": 2}],
}
VERSION = CASE["checklist_version"]
IDS = ["C1", "C2"]


class OutputBuilderTests(unittest.TestCase):
    def test_abstained_is_valid(self) -> None:
        result = output.abstained(CASE, VERSION, IDS)
        self.assertEqual(result["assessment_status"], "abstained")
        self.assertIsNone(result["predicted_trl"])
        self.assertEqual(set(result["criterion_status"]), set(IDS))
        self.assertEqual(set(result["evidence_reference"]), set(IDS))
        self.assertEqual(output.validate_local(result, CASE, IDS), [])

    def test_met_without_evidence_is_downgraded(self) -> None:
        result = output.build_result(
            CASE, VERSION, IDS, status="abstained",
            criterion_status={"C1": "met", "C2": "not met"},
            evidence_reference={"C1": [], "C2": []},
        )
        self.assertEqual(result["criterion_status"]["C1"], "insufficient evidence")
        self.assertTrue(result["missing_evidence"]["C1"].strip())
        self.assertEqual(output.validate_local(result, CASE, IDS), [])

    def test_out_of_range_and_bad_evidence_dropped(self) -> None:
        result = output.build_result(
            CASE, VERSION, IDS, status="abstained",
            criterion_status={"C1": "met", "C2": "insufficient evidence"},
            evidence_reference={
                "C1": [
                    {"document_id": "D001", "page": 1, "supporting_span": "ok"},
                    {"document_id": "D001", "page": 9},       # out of range -> dropped
                    {"document_id": "D999", "page": 1},       # unknown doc -> dropped
                    {"document_id": "D001", "page": 2, "supporting_span": "  "},  # blank span removed
                ],
                "C2": [],
            },
            missing_evidence={"C2": "nothing found"},
        )
        c1 = result["evidence_reference"]["C1"]
        self.assertEqual([(e["document_id"], e["page"]) for e in c1], [("D001", 1), ("D001", 2)])
        self.assertNotIn("supporting_span", c1[1])  # blank removed
        self.assertEqual(result["criterion_status"]["C1"], "met")
        self.assertEqual(output.validate_local(result, CASE, IDS), [])

    def test_completed_result(self) -> None:
        result = output.build_result(
            CASE, VERSION, IDS, status="completed", predicted_trl=4,
            criterion_status={"C1": "met", "C2": "not met"},
            evidence_reference={"C1": [{"document_id": "D001", "page": 1}], "C2": []},
            trl_rationale="lab test reported",
            confidence=0.6,
            uncertainty={"kind": "trl_interval", "lower": 3, "upper": 5},
        )
        self.assertEqual(result["predicted_trl"], 4)
        self.assertIsNone(result["abstention_reason"])
        self.assertEqual(result["confidence"], 0.6)
        self.assertEqual(output.validate_local(result, CASE, IDS), [])

    def test_failed_result_shape(self) -> None:
        result = output.failed(CASE, VERSION, "TEAM_X")
        self.assertEqual(result["assessment_status"], "failed")
        self.assertEqual(result["error_code"], "TEAM_X")
        self.assertEqual(result["criterion_status"], {})
        for field in output.OPTIONAL_FIELDS:
            self.assertNotIn(field, result)
        self.assertEqual(output.validate_local(result, CASE, IDS), [])

    def test_failed_requires_error_code(self) -> None:
        with self.assertRaises(output.ResultContractError):
            output.build_result(CASE, VERSION, (), status="failed", error_code="  ")

    def test_safe_result_catches_exception(self) -> None:
        def boom() -> dict:
            raise RuntimeError("kaboom")
        result = output.safe_result(boom, CASE, VERSION)
        self.assertEqual(result["assessment_status"], "failed")
        self.assertTrue(result["error_code"].strip())
        self.assertEqual(output.validate_local(result, CASE, IDS), [])

    def test_no_null_optional_fields(self) -> None:
        # Optional fields must be omitted, never null.
        result = output.abstained(CASE, VERSION, IDS)
        for field in output.OPTIONAL_FIELDS:
            self.assertNotIn(field, result)


class TimeGuardTests(unittest.TestCase):
    def _ctx(self, remaining: float) -> SimpleNamespace:
        return SimpleNamespace(time_budget_ms=180000, remaining_ms=lambda: remaining)

    def test_exhausted_and_have_ms(self) -> None:
        guard = budget.TimeGuard(self._ctx(20000), safety_ms=15000)
        self.assertFalse(guard.exhausted())
        self.assertTrue(guard.have_ms(4000))
        self.assertFalse(guard.have_ms(6000))

    def test_checkpoint_raises_when_low(self) -> None:
        guard = budget.TimeGuard(self._ctx(10000), safety_ms=15000)
        self.assertTrue(guard.exhausted())
        with self.assertRaises(budget.BudgetExceeded):
            guard.checkpoint("step")

    def test_falls_back_without_remaining_ms(self) -> None:
        guard = budget.TimeGuard(SimpleNamespace(time_budget_ms=180000), safety_ms=0)
        self.assertGreater(guard.remaining_ms(), 170000)

    def test_bad_clock_does_not_crash(self) -> None:
        def bad() -> float:
            raise ValueError("clock gone")
        guard = budget.TimeGuard(SimpleNamespace(time_budget_ms=180000, remaining_ms=bad))
        self.assertGreater(guard.remaining_ms(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
