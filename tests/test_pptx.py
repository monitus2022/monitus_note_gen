from pptx import Presentation

from pdf2study.render.pptx import render_pptx


def test_render_pptx_builds_slides(tmp_path):
    # an image referenced by the slide
    import pymupdf as fitz

    d = fitz.open()
    page = d.new_page(width=100, height=80)
    page.draw_rect(fitz.Rect(5, 5, 95, 75), color=(1, 0, 0), fill=(1, 0, 0))
    img = tmp_path / "images"
    img.mkdir()
    d[0].get_pixmap().save(str(img / "fig_x.png"))
    d.close()

    md = tmp_path / "slides" / "chapter_01_slides.md"
    md.parent.mkdir()
    md.write_text(
        "# Chapter 1\n\n---\n\n## Topic\n- alpha\n- beta\n\n![cap](../images/fig_x.png)\n",
        encoding="utf-8",
    )
    out = tmp_path / "decks" / "chapter_01_slides.pptx"
    assert render_pptx(md, out) is True
    assert out.exists()

    prs = Presentation(str(out))
    assert len(prs.slides._sldIdLst) == 2
