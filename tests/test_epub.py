import zipfile

from PIL import Image

from pdf2study.generate import ChapterArtifacts
from pdf2study.render.epub import image_names, render_epub


def _chapters():
    return [
        ChapterArtifacts(
            1,
            "Chapter One",
            "# Chapter One\n\n---\n\n## Topic A\n\n- alpha\n\n![fig](../images/f1.png)\n",
            "### Question 1: Q\n\n- [ ] A) one\n- [ ] B) two\n\n??? tip \"Reveal\"\n    **Correct Answer:** A\n\n    **Explanation:** because.\n",
        ),
        ChapterArtifacts(2, "Chapter Two", "# Chapter Two\n\n## Topic B\n\n- beta\n", ""),
    ]


def test_image_names_deduped():
    ch = _chapters()
    assert image_names(*[c.slides_md for c in ch]) == ["f1.png"]


def test_render_epub_structure(tmp_path):
    img = tmp_path / "images"
    img.mkdir()
    Image.new("RGB", (40, 30), (1, 2, 3)).save(img / "f1.png")

    out = tmp_path / "book.epub"
    assert render_epub(_chapters(), img, out, title="My Book", slug="book") is True
    assert out.exists()

    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"  # EPUB requires mimetype first, stored
        assert z.read("mimetype") == b"application/epub+zip"
        assert any(n.endswith("chapter_01.xhtml") for n in names)
        assert any(n.endswith("images/f1.png") for n in names)

    # Q&A is intentionally excluded from the EPUB
    with zipfile.ZipFile(out) as z:
        ch1 = z.read([n for n in z.namelist() if n.endswith("chapter_01.xhtml")][0]).decode()
    assert "Practice Questions" not in ch1
    assert "Correct Answer" not in ch1
    assert 'src="images/f1.png"' in ch1
    # a Contents page is included
    assert any(n.endswith("contents.xhtml") for n in zipfile.ZipFile(out).namelist())
