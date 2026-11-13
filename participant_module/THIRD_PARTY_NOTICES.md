# Third-party notices

Team Cache Kita | participant_module | checked 2026-10-29

Everything in `participant_module/` was written by the team and is licensed under MIT
(`LICENSE`). The module ships no third-party code, no packages and no model weights.

## Copied third-party code

None. When a third-party pure-Python file is copied in, list it here with its name, source URL,
version and licence, and keep its licence file next to it (LICENSING.md §2.2).

## Packages used from the common base environment (not shipped)

These are imported at run time and installed by the organizer as part of the common base
environment (`base_id` in `submission.json`); versions are those of `requirements-base.lock`.

| Package | Version | Licence | Used for |
|---|---|---|---|
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0 (PDFium and its bundled libraries keep their own licences, listed in the wheel) | page text extraction |
| rapidocr-onnxruntime | 1.4.4 | Apache-2.0 | OCR of scanned pages |
| torch | 2.11.0 | BSD-3-Clause | running the catalogue model |
| transformers | 5.19.0 | Apache-2.0 | running the catalogue model |

## Models

`deberta-v3-base-zeroshot-v2.0-c` (MIT), by `catalog_id` in `submission.json`, from the organizer's model
store. Its weights are not in this package.
