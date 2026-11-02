"""Stage 0: OCR fallback for scanned / text-less PDFs.

Detection always runs; conversion requires `ocrmypdf` on PATH. When OCR is
needed but unavailable we warn and continue rather than failing the run.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pymupdf as fitz

from .config import Config
from .logging_setup import get_logger

log = get_logger("ocr")


def textless_pages(doc: fitz.Document, min_chars: int = 20) -> list[int]:
    """1-based pages with (almost) no extractable text."""
    pages: list[int] = []
    for i in range(doc.page_count):
        text = doc[i].get_text().strip()
        if len(text) < min_chars:
            pages.append(i + 1)
    return pages


def ocr_available() -> bool:
    return shutil.which("ocrmypdf") is not None


def run_ocr(src: str | Path, dst: str | Path, *, timeout: int = 1800) -> bool:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["ocrmypdf", "--skip-text", "--output-type", "pdf", str(src), str(dst)],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - any failure means "keep original"
        log.warning("ocrmypdf failed (%s); using original PDF", exc)
        return False


def maybe_ocr(cfg: Config, pdf_path: str | Path, workdir: str | Path) -> Path:
    """Return the PDF to parse, running OCR first if needed and enabled."""
    pdf_path = Path(pdf_path)
    if cfg.ocr == "never":
        return pdf_path

    doc = fitz.open(pdf_path)
    try:
        pages = textless_pages(doc)
    finally:
        doc.close()

    if not pages and cfg.ocr != "always":
        return pdf_path

    if pages:
        log.info("%d page(s) appear image-only (%s...)", len(pages), pages[:5])
    if not ocr_available():
        log.warning("OCR needed but 'ocrmypdf' is not installed; proceeding without OCR")
        return pdf_path

    out = Path(workdir) / f"{pdf_path.stem}.ocr.pdf"
    if run_ocr(pdf_path, out):
        log.info("wrote OCR text layer: %s", out)
        return out
    return pdf_path
