"""Stage 1: layout parsing.

`PyMuPDFParser` is the default, dependency-light backend. It converts the whole
document to Markdown once, derives sections from the PDF outline (with a
font-size heuristic fallback), and leaves figure extraction to `figures.py`.

Additional backends (Docling, MinerU) implement the same `PDFParser` protocol.
"""

from __future__ import annotations

import re
import statistics
from typing import Protocol

import pymupdf as fitz  # PyMuPDF (new module name)
import pymupdf4llm

from .logging_setup import get_logger
from .models import ParsedDocument, Section

log = get_logger("parser")

CAPTION_RE = re.compile(
    r"^\s*(figure|fig\.?|table|chart|diagram|exhibit)\s*([0-9]+(?:[.\-][0-9]+)*)",
    re.IGNORECASE,
)


class PDFParser(Protocol):
    name: str

    def parse(self, pdf_path: str, dpi: int = 200) -> ParsedDocument: ...


class PyMuPDFParser:
    name = "pymupdf"

    def parse(self, pdf_path: str, dpi: int = 200) -> ParsedDocument:
        doc = fitz.open(pdf_path)
        try:
            toc = doc.get_toc()  # [[level, title, page], ...], page is 1-based
            page_md = self._page_markdown(doc)
            if toc:
                sections = self._sections_from_toc(doc, toc, page_md)
            else:
                log.info("no PDF outline; using font-size heuristic")
                sections = self._sections_from_heuristic(doc, page_md)
            title = (doc.metadata or {}).get("title") or None
            return ParsedDocument(title=title, sections=sections, toc=toc, parser=self.name)
        finally:
            doc.close()

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _page_markdown(doc: fitz.Document) -> list[str]:
        """Whole-document Markdown, one string per page (index 0 == page 1)."""
        chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, write_images=False)
        pages: list[str] = []
        for item in chunks:
            if isinstance(item, dict):
                pages.append(item.get("text", ""))
            else:  # pragma: no cover - older API returns plain strings
                pages.append(str(item))
        # Guard against length mismatch.
        while len(pages) < doc.page_count:
            pages.append("")
        return pages[: doc.page_count]

    @staticmethod
    def _sections_from_toc(
        doc: fitz.Document, toc: list, page_md: list[str]
    ) -> list[Section]:
        boundaries = [(int(lvl), str(title), int(page)) for lvl, title, page in toc]
        sections: list[Section] = []
        for i, (level, title, page) in enumerate(boundaries):
            start = max(1, page)
            end = boundaries[i + 1][2] - 1 if i + 1 < len(boundaries) else doc.page_count
            end = max(end, start)
            md = "\n\n".join(page_md[p - 1] for p in range(start, end + 1) if 1 <= p <= len(page_md))
            sections.append(Section(title=title, level=level, page=start, markdown=md.strip()))
        return sections

    @staticmethod
    def _sections_from_heuristic(doc: fitz.Document, page_md: list[str]) -> list[Section]:
        """Detect headings by font size relative to the body text."""
        sizes: list[float] = []
        per_page_spans: list[list[tuple[str, float, bool]]] = []
        for page in doc:
            spans: list[tuple[str, float, bool]] = []
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                    if not text:
                        continue
                    size = max((s.get("size", 0) for s in line.get("spans", [])), default=0)
                    bold = any("Bold" in s.get("font", "") for s in line.get("spans", []))
                    spans.append((text, size, bold))
                    sizes.append(size)
            per_page_spans.append(spans)

        body = statistics.median(sizes) if sizes else 0.0
        threshold = body * 1.35

        headings: list[tuple[int, str, int]] = []
        for page_no, spans in enumerate(per_page_spans, start=1):
            for text, size, bold in spans:
                if size >= threshold or (bold and size >= body * 1.1 and len(text) < 80):
                    level = 1 if size >= threshold * 1.15 else 2
                    headings.append((level, text, page_no))

        if not headings:
            return [Section(title="Document", level=1, page=1, markdown="\n\n".join(page_md).strip())]

        sections: list[Section] = []
        for i, (level, text, page) in enumerate(headings):
            start = page
            end = headings[i + 1][2] - 1 if i + 1 < len(headings) else doc.page_count
            end = max(end, start)
            md = "\n\n".join(page_md[p - 1] for p in range(start, end + 1) if 1 <= p <= len(page_md))
            sections.append(Section(title=text, level=level, page=start, markdown=md.strip()))
        return sections
