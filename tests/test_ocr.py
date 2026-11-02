import pymupdf as fitz

from pdf2study.ocr import textless_pages


def test_textless_pages_detects_image_only_page(sample_pdf):
    doc = fitz.open(sample_pdf)
    try:
        pages = textless_pages(doc)
    finally:
        doc.close()
    assert 4 in pages  # page 4 is a full-page image with no text
    assert 1 not in pages
