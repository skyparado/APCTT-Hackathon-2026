from __future__ import annotations

from participant_module.quotes import pick_quote, verify_quote
from participant_module.retrieval import BM25Index, rank_pages


def test_bm25_orders_relevant_page_first_and_index_is_reusable() -> None:
    pages = [
        {"document_id": "D001", "page": 1, "text": "Background on spacecraft design."},
        {
            "document_id": "D001",
            "page": 2,
            "text": "The prototype was tested in a thermal vacuum chamber.",
        },
    ]
    index = BM25Index(pages)
    query = "prototype tested thermal vacuum"
    assert rank_pages(query, index, k=1)[0]["page"] == 2
    assert rank_pages(query, pages, k=1, index=index)[0]["page"] == 2


def test_quote_is_a_verifiable_exact_page_substring() -> None:
    page = (
        "Reached TRL 6. The prototype was tested in a thermal vacuum chamber "
        "for twelve cycles, and the measured results met acceptance criteria."
    )
    quote = pick_quote(page, "prototype tested thermal vacuum acceptance criteria")
    assert quote is not None
    assert quote in page
    assert verify_quote(quote, page)
    assert not verify_quote("measured results met", page.replace("met", "failed"))


def test_trl_only_sentence_is_skipped() -> None:
    assert pick_quote("The technology reached TRL 6.", "TRL maturity level") is None
