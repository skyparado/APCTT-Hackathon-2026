"""TRL decision logic (Task 13).

Turns evidence sentences into a TRL, or an abstention with a reason, following
team/TRL_CHEATSHEET.md:

  * `level_cues(sentence)` reads one sentence and returns the TRL levels it is evidence for,
    using the cheat-sheet keywords. Sentences that only claim a TRL ("reached TRL 6"),
    describe plans ("will be tested") or report failures never count.
  * `decide(sentences, target_type)` takes the highest level with real evidence (higher
    evidence implies the lower levels), applies the weakest-link cap, and abstains only when
    there is no build/test evidence at all or the scope is ambiguous.

Scoring (PROBLEM_DESCRIPTION 13.2) shapes the rules: exact 1.0, off by one 0.5, abstain 0.25,
off by two 0. So between two neighbouring levels we always pick one rather than abstain.

Standard library only: this ships inside the submission.

    python -m participant_module.trl      # self-check, from the repo root
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

# ponytail: keyword cues from the cheat-sheet, a baseline the criterion judge (Task 11) can
# replace or feed with NLI scores; extend these lists from labelled-case misses, not by guessing.
_CUES: dict[int, tuple[str, ...]] = {
    1: (r"basic principles?", r"phenomenon was observed", r"theoretical (basis|study)"),
    2: (r"\bconcept(ual)? (study|design)\b", r"\bfeasibility\b", r"\btrade stud", r"architecture was developed",
        r"algorithmically feasible", r"\b(calculated|estimated|modell?ed|simulated)\b", r"\bdesigned a\b"),
    3: (r"proof[- ]of[- ]concept", r"laboratory experiment", r"bench(top)? test", r"\bfabricated\b",
        r"\bsurrogate\b", r"\bwas tested\b"),
    4: (r"\bbreadboard\b", r"\bin the lab(oratory)?\b", r"\bcomponent test", r"tensile strength",
        r"\bproof[- ]?test", r"times the expected load", r"\bsubscale\b"),
    5: (r"thermal[- ]vacuum (test|chamber|testing)", r"\b(random )?vibration (test|testing|tests)\b",
        r"random vibration", r"relevant environment", r"qualification-level",
        r"environmental test", r"representative of anticipated mission"),
    # A named unit only counts when the sentence also says it was tested.
    6: (r"proto-?flight", r"engineering (development|model) unit\b.*\btest", r"flight[- ]sized",
        r"system[- ]level test", r"prototype (was )?demonstrated"),
    7: (r"\bflight test(s|ed|ing)?\b(?! aircraft model)", r"\bflight trials?\b", r"\bon-orbit\b",
        r"real world (operations|environment)", r"operational environment", r"international space station",
        r"\baltitude of\b"),
    8: (r"flight[- ]qualified", r"qualification (testing|program) (was )?(completed|passed)", r"\bcertified\b"),
    9: (r"mission mode", r"successful landing", r"continues to operate", r"\bin operational use\b"),
}
_CUE_RE = {level: re.compile("|".join(pats), re.IGNORECASE) for level, pats in _CUES.items()}

# A sentence whose content is a readiness claim is never evidence (PROBLEM_DESCRIPTION 13.4);
# manufacturing readiness levels (MRL) are claims too.
_TRL_CLAIM = re.compile(r"\b[TM]RLs?\b|readiness level", re.IGNORECASE)
# Intent, possibility, conditions and requirements describe what has not happened yet.
_NOT_DONE = re.compile(
    r"\b(will|shall|would|could|might|plans? to|planned|is planned|future work|aims? to|"
    r"intends? to|proposed|is possible|will be required|to be tested|if|in order to|potential)\b",
    re.IGNORECASE,
)
# Title blocks and running headers repeat the report number; they name things, never test them.
_FRONT_MATTER = re.compile(r"\bNASA/(TM|CR|TP|SP)\b")
_FAILED = re.compile(r"\b(failed|did not (meet|reach|pass)|was not achieved|shut down|anomal)", re.IGNORECASE)
# Heritage describes parts proven elsewhere, not the assessed target (cheat-sheet trap 4).
_HERITAGE = re.compile(r"\bheritage\b", re.IGNORECASE)

ABSTAIN_NO_EVIDENCE = "insufficient evidence"
ABSTAIN_SCOPE = "ambiguous scope"


def level_cues(sentence: str) -> set[int]:
    """TRL levels this sentence is evidence for; empty if it is a claim, a plan or a failure."""
    if (_TRL_CLAIM.search(sentence) or _NOT_DONE.search(sentence) or _FAILED.search(sentence)
            or _FRONT_MATTER.search(sentence)):
        return set()
    return {level for level, rx in _CUE_RE.items() if rx.search(sentence)}


@dataclass
class Decision:
    status: str  # "completed" or "abstained"
    predicted_trl: int | None
    abstention_reason: str | None
    trl_rationale: str
    confidence: float | None = None
    uncertainty: dict[str, Any] | None = None
    support: dict[int, list[str]] = field(default_factory=dict)  # level -> supporting sentences

    def result_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for output.build_result (support stays internal)."""
        kwargs: dict[str, Any] = {
            "status": self.status,
            "predicted_trl": self.predicted_trl,
            "abstention_reason": self.abstention_reason,
            "trl_rationale": self.trl_rationale,
        }
        if self.confidence is not None:
            kwargs["confidence"] = self.confidence
        if self.uncertainty is not None:
            kwargs["uncertainty"] = self.uncertainty
        return kwargs


