"""Pure-Python PPTX rendering (no LibreOffice dependency).

Parses the assembled Marp Markdown into slides and rebuilds them with
python-pptx. Image-only slides are scaled to fit the slide (aspect preserved)
and centered, matching Marp's `![bg fit]` behaviour.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu, Inches, Pt

from ..logging_setup import get_logger
from ..validate import parse_slide, split_slides

log = get_logger("render.pptx")

_TITLE_TOP = Inches(0.4)
_TITLE_HEIGHT = Inches(0.9)
_BODY_TOP = Inches(1.4)
_LEFT = Inches(0.6)
_CONTENT_MARGIN = Inches(0.3)


def _fit_size(path: Path, max_w: int, max_h: int) -> tuple[int, int]:
    """Largest (w, h) in EMU that fits within max_w x max_h, aspect preserved."""
    with Image.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    return max(1, int(w * scale)), max(1, int(h * scale))


def render_pptx(md_path: str | Path, out_path: str | Path) -> bool:
    md_path, out_path = Path(md_path), Path(out_path)
    try:
        markdown = md_path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("cannot read %s: %s", md_path, exc)
        return False

    prs = Presentation()
    blank = prs.slide_layouts[6]
    base_dir = md_path.parent
    slide_w, slide_h = prs.slide_width, prs.slide_height

    for block in split_slides(markdown):
        slide = parse_slide(block)
        s = prs.slides.add_slide(blank)

        images = [(alt, (base_dir / path).resolve()) for alt, path in slide.images]
        images = [(alt, path) for alt, path in images if path.exists()]
        for alt, path in [(a, p) for a, p in slide.images if not (base_dir / p).resolve().exists()]:
            log.warning("missing image referenced by slide: %s", path)

        # Image-only slide: fit to the full slide and center.
        if images and not slide.bullets and not slide.title:
            w, h = _fit_size(images[0][1], slide_w - 2 * _CONTENT_MARGIN, slide_h - 2 * _CONTENT_MARGIN)
            left = int((slide_w - w) / 2)
            top = int((slide_h - h) / 2)
            try:
                s.shapes.add_picture(str(images[0][1]), Emu(left), Emu(top), width=Emu(w), height=Emu(h))
            except Exception as exc:  # noqa: BLE001 - bad/corrupt image
                log.warning("failed to embed %s: %s", images[0][1], exc)
            continue

        title_box = s.shapes.add_textbox(_LEFT, _TITLE_TOP, slide_w - 2 * _LEFT, _TITLE_HEIGHT)
        tf = title_box.text_frame
        tf.text = slide.title or " "
        tf.paragraphs[0].font.size = Pt(28)
        tf.paragraphs[0].font.bold = True

        image_top = _BODY_TOP
        if slide.bullets:
            body = s.shapes.add_textbox(_LEFT, _BODY_TOP, slide_w - 2 * _LEFT, Inches(3.0))
            bf = body.text_frame
            bf.word_wrap = True
            for i, bullet in enumerate(slide.bullets):
                para = bf.paragraphs[0] if i == 0 else bf.add_paragraph()
                para.text = f"\u2022 {bullet}"
                para.font.size = Pt(18)
            image_top = Inches(4.4)

        # Leftover inline image on a text slide: fit into the remaining area.
        if images:
            box_w = slide_w - 2 * _CONTENT_MARGIN
            box_h = slide_h - image_top - _CONTENT_MARGIN
            w, h = _fit_size(images[0][1], box_w, box_h)
            left = int((slide_w - w) / 2)
            try:
                s.shapes.add_picture(str(images[0][1]), Emu(left), image_top, width=Emu(w), height=Emu(h))
            except Exception as exc:  # noqa: BLE001
                log.warning("failed to embed %s: %s", images[0][1], exc)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    log.info("wrote %s (%d slides)", out_path.name, len(prs.slides._sldIdLst))
    return True
