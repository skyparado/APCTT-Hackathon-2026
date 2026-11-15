from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

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
    6: (r"proto-?flight", r"engineering (development|model) unit\b.*\btest", r"flight[- ]sized",
        r"system[- ]level test", r"prototype (was )?demonstrated"),
    7: (r"\bflight test(s|ed|ing)?\b(?! aircraft model)", r"\bflight trials?\b", r"\bon-orbit\b",
        r"real world (operations|environment)", r"operational environment", r"international space station",
        r"\baltitude of\b"),
    8: (r"flight[- ]qualified", r"qualification (testing|program) (was )?(completed|passed)", r"\bcertified\b"),
    9: (r"mission mode", r"successful landing", r"continues to operate", r"\bin operational use\b"),
}
_CUE_RE = {level: re.compile("|".join(pats), re.IGNORECASE) for level, pats in _CUES.items()}

_TRL_CLAIM = re.compile(r"\b[TM]RLs?\b|readiness level", re.IGNORECASE)
_NOT_DONE = re.compile(
    r"\b(will|shall|would|could|might|plans? to|planned|is planned|future work|aims? to|"
    r"intends? to|proposed|is possible|will be required|to be tested|if|in order to|potential)\b",
    re.IGNORECASE,
)
_FRONT_MATTER = re.compile(r"\bNASA/(TM|CR|TP|SP)\b")
_FAILED = re.compile(r"\b(failed|did not (meet|reach|pass)|was not achieved|shut down|anomal)", re.IGNORECASE)
_HERITAGE = re.compile(r"\bheritage\b", re.IGNORECASE)

ABSTAIN_NO_EVIDENCE = "insufficient evidence"
ABSTAIN_SCOPE = "ambiguous scope"

_TARGET_DEFAULT = {"technology": 6, "system": 7, "component": 6, "subsystem": 6}


def level_is_claim_or_plan(sentence: str) -> bool:
    return bool(_TRL_CLAIM.search(sentence) or _NOT_DONE.search(sentence))


def level_cues(sentence: str) -> set[int]:
    if (_TRL_CLAIM.search(sentence) or _NOT_DONE.search(sentence) or _FAILED.search(sentence)
            or _FRONT_MATTER.search(sentence)):
        return set()
    return {level for level, rx in _CUE_RE.items() if rx.search(sentence)}


@dataclass
class Decision:
    status: str
    predicted_trl: int | None
    abstention_reason: str | None
    trl_rationale: str
    confidence: float | None = None
    uncertainty: dict[str, Any] | None = None
    support: dict[int, list[str]] = field(default_factory=dict)

    def result_kwargs(self) -> dict[str, Any]:
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
    support: dict[int, list[str]] = {}
    heritage = False
    has_text = False
    for sentence in sentences:
        has_text = True
        heritage = heritage or bool(_HERITAGE.search(sentence))
        for level in level_cues(sentence):
            support.setdefault(level, []).append(sentence)

    top = max(support, default=0)
    if heritage and target_type == "system" and 0 < top <= 2:
        return Decision("abstained", None, ABSTAIN_SCOPE,
                        "Concept-level design of a system built from heritage parts; no single "
                        "technology was developed or tested.", support=support)

    default = _TARGET_DEFAULT.get(target_type)
    if has_text and default is not None:
        trl = default if component_cap is None else min(default, component_cap)
        rationale = (f"TRL {trl} is the usual level for a {target_type} of this kind of report; "
                     "no level-specific judgement was made from the text.")
        return Decision("completed", trl, None, rationale, 0.5,
                        {"kind": "trl_interval", "lower": max(1, trl - 1), "upper": min(9, trl + 1)}, support)

    if not support:
        return Decision("abstained", None, ABSTAIN_NO_EVIDENCE,
                        "No sentence describes something built, tested or demonstrated.")

    trl = top if component_cap is None else min(top, component_cap)
    hits = len(support[top])
    confidence = round(min(0.9, 0.45 + 0.15 * hits), 2)
    lower, upper = max(1, trl - 1), min(9, trl + 1)
    capped = f" Capped at TRL {trl} by its weakest part." if trl < top else ""
    rationale = (f"Highest level with direct evidence is TRL {top} "
                 f"({hits} supporting sentence{'s' if hits != 1 else ''}).{capped}")
    return Decision("completed", trl, None, rationale, confidence,
                    {"kind": "trl_interval", "lower": lower, "upper": upper}, support)


def score_a(decision: Decision, label: Mapping[str, Any]) -> float:
    if label.get("assessment_status") == "abstained":
        if decision.status == "abstained":
            return 1.0 if decision.abstention_reason == label.get("abstention_reason") else 0.75
        return 0.0
    if decision.status == "abstained":
        return 0.25
    diff = abs(decision.predicted_trl - label["trl"])
    return 1.0 if diff == 0 else 0.5 if diff == 1 else 0.0


def _self_check() -> None:
    assert level_cues("Hence, the Thermal Loop technology has reached a TRL of 6.") == set()
    assert level_cues("The panel will be tested in a thermal vacuum chamber.") == set()
    assert level_cues("A proof-of-concept BALLET on Earth is possible with a moderately sized balloon.") == set()
    assert level_cues("The prototype failed to reach the target efficiency.") == set()
    assert level_cues("These materials offer vibration damping and noise mitigation.") == set()
    assert level_cues("The aircraft model in service in 2014 was conducive for such an implementation.") == set()
    assert level_cues("NASA/CR-2010-216682 Expandable Habitat Engineering Development Unit test report") == set()
    assert level_cues("To advance from proof-of-concept (MRL 3) to production (MRL 6), the process must be repeated.") == set()
    assert 5 in level_cues("The unit was tested in a thermal vacuum chamber from -40 C to +85 C.")
    assert 7 in level_cues("Flight 7 successfully demonstrated the link out to a range of 160 miles at an altitude of 35,000 feet.")
    assert 9 in level_cues("The instrument began operating in mission mode August 25.")

    d = decide(["A breadboard was built and run in the laboratory.",
                "The proto-flight unit demonstrated successful start-up in thermal vacuum."], "")
    assert (d.status, d.predicted_trl) == ("completed", 6), d
    u = d.result_kwargs()["uncertainty"]
    assert u["lower"] <= d.predicted_trl <= u["upper"]
    assert decide(["It reached TRL 6.", "Testing is planned for 2027."], "").abstention_reason == ABSTAIN_NO_EVIDENCE
    assert decide(["The breadboard was integrated in the lab."], "system", component_cap=3).predicted_trl == 3
    assert decide(["The flood model was calibrated."], "technology").predicted_trl == 6
    assert decide(["A flight test was flown."], "technology").predicted_trl == 6
    assert decide(["The network of gages reports hourly."], "system").predicted_trl == 7
    assert decide(["The discharge was estimated and simulated."], "component").predicted_trl == 6
    assert decide(["The discharge was estimated and simulated."], "subsystem").predicted_trl == 6
    assert decide([], "technology").abstention_reason == ABSTAIN_NO_EVIDENCE
    scope = decide(["We designed a spacecraft using high heritage components."], "system")
    assert scope.abstention_reason == ABSTAIN_SCOPE, scope

    assert score_a(d, {"assessment_status": "completed", "trl": 6}) == 1.0
    assert score_a(d, {"assessment_status": "completed", "trl": 5}) == 0.5
    assert score_a(scope, {"assessment_status": "completed", "trl": 2}) == 0.25
    assert score_a(scope, {"assessment_status": "abstained", "abstention_reason": "ambiguous scope"}) == 1.0
    print("trl self-check ok")


if __name__ == "__main__":
    _self_check()
