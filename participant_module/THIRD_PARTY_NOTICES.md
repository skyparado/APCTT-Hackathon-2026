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

## Models

None. Catalogue models, once used, are listed by `catalog_id` in `submission.json` and are
provided by the organizer's model store; their weights are never in this package.
