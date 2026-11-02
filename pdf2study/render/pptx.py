"""Pure-Python PPTX rendering (no LibreOffice dependency).

Parses the assembled Marp Markdown into slides and rebuilds them with
python-pptx. Fidelity is lower than Marp's native --pptx (no custom themes), but
it keeps the tool portable.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from ..logging_setup import get_logger
from ..validate import parse_slide, split_slides

log = get_logger("render.pptx")

_TITLE_TOP = Inches(0.4)
_BODY_TOP = Inches(1.4)
_LEFT = Inches(0.6)
_WIDTH = Inches(9.0)
_IMAGE_TOP = Inches(4.6)


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

    for block in split_slides(markdown):
        slide = parse_slide(block)
        s = prs.slides.add_slide(blank)

        title_box = s.shapes.add_textbox(_LEFT, _TITLE_TOP, _WIDTH, Inches(0.9))
        tf = title_box.text_frame
        tf.text = slide.title or " "
        tf.paragraphs[0].font.size = Pt(28)
        tf.paragraphs[0].font.bold = True

        if slide.bullets:
            body = s.shapes.add_textbox(_LEFT, _BODY_TOP, _WIDTH, Inches(3.0))
            bf = body.text_frame
            bf.word_wrap = True
            for i, bullet in enumerate(slide.bullets):
                para = bf.paragraphs[0] if i == 0 else bf.add_paragraph()
                para.text = f"\u2022 {bullet}"
                para.font.size = Pt(18)

        y = _IMAGE_TOP
        for alt, img_path in slide.images[:2]:
            resolved = (base_dir / img_path).resolve()
            if resolved.exists():
                try:
                    s.shapes.add_picture(str(resolved), _LEFT, y, height=Inches(3.0))
                    y += Inches(3.0)
                except Exception as exc:  # noqa: BLE001 - bad/corrupt image
                    log.warning("failed to embed %s: %s", img_path, exc)
            else:
                log.warning("missing image referenced by slide: %s", img_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    log.info("wrote %s (%d slides)", out_path.name, len(prs.slides._sldIdLst))
    return True
