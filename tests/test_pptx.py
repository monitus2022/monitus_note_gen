from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

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


def test_render_pptx_fits_image_only_slide(tmp_path):
    from PIL import Image

    img = tmp_path / "images"
    img.mkdir()
    Image.new("RGB", (2000, 500), (10, 20, 30)).save(img / "wide.png")

    md = tmp_path / "slides" / "img.md"
    md.parent.mkdir()
    md.write_text("![bg fit](../images/wide.png)\n", encoding="utf-8")

    out = tmp_path / "out.pptx"
    assert render_pptx(md, out) is True

    prs = Presentation(str(out))
    slides = list(prs.slides)
    assert len(slides) == 1
    pics = [sh for sh in slides[0].shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) == 1
    pic = pics[0]
    # fits within the slide and preserves the 4:1 aspect ratio
    assert pic.width <= prs.slide_width and pic.height <= prs.slide_height
    assert abs((pic.width / pic.height) - 4.0) < 0.05
