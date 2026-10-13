"""Build a request file from PDF reports: python tools/make_request.py REPORT.pdf [...] -o FILE.

The case fields (target, application, environment, title, versions, …) are copied from a template
request (default: docs/EXAMPLE_REQUEST.json); only `documents` is replaced by the given PDFs, each
with `format`, `content_base64` and `sha256` filled in. Edit the template or the output for your
own cases. Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path


def build_request(template: dict, pdfs: list[Path], request_id: str) -> dict:
    case = {k: v for k, v in template["case"].items() if k != "documents"}
    documents = []
    for index, pdf in enumerate(pdfs, start=1):
        data = pdf.read_bytes()
        if not data.startswith(b"%PDF-"):
            raise SystemExit(f"{pdf}: not a PDF file (no %PDF- header)")
        documents.append(
            {
                "document_id": f"D{index:03d}",
                "title": pdf.stem,
                "document_date": None,
                "language": "en",
                "format": "pdf",
                "content_base64": base64.b64encode(data).decode("ascii"),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    case["documents"] = documents
    return {"request_id": request_id, "case": case}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path, help="PDF files, in document order")
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--template", type=Path, default=Path("docs/EXAMPLE_REQUEST.json"))
    parser.add_argument("--case-id", help="case_id to set (identifier)")
    parser.add_argument("--request-id", default="REQ-LOCAL-001")
    args = parser.parse_args(argv)
    template = json.loads(args.template.read_text(encoding="utf-8"))
    body = build_request(template, args.pdfs, args.request_id)
    if args.case_id:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", args.case_id):
            raise SystemExit("--case-id must be an identifier [A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
        body["case"]["case_id"] = args.case_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    pages = ", ".join(str(p) for p in args.pdfs)
    print(f"{args.output}: {len(args.pdfs)} document(s) from {pages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
