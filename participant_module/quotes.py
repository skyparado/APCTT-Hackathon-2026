"""Select and verify concise evidence quotes from extracted page text."""

from __future__ import annotations

import re

from participant_module.retrieval import tokenize

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])(?:[\"')\]]*)\s+")
_TRL_ONLY = re.compile(
    r"^\W*(\w+\W+){0,8}TRL[\s-]*\d(\W+\w+){0,3}\W*$",
    re.IGNORECASE,
)
_MAX_QUOTE_LENGTH = 300


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        part = text[start:match.start()].strip()
        if part:
            sentences.append(part)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _short_window(sentence: str, query_terms: set[str]) -> str:
    if len(sentence) <= _MAX_QUOTE_LENGTH:
        return sentence
    token_spans = [
        (match.start(), match.end(), tokenize(match.group()))
        for match in re.finditer(r"[A-Za-z0-9]+", sentence)
    ]
    best_start = 0
    best_score = -1
    for token_start, _, _ in token_spans:
        end = min(len(sentence), token_start + _MAX_QUOTE_LENGTH)
        score = sum(
            1
            for start, finish, terms in token_spans
            if start >= token_start and finish <= end and query_terms.intersection(terms)
        )
        if score > best_score:
            best_start, best_score = token_start, score
    end = min(len(sentence), best_start + _MAX_QUOTE_LENGTH)
    return sentence[best_start:end].strip()


def pick_quote(page_text: str, criterion_text: str) -> str | None:
    """Return a high-overlap sentence (or exact substring) of at most ~300 chars."""
    query_terms = set(tokenize(criterion_text))
    if not query_terms:
        return None
    best_quote: str | None = None
    best_score = 0
    for sentence in _sentences(page_text):
        if _TRL_ONLY.fullmatch(sentence):
            continue
        overlap = query_terms.intersection(tokenize(sentence))
        if not overlap:
            continue
        score = len(overlap)
        if score > best_score:
            best_quote = _short_window(sentence, query_terms)
            best_score = score
    return best_quote


def verify_quote(quote: str, page_text: str) -> bool:
    """Check whether a quote occurs on a page, allowing whitespace normalization only."""
    normalized_quote = _normalized(quote)
    return bool(normalized_quote) and normalized_quote in _normalized(page_text)
