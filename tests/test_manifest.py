from pdf2study.chunker import HierarchicalChunker
from pdf2study.manifest import build_manifest
from pdf2study.models import Figure, ParsedDocument, Section


def test_manifest_groups_chapters_and_assigns_figures():
    sections = [
        Section(title="Ch1", level=1, page=1, markdown="a", figures=[Figure("f1", 1, (0, 0, 1, 1), "cap")]),
        Section(title="Ch2", level=1, page=3, markdown="b"),
    ]
    chunks = HierarchicalChunker("b").chunk(sections)
    manifest = build_manifest(
        slug="b", parsed=ParsedDocument("Title", sections, parser="pymupdf"), chunks=chunks, model="qwen3.5:4b"
    )
    assert manifest["slug"] == "b"
    assert manifest["model"] == "qwen3.5:4b"
    assert len(manifest["chapters"]) == 2
    assert manifest["chapters"][0]["figures"][0]["id"] == "f1"
    assert manifest["chapters"][0]["slides"] == "slides/chapter_01_slides.md"
    assert manifest["chapters"][1]["deck_pdf"] == "decks/chapter_02_slides.pdf"
