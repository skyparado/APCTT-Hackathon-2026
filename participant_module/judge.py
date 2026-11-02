"""Criterion judge (Task 11): met or insufficient evidence for each checklist criterion.

For one criterion: BM25 narrows the case to candidate sentences (`retrieval.py`), a zero-shot
entailment model scores them against a plain statement of the criterion, and the criterion is
`met` when the best score clears its threshold. Evidence is real sentences from the page, best
first, so quotes can never be invented. Without the model (not in the store, or short of time)
every criterion stays `insufficient evidence`.

Criteria come from the checklist in `load()`. Statements are chosen from the description's text,
never its ID; an unknown criterion is judged on its own description.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from participant_module.retrieval import BM25Index
from participant_module.trl import level_is_claim_or_plan

MODEL_PATH = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0-c/bddf8c5411c34ac3565e16e04384fd68b2618dda"
CANDIDATES_PER_CRITERION = 12
MAX_EVIDENCE = 3
BATCH_SIZE = 16
DEFAULT_THRESHOLD = 0.5

_SENTENCE_END = re.compile(r"(?<!U\.S\.)(?<!et al\.)(?<!Fig\.)(?<![Nn]o\.)(?<!\b[A-Z]\.)(?<=[.!?])\s+(?=[A-Z0-9(])")
_LEVEL = re.compile(r"\(TRL (\d)\)")
_NOT_PROSE = re.compile(r"^(figure|table|plate|appendix|contents|photograph)\b|https?://|\bdoi\b|\.{4,}", re.IGNORECASE)
# Report furniture that can read like a claim: copyright notices, cover pages, running titles.
_BOILERPLATE = re.compile(
    r"public domain|copyrighted|reproduc(e|tion) of|prepared in cooperation|national technical information|"
    r"suggested citation|for more information|manuscript approved|does not constitute|as used in this report|"
    r"scientific investigations report \d|open-file report \d", re.IGNORECASE)
_REFERENCE_LINE = re.compile(r"\b(19|20)\d{2}[a-z]?[,.:]|\bdoi\b|https?://", re.IGNORECASE)
_REFERENCE_HEADING = re.compile(r"^\s*(references( cited)?|bibliography|selected references)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Profile:
    query: str  # extra BM25 terms: reports say "calibrated", the checklist says "validated"
    statement: str  # what the entailment model checks each candidate sentence against
    threshold: float = DEFAULT_THRESHOLD


# Thresholds come from data/public_criteria_labels.json and data/cases (team/eval_judge.py). A
# missed `met` costs twice a wrong one in Part B and a wrong one loses nothing in Part C unless the
# quote is invented, which it cannot be here, so they sit well below "certain".
# The experts read the hardware words of C04-C09 by analogy for models and data products
# (PROBLEM_DESCRIPTION 5.1), so the statements and query terms do too.
_LEVEL_PROFILES: dict[int, Profile] = {
    1: Profile("principle theory equation based previous studies literature physical process",
               "The text states the scientific principles or earlier studies that the method is based on.", 0.5),
    2: Profile("purpose objective application used to approach method designed intended provide",
               "The text explains the purpose of the method or what it is used for.", 0.5),
    3: Profile("analysis results demonstrate showed laboratory experiment analytical regression statistical",
               "The analysis results show how well the method or model performs.", 0.3),
    4: Profile("laboratory bench controlled experiment tested initial version calibrated test results",
               "An early version of the method, model or component was tested in a laboratory or controlled setting.", 0.8),
    5: Profile("field conditions simulated validated verification calibration observed site tested realistic",
               "The model or method was calibrated or tested against field observations.", 0.85),
    6: Profile("model calibrated validated applied study area demonstrated observed streamgage flood event survey",
               "The model or method was applied to and tested on a real site with observed data.", 0.45),
    7: Profile("operational deployed field campaign monitoring network real-time collected survey installed",
               "The system or method was deployed and used in the field under real operating conditions.", 0.55),
    8: Profile("final system completed qualified certified requirements acceptance approved published release",
               "The final system was completed and qualified through tests against its requirements.", 0.6),
    9: Profile("operational use years decades ongoing routinely agencies used maintained continuously since",
               "The system has been in routine operational use for years.", 0.7),
}
_CROSS_PROFILES: tuple[tuple[str, Profile], ...] = (
    ("against requirements", Profile("requirement criteria standard target accuracy met within error compared acceptable",
                                     "Measured performance was compared with stated requirements or acceptance criteria.", 0.7)),
    ("test article", Profile("conditions configuration instrument equipment setup resolution method sampled tested",
                             "The text describes how the measurements or tests were carried out and what equipment was used.", 0.5)),
)
_TARGET_STATEMENT = "This text is about {target}."


@dataclass
class Sentence:
    document_id: str
    page: int
    text: str


@dataclass
class Judgement:
    status: str
    score: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)


def _is_reference_page(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    if _REFERENCE_HEADING.search(text):
        return True
    return sum(bool(_REFERENCE_LINE.search(line)) for line in lines) / len(lines) > 0.4


def _usable(sentence: str) -> bool:
    if not 40 <= len(sentence) <= 450 or _NOT_PROSE.search(sentence) or _BOILERPLATE.search(sentence):
        return False
    if sum(c.isalpha() or c.isspace() for c in sentence) / len(sentence) < 0.8:
        return False  # tables and number runs
    return not level_is_claim_or_plan(sentence)


def sentences_of(pages: Iterable[Mapping[str, Any]]) -> list[Sentence]:
    """Prose sentences of every page, from `pages.read_pages` records."""
    out: list[Sentence] = []
    seen: set[str] = set()
    for page in pages:
        text = str(page.get("text", ""))
        if _is_reference_page(text):
            continue
        flat = " ".join(text.replace(chr(0xFFFE), "-").split())  # pdfium's line-break hyphen
        for sentence in _SENTENCE_END.split(flat):
            if sentence not in seen and _usable(sentence):
                seen.add(sentence)
                out.append(Sentence(page["document_id"], page["page"], sentence))
    return out


def profile_for(description: str, target: str = "") -> Profile:
    level = _LEVEL.search(description)
    if level and int(level.group(1)) in _LEVEL_PROFILES:
        return _LEVEL_PROFILES[int(level.group(1))]
    lowered = description.lower()
    for marker, profile in _CROSS_PROFILES:
        if marker in lowered:
            return profile
    if "assessment target" in lowered and target:
        return Profile(target, _TARGET_STATEMENT.format(target=target))  # default threshold
    return Profile("", description)


def query_for(description: str, profile: Profile) -> str:
    # Not the target's name: it appears in every sentence that mentions the model and would win
    # every criterion. Only the assessment-target criterion searches on it, through its profile.
    return f"{description} {profile.statement} {profile.query}"


class SentenceSearch:
    """BM25 over a case's sentences; reused for all criteria of the case."""

    def __init__(self, sentences: Sequence[Sentence]) -> None:
        self.sentences = list(sentences)
        self._index = BM25Index([{"document_id": "s", "page": i, "text": s.text} for i, s in enumerate(self.sentences)])

    def candidates(self, query: str, k: int = CANDIDATES_PER_CRITERION) -> list[Sentence]:
        return [self.sentences[hit["page"]] for hit in self._index.rank(query, k=k)]


