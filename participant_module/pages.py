"""PDF page extraction with optional OCR and a local content-addressed cache."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)
_MIN_OCR_REMAINING_MS = 20_000
_CACHE_DIR = Path(tempfile.gettempdir()) / "apctt-page-cache"


def _ocr_page(page: Any, engine: Any) -> str:
    image = page.render(scale=2).to_pil()
    result, _ = engine(image)
    if not result:
        return ""
    return "\n".join(str(item[1]) for item in result if len(item) > 1 and item[1])


def _read_pdf(path: Path, deadline: Callable[[], float] | None) -> tuple[list[str], bool]:
    import pypdfium2

    pdf = pypdfium2.PdfDocument(str(path))
    try:
        texts: list[str] = []
        cacheable = True
        ocr_engine: Any = None
        ocr_unavailable = False
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range() or ""
                finally:
                    textpage.close()

                if len(text.strip()) < 20 and not ocr_unavailable:
                    if deadline is not None and deadline() < _MIN_OCR_REMAINING_MS:
                        texts.append(text)
                        cacheable = False
                        continue
                    if ocr_engine is None:
                        try:
                            from rapidocr_onnxruntime import RapidOCR

                            ocr_engine = RapidOCR()
                        except ImportError:
                            ocr_unavailable = True
                    if ocr_engine is not None:
                        try:
                            text = _ocr_page(page, ocr_engine) or text
                        except Exception:
                            _LOGGER.exception("OCR failed on %s page %d", path, index + 1)
                texts.append(text)
            finally:
                page.close()
        return texts, cacheable
    finally:
        pdf.close()


def read_pages(
    document: dict[str, Any],
    deadline: Callable[[], float] | None = None,
) -> list[dict[str, Any]]:
    """Read a PDF into page records; invalid PDFs are logged and return an empty list."""
    document_id = document.get("document_id")
    try:
        path = Path(document["path"])
        hasher = hashlib.sha256()
        with path.open("rb") as pdf_file:
            for chunk in iter(lambda: pdf_file.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        cache_path = _CACHE_DIR / f"{digest}.json"

        if cache_path.is_file():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(cached, list) and all(isinstance(text, str) for text in cached):
                    return [
                        {"document_id": document_id, "page": number, "text": text}
                        for number, text in enumerate(cached, start=1)
                    ]
            except (OSError, ValueError):
                _LOGGER.warning("Ignoring invalid page cache %s", cache_path, exc_info=True)

        texts, cacheable = _read_pdf(path, deadline)
        if not texts:
            _LOGGER.warning("PDF has no pages: %s", path)
            return []

        if cacheable:
            try:
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                temporary = cache_path.with_suffix(f".{os.getpid()}.tmp")
                temporary.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
                temporary.replace(cache_path)
            except OSError:
                _LOGGER.exception("Could not cache extracted page text for %s", path)

        return [
            {"document_id": document_id, "page": number, "text": text}
            for number, text in enumerate(texts, start=1)
        ]
    except Exception:
        _LOGGER.exception("Could not read PDF document %r", document_id)
        return []
