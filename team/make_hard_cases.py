"""Build hard cases the public set never exercises, as server request files (dev-only, never shipped).

    ~/apctt-env/bin/python team/make_hard_cases.py --req ~/apctt-cases/req --out ~/apctt-hard

Every case is legal under DATA_CONTRACT (at most 3 PDFs, 50 MiB each, 300 pages in all) and built from
the public USGS PDFs, so it looks like a hidden case but stresses one weak spot:

  HARD-SCAN3     3 image-only PDFs (pages rendered to JPEG, no text layer), 300 pages: OCR worst case
  HARD-TEXT3     3 text PDFs at the 300-page limit and about 59 MiB: reading and judging worst case
  HARD-MIXED     a text report + an image-only copy of another + a blank 1-page PDF
  HARD-BLANK     one PDF of 3 blank pages: nothing to read at all
  HARD-DUPE      the same report sent twice as two documents
  HARD-OWNERPW   a report encrypted with an owner password (opens without a password)
  HARD-COMPONENT a USGS model report whose target type is `component` (the contract allows it)
  HARD-SUBSYS    a USGS system report whose target type is `subsystem`
  HARD-SHORT     only the first 2 pages of a report (title page and contents)
  HARD-NOFIELDS  optional case fields left out (description, benefits, sdg_targets, sdg_rationale)
Run them with team/run_public.py --req OUT/req --pdf OUT/pdf (quotes are checked against OUT/pdf/<case>.pdf,
the first document).
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
from pathlib import Path

import pypdf
import pypdfium2 as pdfium
from PIL import Image


def load(req_dir: Path, case_id: str) -> dict:
    return json.loads((req_dir / f"{case_id}.json").read_text(encoding="utf-8"))


def pdf_bytes(body: dict, index: int = 0) -> bytes:
    return base64.b64decode(body["case"]["documents"][index]["content_base64"])


def document(template: dict, document_id: str, data: bytes, title: str) -> dict:
    doc = {k: v for k, v in template.items() if k in ("title", "document_date", "language", "format")}
    doc.update(document_id=document_id, title=title,
               content_base64=base64.b64encode(data).decode("ascii"), sha256=hashlib.sha256(data).hexdigest())
    return doc


def image_only(data: bytes, max_pages: int, scale: float = 1.4) -> bytes:
    """Render each page to a JPEG and rebuild the PDF from the images: a scan without a text layer."""
    source = pdfium.PdfDocument(data)
    images = []
    try:
        for index in range(min(max_pages, len(source))):
            page = source[index]
            images.append(page.render(scale=scale).to_pil().convert("L"))
            page.close()
    finally:
        source.close()
    out = io.BytesIO()
    images[0].save(out, "PDF", save_all=True, append_images=images[1:], resolution=72 * scale, quality=55)
    return out.getvalue()


def first_pages(data: bytes, count: int) -> bytes:
    reader = pypdf.PdfReader(io.BytesIO(data))
    writer = pypdf.PdfWriter()
    for page in reader.pages[:count]:
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def blank(pages: int) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def owner_password(data: bytes) -> bytes:
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password="", owner_password="team-cache-kita", algorithm="AES-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--req", type=Path, default=Path.home() / "apctt-cases" / "req")
    parser.add_argument("--out", type=Path, default=Path.home() / "apctt-hard")
    args = parser.parse_args()
    (args.out / "req").mkdir(parents=True, exist_ok=True)
    (args.out / "pdf").mkdir(parents=True, exist_ok=True)

    def write(case_id: str, base: dict, docs: list[tuple[bytes, str]], **case_changes) -> None:
        body = copy.deepcopy(base)
        case = body["case"]
        template = case["documents"][0]
        case["case_id"] = case_id
        case["documents"] = [document(template, f"D{n:03d}", data, title) for n, (data, title) in enumerate(docs, 1)]
        for key, value in case_changes.items():
            if value is None:
                case.pop(key, None)
            else:
                case[key] = value
        body["request_id"] = case_id
        (args.out / "req" / f"{case_id}.json").write_text(json.dumps(body), encoding="utf-8")
        (args.out / "pdf" / f"{case_id}.pdf").write_bytes(docs[0][0])
        for n, (data, _) in enumerate(docs, 1):
            (args.out / "pdf" / f"{case_id}.D{n:03d}.pdf").write_bytes(data)
        pages = sum(len(pypdf.PdfReader(io.BytesIO(d)).pages) for d, _ in docs)
        size = sum(len(d) for d, _ in docs) / 2**20
        print(f"{case_id:15} {len(docs)} PDFs, {pages} pages, {size:.1f} MiB", flush=True)

    c075, c034, c056 = load(args.req, "USGS-SDG-075"), load(args.req, "USGS-SDG-034"), load(args.req, "USGS-SDG-056")
    c001, c040, c033 = load(args.req, "USGS-SDG-001"), load(args.req, "USGS-SDG-040"), load(args.req, "USGS-SDG-033")

    write("HARD-SCAN3", c075, [(image_only(pdf_bytes(c075), 208), "Scanned report 1"),
                               (image_only(pdf_bytes(c034), 46), "Scanned report 2"),
                               (image_only(pdf_bytes(c056), 46), "Scanned report 3")])
    write("HARD-TEXT3", c075, [(pdf_bytes(c034), "Report 1"), (pdf_bytes(c056), "Report 2"), (pdf_bytes(c075), "Report 3")])
    write("HARD-MIXED", c001, [(pdf_bytes(c001), "Main report"), (image_only(pdf_bytes(c040), 40), "Scanned annex"),
                               (blank(1), "Blank cover")])
    write("HARD-BLANK", c001, [(blank(3), "Blank report")])
    write("HARD-DUPE", c001, [(pdf_bytes(c001), "Report"), (pdf_bytes(c001), "Report, second copy")])
    write("HARD-OWNERPW", c001, [(owner_password(pdf_bytes(c001)), "Protected report")])
    target = dict(c001["case"]["assessment_target"], type="component")
    write("HARD-COMPONENT", c001, [(pdf_bytes(c001), "Report")], assessment_target=target)
    target = dict(c033["case"]["assessment_target"], type="subsystem")
    write("HARD-SUBSYS", c033, [(pdf_bytes(c033), "Report")], assessment_target=target)
    write("HARD-SHORT", c040, [(first_pages(pdf_bytes(c040), 2), "Report, first 2 pages")])
    write("HARD-NOFIELDS", c040, [(pdf_bytes(c040), "Report")], description=None, benefits=None,
          sdg_targets=None, sdg_rationale=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
