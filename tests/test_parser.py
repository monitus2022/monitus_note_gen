from pdf2study.parser import PyMuPDFParser


def test_parse_uses_pdf_outline(sample_pdf):
    parsed = PyMuPDFParser().parse(str(sample_pdf))
    assert parsed.toc, "sample PDF has an outline"
    assert len(parsed.sections) == 3
    assert parsed.sections[0].title.startswith("Chapter 1")
    assert parsed.parser == "pymupdf"


def test_sections_have_markdown(sample_pdf):
    parsed = PyMuPDFParser().parse(str(sample_pdf))
    assert any("Introduction" in s.markdown or s.title.startswith("Chapter 1") for s in parsed.sections)
