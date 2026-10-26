"""Simple evidence-threshold TRL rules for applied-science reports."""

from __future__ import annotations

import re
from collections.abc import Iterable

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_REFERENCE_TERMS = re.compile(
    r"\b(?:references|bibliography|works cited|table of contents|contents)\b",
    re.IGNORECASE,
)
_REFERENCE_LINE = re.compile(
    r"^\s*(?:\[\d+\]|\(?\d{4}[a-z]?\)?(?:[.,:)]|\s))",
    re.IGNORECASE,
)
_FRONT_MATTER = re.compile(
    r"\b(?:report documentation page|abstract|disclaimer|acknowledg(?:e)?ments)\b",
    re.IGNORECASE,
)
_PLAN = re.compile(
    r"\b(?:will|shall|would|could|might|future work|plans? to|planned|"
    r"proposed|intends? to|is expected to|should be|to be conducted)\b",
    re.IGNORECASE,
)
_TRL_CLAIM = re.compile(r"\bTRL\s*\d+\b|\btechnology readiness level\b", re.IGNORECASE)

_FIELD_SIGNALS: tuple[tuple[str, re.Pattern[str], int], ...] = (
    (
        "field campaigns",
        re.compile(r"\bfield campaign(?:s)?\b", re.IGNORECASE),
        2,
    ),
    (
        "field setting/data",
        re.compile(
            r"\b(?:in|at|from|across|within)\s+(?:the\s+)?field\b|"
            r"\bfield\s+(?:data|measurements?|observations?|sites?)\b",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        "collected over a date range",
        re.compile(
            r"\b(?:collected|measured|recorded|observed|monitored|surveyed)\b"
            r".{0,80}\b(?:from|between)\s+(?:19|20)\d{2}\b"
            r".{0,35}\b(?:to|through|and|until)\s+(?:19|20)\d{2}\b",
            re.IGNORECASE,
        ),
        2,
    ),
    (
        "continuous monitoring",
        re.compile(r"\bcontinuous(?:ly)?\s+monitor(?:ing|ed)?\b", re.IGNORECASE),
        2,
    ),
    (
        "streamgage",
        re.compile(r"\bstream[\s-]?gages?\b|\bgaging stations?\b", re.IGNORECASE),
        1,
    ),
    (
        "actual observations",
        re.compile(r"\bactual\s+(?:field\s+)?(?:data|measurements?|observations?)\b", re.IGNORECASE),
        1,
    ),
    (
        "operational use",
        re.compile(r"\boperational(?:ly)?\b|\bin\s+operation\b", re.IGNORECASE),
        3,
    ),
    (
        "agency use",
        re.compile(
            r"\b(?:used|adopted|implemented|applied)\s+by\b"
            r".{0,100}\b(?:agency|agencies|department|district|service|office|"
            r"USGS|FEMA|NOAA|NWS)\b",
            re.IGNORECASE,
        ),
        4,
    ),
)

_LOW_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "newly developed model/regression",
        re.compile(
            r"\b(?:developed|developing|development of|newly developed)\b"
            r".{0,100}\b(?:model|regression|method|approach)\b|"
            r"\b(?:model|regression|method|approach)\b.{0,100}"
            r"\b(?:developed|developing|development)\b",
            re.IGNORECASE,
        ),
    ),
    ("preliminary", re.compile(r"\bpreliminary\b", re.IGNORECASE)),
    ("exploratory", re.compile(r"\bexploratory\b", re.IGNORECASE)),
    ("proof of concept", re.compile(r"\bproof[- ]of[- ]concept\b", re.IGNORECASE)),
    (
        "limited samples",
        re.compile(r"\blimited\s+(?:number\s+of\s+)?(?:samples?|data|observations?)\b", re.IGNORECASE),
    ),
    (
        "weak fit statistic",
        re.compile(
            r"\b(?:poor|weak|low|unsatisfactory)\s+"
            r"(?:model\s+)?(?:fit|performance|correlation|accuracy|efficiency)\b|"
            r"\b(?:fit|performance|correlation|accuracy|efficiency)\s+"
            r"(?:was|is|remained|were)\s+(?:poor|weak|low|unsatisfactory)\b|"
            r"\b(?:R\s*(?:2|²)|NSE|Nash[- ]Sutcliffe(?:\s+efficiency)?)\s*"
            r"(?:=|of|was|is|below|less than)\s*0\.[0-5]\d*\b",
            re.IGNORECASE,
        ),
    ),
)


def _page_is_reference_or_front_matter(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    if _FRONT_MATTER.search("\n".join(lines[:8])):
        return True
    if _REFERENCE_TERMS.search(lines[0]):
        return True
    reference_lines = sum(bool(_REFERENCE_LINE.match(line)) for line in lines)
    return reference_lines / len(lines) > 0.4


def _usable_sentences(pages: Iterable[str]) -> list[str]:
    result: list[str] = []
    for page in pages:
        if not isinstance(page, str) or not page.strip() or _page_is_reference_or_front_matter(page):
            continue
        flat = " ".join(page.split())
        for sentence in _SENTENCE_SPLIT.split(flat):
            sentence = sentence.strip()
            if len(sentence) < 20 or _PLAN.search(sentence) or _TRL_CLAIM.search(sentence):
                continue
            result.append(sentence)
    return result


def inspect(pages: Iterable[str]) -> dict[str, object]:
    """Return usable-text status and fired 7/5 signal groups for evaluation."""
    page_texts = [page for page in pages if isinstance(page, str)]
    sentences = _usable_sentences(page_texts)
    fired_7 = [
        name
        for name, pattern, _weight in _FIELD_SIGNALS
        if any(pattern.search(sentence) for sentence in sentences)
    ]
    fired_5 = [
        name
        for name, pattern in _LOW_SIGNALS
        if any(pattern.search(sentence) for sentence in sentences)
    ]
    score_7 = sum(
        weight
        for _name, pattern, weight in _FIELD_SIGNALS
        if any(pattern.search(sentence) for sentence in sentences)
    )
    return {
        "has_text": any(page.strip() for page in page_texts),
        "signals_7": fired_7,
        "signals_5": fired_5,
        "score_7": score_7,
        "score_5": len(fired_5),
    }


def decide(
    pages: Iterable[str],
    *,
    threshold_7: int = 4,
    threshold_5: int = 2,
) -> tuple[int | None, float]:
    """Choose TRL 5, 6, or 7; return ``(None, 0)`` only when no text is extractable."""
    return decide_from_signals(
        inspect(pages),
        threshold_7=threshold_7,
        threshold_5=threshold_5,
    )


def decide_from_signals(
    signals: dict[str, object],
    *,
    threshold_7: float = 4,
    threshold_5: float = 2,
) -> tuple[int | None, float]:
    """Apply the same threshold rule to features already returned by :func:`inspect`."""
    if not signals["has_text"]:
        return None, 0.0

    score_7 = float(signals["score_7"])
    score_5 = float(signals["score_5"])
    if score_7 >= threshold_7:
        selected_score, threshold, trl = score_7, threshold_7, 7
    elif score_5 >= threshold_5:
        selected_score, threshold, trl = score_5, threshold_5, 5
    else:
        return 6, 0.5

    confidence = min(0.95, 0.6 + 0.1 * max(0, selected_score - threshold))
    return trl, round(confidence, 2)