def decide(
    sentences: Iterable[str],
    target_type: str,
    *,
    component_cap: int | None = None,
) -> Decision:
    """Pick a TRL from evidence sentences (best evidence anywhere in the case).

    `target_type` is the case's assessment_target.type. `component_cap` is the lowest TRL
    of the target's known parts, if the pipeline found one: a parent can never be rated
    above its weakest part (NASA AIST cookbook).
    """
    support: dict[int, list[str]] = {}
    heritage = False
    for sentence in sentences:
        heritage = heritage or bool(_HERITAGE.search(sentence))
        for level in level_cues(sentence):
            support.setdefault(level, []).append(sentence)

    if not support:
        return Decision("abstained", None, ABSTAIN_NO_EVIDENCE,
                        "No sentence describes something built, tested or demonstrated.")

    top = max(support)
    # A whole system designed around parts proven elsewhere, with nothing of its own beyond a
    # concept: the readiness depends on which part is assessed.
    if heritage and target_type == "system" and top <= 2:
        return Decision("abstained", None, ABSTAIN_SCOPE,
                        "Concept-level design of a system built from heritage parts; no single "
                        "technology was developed or tested.", support=support)

    trl = top if component_cap is None else min(top, component_cap)
    hits = len(support[top])
    # ponytail: confidence is a count heuristic, replace with judge scores once Task 11 exists.
    confidence = round(min(0.9, 0.45 + 0.15 * hits), 2)
    lower, upper = max(1, trl - 1), min(9, trl + 1)
    capped = f" Capped at TRL {trl} by its weakest part." if trl < top else ""
    rationale = (f"Highest level with direct evidence is TRL {top} "
                 f"({hits} supporting sentence{'s' if hits != 1 else ''}).{capped}")
    return Decision("completed", trl, None, rationale, confidence,
                    {"kind": "trl_interval", "lower": lower, "upper": upper}, support)


def score_a(decision: Decision, label: Mapping[str, Any]) -> float:
    """Part A score for one case against a labels.json dict (PROBLEM_DESCRIPTION 13.2)."""
    if label.get("assessment_status") == "abstained":
        if decision.status == "abstained":
            return 1.0 if decision.abstention_reason == label.get("abstention_reason") else 0.75
        return 0.0  # no expert interval in our labels, so a TRL counts as outside it
    if decision.status == "abstained":
        return 0.25
    diff = abs(decision.predicted_trl - label["trl"])
    return 1.0 if diff == 0 else 0.5 if diff == 1 else 0.0


def _self_check() -> None:
    # traps never count
    assert level_cues("Hence, the Thermal Loop technology has reached a TRL of 6.") == set()
    assert level_cues("The panel will be tested in a thermal vacuum chamber.") == set()
    assert level_cues("A proof-of-concept BALLET on Earth is possible with a moderately sized balloon.") == set()
    assert level_cues("The prototype failed to reach the target efficiency.") == set()
    assert level_cues("These materials offer vibration damping and noise mitigation.") == set()
    assert level_cues("The aircraft model in service in 2014 was conducive for such an implementation.") == set()
    assert level_cues("NASA/CR-2010-216682 Expandable Habitat Engineering Development Unit test report") == set()
    assert level_cues("To advance from proof-of-concept (MRL 3) to production (MRL 6), the process must be repeated.") == set()
    # real evidence does
    assert 5 in level_cues("The unit was tested in a thermal vacuum chamber from -40 C to +85 C.")
    assert 7 in level_cues("Flight 7 successfully demonstrated the link out to a range of 160 miles at an altitude of 35,000 feet.")
    assert 9 in level_cues("The instrument began operating in mission mode August 25.")

    d = decide(["A breadboard was built and run in the laboratory.",
                "The proto-flight unit demonstrated successful start-up in thermal vacuum."], "subsystem")
    assert (d.status, d.predicted_trl) == ("completed", 6), d
    u = d.result_kwargs()["uncertainty"]
    assert u["lower"] <= d.predicted_trl <= u["upper"]
    assert decide(["It reached TRL 6.", "Testing is planned for 2027."], "system").abstention_reason == ABSTAIN_NO_EVIDENCE
    assert decide(["The breadboard was integrated in the lab."], "system", component_cap=3).predicted_trl == 3
    scope = decide(["We designed a spacecraft using high heritage components."], "system")
    assert scope.abstention_reason == ABSTAIN_SCOPE, scope

    assert score_a(d, {"assessment_status": "completed", "trl": 6}) == 1.0
    assert score_a(d, {"assessment_status": "completed", "trl": 5}) == 0.5
    assert score_a(scope, {"assessment_status": "completed", "trl": 2}) == 0.25
    assert score_a(scope, {"assessment_status": "abstained", "abstention_reason": "ambiguous scope"}) == 1.0
    print("trl self-check ok")


if __name__ == "__main__":
    _self_check()
