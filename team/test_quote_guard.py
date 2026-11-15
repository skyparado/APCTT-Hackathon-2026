"""Tests for source-verified criterion evidence and page extraction time limits."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from participant_module import judge, output, pages  # noqa: E402


CASE = {
    "schema_version": "apctt-pdf-example-v1",
    "checklist_version": "TEST",
    "case_id": "TEST-001",
    "assessment_target": {"target_id": "T001", "type": "technology", "description": "test"},
    "documents": [{"document_id": "D001", "page_count": 1}],
}
CRITERION = "TRL 4 laboratory test"
PAGE_TEXT = "The instrument was tested in a laboratory under controlled thermal conditions."


class _Search:
    def __init__(self, candidate: judge.Sentence) -> None:
        self.candidate = candidate

    def candidates(self, _query: str) -> list[judge.Sentence]:
        return [self.candidate]


class _Model:
    def score(self, _premises: list[str], _hypothesis: str) -> list[float]:
        return [0.99]


class QuoteGuardTests(unittest.TestCase):
    def _judge(self, span: str, original: str = PAGE_TEXT) -> judge.Judgement:
        candidate = judge.Sentence("D001", 1, span, original)
        return judge.judge_criterion(_Search(candidate), _Model(), CRITERION, "test")

    def test_exact_quote_passes(self) -> None:
        result = self._judge(PAGE_TEXT)
        self.assertEqual(result.status, "met")
        self.assertEqual(result.evidence[0]["supporting_span"], PAGE_TEXT)

    def test_altered_quote_is_dropped(self) -> None:
        result = self._judge(
            "The instrument was tested in a laboratory under controlled electrical conditions."
        )
        self.assertEqual(result.status, "insufficient evidence")
        self.assertEqual(result.evidence, [])

    def test_met_without_verified_evidence_is_insufficient_with_note(self) -> None:
        judgement = self._judge(
            "The instrument was tested in a laboratory under controlled electrical conditions."
        )
        result = output.build_result(
            CASE,
            "TEST",
            ["C1"],
            status="abstained",
            criterion_status={"C1": judgement.status},
            evidence_reference={"C1": judgement.evidence},
            missing_evidence={"C1": "No verified evidence was found."},
            abstention_reason="insufficient evidence",
        )
        self.assertEqual(result["criterion_status"]["C1"], "insufficient evidence")
        self.assertEqual(result["evidence_reference"]["C1"], [])
        self.assertEqual(result["missing_evidence"]["C1"], "No verified evidence was found.")

    def test_pdfium_hyphen_is_quoted_as_printed(self) -> None:
        original = "The instrument was tested in a labora\ufffe\r\ntory under controlled thermal conditions."
        transformed = " ".join(original.replace("\ufffe", "-").split())
        result = self._judge(transformed, original)
        self.assertEqual(result.status, "met")
        self.assertEqual(result.evidence[0]["supporting_span"], transformed)
        self.assertNotIn("\ufffe", result.evidence[0]["supporting_span"])


class ReferenceEntryTests(unittest.TestCase):
    def test_reference_list_entries_are_never_evidence(self) -> None:
        # Real quotes from the public-case run of 2026-11-13.
        self.assertFalse(judge._usable("Guy, H.P., 1969, Laboratory theory and methods for sediment analysis: "
                                       "U.S. Geological Survey Techniques of Water Resources"))
        self.assertFalse(judge._usable("Smith, R.A., Alexander, R.B., and Schwartz, G.E., 2003, Natural background "
                                       "concentrations of nutrients in streams and rivers"))
        self.assertTrue(judge._usable("Duan smearing (Duan, 1983) was used to calculate a bias correction factor "
                                      "of 2.12 for equation 1 and is also provided for the other equations."))

    def test_table_of_contents_is_never_evidence(self) -> None:
        # Real quotes from the hard-case and public runs of 2026-11-13.
        self.assertFalse(judge._usable("Abstract... .1 Introduction. .1 Purpose and Scope of the flood study area."))
        self.assertFalse(judge._usable("iii Contents Abstract 1 Introduction 1 Methodology 2 Deep-water Waves and "
                                       "Storm Surges 2 Shallow-water Waves 2"))
        self.assertTrue(judge._usable("The soil water contents were measured at 12 sites and compared with the "
                                      "simulated values from the model."))


class AlignWithTrlTests(unittest.TestCase):
    def test_levels_follow_the_decided_trl(self) -> None:
        item = {"document_id": "D001", "page": 3, "supporting_span": "The model was calibrated."}
        criteria = [{"criterion_id": f"C{n}", "description": f"Level {n} (TRL {n}): text"} for n in (3, 6, 7)]
        criteria.append({"criterion_id": "C10", "description": "Quantified results against requirements: text"})
        judgements = {
            "C3": judge.Judgement("insufficient evidence", 0.1, [], [item]),  # below threshold -> met on fallback
            "C6": judge.Judgement("insufficient evidence", 0.0, [], []),      # nothing verified -> stays
            "C7": judge.Judgement("met", 0.9, [item], [item]),                # above the TRL -> never met
            "C10": judge.Judgement("insufficient evidence", 0.1, [], [item]),  # not a level -> untouched
        }
        judge.align_with_trl(judgements, criteria, 6)
        self.assertEqual((judgements["C3"].status, judgements["C3"].evidence), ("met", [item]))
        self.assertEqual(judgements["C6"].status, "insufficient evidence")
        self.assertEqual((judgements["C7"].status, judgements["C7"].evidence), ("insufficient evidence", []))
        self.assertEqual(judgements["C10"].status, "insufficient evidence")


class PageBudgetTests(unittest.TestCase):
    def test_stops_before_reading_page_when_less_than_sixty_seconds_remain(self) -> None:
        class FakeTextPage:
            def __init__(self, text: str) -> None:
                self.text = text

            def get_text_range(self) -> str:
                return self.text

            def close(self) -> None:
                pass

        class FakePage:
            def __init__(self, text: str) -> None:
                self.text = text

            def get_textpage(self) -> FakeTextPage:
                return FakeTextPage(self.text)

            def close(self) -> None:
                pass

        class FakePdf:
            def __init__(self, _path: str) -> None:
                self.items = [FakePage("Page one has enough extracted text."), FakePage("Page two text.")]

            def __len__(self) -> int:
                return len(self.items)

            def __getitem__(self, index: int) -> FakePage:
                return self.items[index]

            def close(self) -> None:
                pass

        clock = iter((61_000, 59_999))
        stderr = io.StringIO()
        with mock.patch.dict(sys.modules, {"pypdfium2": SimpleNamespace(PdfDocument=FakePdf)}):
            with contextlib.redirect_stderr(stderr):
                texts, cacheable = pages._read_pdf(Path("test.pdf"), lambda: next(clock))
        self.assertEqual(texts, ["Page one has enough extracted text."])
        self.assertFalse(cacheable)
        self.assertIn("less than 60 seconds remain", stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
