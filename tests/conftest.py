"""Shared test fixtures: a synthetic PDF exercising the figure/OCR paths."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
import pytest


def _image_bytes() -> bytes:
    d = fitz.open()
    p = d.new_page(width=200, height=150)
    p.draw_rect(fitz.Rect(10, 10, 190, 140), color=(1, 0, 0), fill=(0.8, 0.8, 1))
    pix = p.get_pixmap()
    data = pix.tobytes("png")
    d.close()
    return data


def make_sample_pdf(path: Path) -> Path:
    doc = fitz.open()
    img = _image_bytes()

    # Page 1 - chapter heading + raster figure + caption
    p1 = doc.new_page()
    p1.insert_text((72, 80), "Chapter 1: Introduction", fontsize=24)
    p1.insert_text((72, 120), "Introductory body text. " * 4, fontsize=11)
    p1.insert_image(fitz.Rect(72, 200, 300, 350), stream=img)
    p1.insert_text((72, 370), "Figure 1.1: A sample raster figure.", fontsize=9)

    # Page 2 - subsection + vector chart + caption
    p2 = doc.new_page()
    p2.insert_text((72, 80), "Section 1.1 Details", fontsize=16)
    p2.insert_text((72, 120), "Detailed body text. " * 6, fontsize=11)
    for i in range(8):
        bar_h = 30 + i * 12
        p2.draw_rect(
            fitz.Rect(120 + i * 35, 360 - bar_h, 145 + i * 35, 360),
            color=(0, 0, 1),
            fill=(0.5, 0.5, 1),
        )
    p2.insert_text((72, 380), "Figure 1.2: A vector bar chart.", fontsize=9)

    # Page 3 - second chapter
    p3 = doc.new_page()
    p3.insert_text((72, 80), "Chapter 2: Methods", fontsize=24)
    p3.insert_text((72, 120), "Methods body text. " * 6, fontsize=11)

    # Page 4 - text-less page (full-page image) to exercise OCR detection
    p4 = doc.new_page()
    p4.insert_image(fitz.Rect(0, 0, 612, 792), stream=img)

    doc.set_toc(
        [
            [1, "Chapter 1: Introduction", 1],
            [2, "Section 1.1 Details", 2],
            [1, "Chapter 2: Methods", 3],
        ]
    )
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> Path:
    return make_sample_pdf(tmp_path_factory.mktemp("pdf") / "sample.pdf")