class Entailment:
    """The catalogue's zero-shot model, loaded once per case from the read-only store."""

    def __init__(self, directory: Path) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True)
        self._model = AutoModelForSequenceClassification.from_pretrained(str(directory), local_files_only=True)
        self._model.eval()
        labels = {name.lower(): index for index, name in self._model.config.id2label.items()}
        self._entailment = labels["entailment"]

    def score(self, premises: Sequence[str], hypothesis: str) -> list[float]:
        scores: list[float] = []
        for start in range(0, len(premises), BATCH_SIZE):
            batch = list(premises[start:start + BATCH_SIZE])
            encoded = self._tokenizer(batch, [hypothesis] * len(batch), truncation=True, max_length=256,
                                      padding=True, return_tensors="pt")
            with self._torch.inference_mode():
                logits = self._model(**encoded).logits
            scores += self._torch.softmax(logits, dim=-1)[:, self._entailment].tolist()
        return scores


def load_entailment() -> Entailment | None:
    """The model when the store has it; None means judge nothing rather than fail the case."""
    store = os.environ.get("APCTT_MODEL_STORE")
    if not store or not (Path(store) / MODEL_PATH).is_dir():
        return None
    return Entailment(Path(store) / MODEL_PATH)


def judge_criterion(search: SentenceSearch, model: Entailment, description: str, target: str) -> Judgement:
    profile = profile_for(description, target)
    candidates = search.candidates(query_for(description, profile))
    if not candidates:
        return Judgement("insufficient evidence")
    scores = model.score([c.text for c in candidates], profile.statement)
    ranked = sorted(zip(scores, candidates), key=lambda pair: -pair[0])
    evidence: list[dict[str, Any]] = []
    pages: set[tuple[str, int]] = set()
    for score, sentence in ranked:
        key = (sentence.document_id, sentence.page)
        if score >= profile.threshold and key not in pages and len(evidence) < MAX_EVIDENCE:
            pages.add(key)
            evidence.append({"document_id": sentence.document_id, "page": sentence.page,
                             "supporting_span": sentence.text})
    return Judgement("met" if evidence else "insufficient evidence", ranked[0][0], evidence)


def judge_case(records: Iterable[Mapping[str, Any]], criteria: Sequence[Mapping[str, str]], model: Entailment,
               target: str, keep_going: Callable[[float], bool]) -> dict[str, Judgement]:
    """Judge every criterion; `keep_going(seconds_of_last_step)` False stops, leaving the rest unjudged."""
    search = SentenceSearch(sentences_of(records))
    judgements: dict[str, Judgement] = {}
    last = 0.0
    for criterion in criteria:
        if not keep_going(last):
            break
        start = time.monotonic()
        judgements[criterion["criterion_id"]] = judge_criterion(search, model, criterion["description"], target)
        last = time.monotonic() - start
    return judgements
