"""Small dependency-free BM25 page retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be been being by for from has have in into is it its "
    "of on or that the their this to was were will with".split()
)


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        token = token[:-3]
    elif len(token) > 4 and token.endswith("ed"):
        token = token[:-2]
    elif len(token) > 4 and token.endswith("es"):
        token = token[:-2]
    elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    if len(token) > 4 and token.endswith("ly"):
        token = token[:-2]
    return token


def tokenize(text: str) -> list[str]:
    """Lowercase, remove common stopwords, and apply light suffix stemming."""
    tokens = []
    for token in _TOKEN_RE.findall(text.lower()):
        if token not in _STOPWORDS:
            stemmed = _stem(token)
            if stemmed and stemmed not in _STOPWORDS:
                tokens.append(stemmed)
    return tokens


class BM25Index:
    """An immutable page index that can be reused for multiple criterion queries."""

    def __init__(self, pages: Sequence[dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> None:
        self.pages = list(pages)
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(str(page.get("text", ""))) for page in self.pages]
        self.term_frequencies = [Counter(tokens) for tokens in self.tokens]
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.document_frequency: Counter[str] = Counter()
        for tokens in self.tokens:
            self.document_frequency.update(set(tokens))

    def rank(
        self,
        criterion_text: str,
        k: int = 5,
        extra_keywords: Iterable[str] | str | None = None,
    ) -> list[dict[str, Any]]:
        if k <= 0 or not self.pages:
            return []
        query = criterion_text
        if isinstance(extra_keywords, str):
            query += " " + extra_keywords
        elif extra_keywords:
            query += " " + " ".join(extra_keywords)
        query_terms = set(tokenize(query))
        if not query_terms:
            return []

        count = len(self.pages)
        scored: list[tuple[float, int]] = []
        for index, frequencies in enumerate(self.term_frequencies):
            score = 0.0
            length = self.lengths[index]
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                df = self.document_frequency[term]
                inverse_frequency = math.log1p((count - df + 0.5) / (df + 0.5))
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length / (self.average_length or 1.0)
                )
                score += inverse_frequency * frequency * (self.k1 + 1.0) / denominator
            if score > 0:
                scored.append((score, index))

        scored.sort(key=lambda item: (-item[0], item[1]))
        ranked: list[dict[str, Any]] = []
        seen: set[tuple[Any, Any]] = set()
        for score, index in scored:
            page = self.pages[index]
            key = (page.get("document_id"), page.get("page"))
            if key in seen:
                continue
            seen.add(key)
            ranked.append({
                "document_id": page.get("document_id"),
                "page": page.get("page"),
                "score": score,
            })
            if len(ranked) == k:
                break
        return ranked


def rank_pages(
    criterion_text: str,
    pages: Sequence[dict[str, Any]] | BM25Index,
    k: int = 5,
    *,
    extra_keywords: Iterable[str] | str | None = None,
    index: BM25Index | None = None,
) -> list[dict[str, Any]]:
    """Rank distinct pages best-first; pass an index to reuse work across criteria.

    ``extra_keywords`` is a lightweight query-expansion hook. An index can also be
    passed as ``pages`` directly, or separately with the original page sequence.
    """
    if isinstance(pages, BM25Index):
        active_index = pages
    elif index is not None:
        active_index = index
    else:
        active_index = BM25Index(pages)
    return active_index.rank(criterion_text, k=k, extra_keywords=extra_keywords)
