"""EPUB rendering: a single e-reader file per book.

Preserves headings and embeds figures (something PDF slides / Markdown can't do
on basic e-readers). Q&A callouts are converted to plain readable text.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import markdown
from ebooklib import epub

from ..logging_setup import get_logger

log = get_logger("render.epub")

_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}
_CSS = (
    "body{font-family:serif;line-height:1.4;}"
    "h1,h2,h3{line-height:1.2;}"
    "img{max-width:100%;height:auto;}"
    "ul{margin-left:1em;}"
)


def image_names(*markdowns: str) -> list[str]:
    """Basenames of every image referenced across the given Markdown blobs."""
    names: list[str] = []
    for md in markdowns:
        for m in _IMG.finditer(md or ""):
            name = Path(m.group(2)).name
            if name not in names:
                names.append(name)
    return names


def _slides_body_html(slides_md: str) -> str:
    md = re.sub(r"(?m)^\s*#\s+.*$", "", slides_md, count=1)  # drop duplicate title
    md = _IMG.sub(lambda m: f"![{m.group(1)}](images/{Path(m.group(2)).name})", md)
    md = re.sub(r"(?m)^---\s*$", "", md)  # drop slide separators
    return markdown.markdown(md, extensions=["tables", "sane_lists"])


def _qna_html(qna_md: str) -> str:
    lines: list[str] = []
    for line in qna_md.splitlines():
        if re.match(r"^\?\?\? tip", line):
            continue
        if line.startswith("    "):
            line = line[4:]
        line = re.sub(r"^(\s*)- \[[ xX]\] ", r"\1- ", line)  # checkbox -> bullet
        lines.append(line)
    return markdown.markdown("\n".join(lines), extensions=["tables", "sane_lists"])


def render_epub(chapters, images_dir: str | Path, out_path: str | Path, *, title: str, slug: str) -> bool:
    """Build a single EPUB from chapter artifacts (attributes: index, title, slides_md, qna_md)."""
    images_dir = Path(images_dir)
    out_path = Path(out_path)

    book = epub.EpubBook()
    book.set_identifier(f"pdf2study-{slug}")
    book.set_title(title)
    book.set_language("en")
    book.add_author("pdf2study")

    css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=_CSS)
    book.add_item(css)

    # Cover-ish title page.
    title_page = epub.EpubHtml(title=title, file_name="title.xhtml", lang="en")
    title_page.content = f"<html><head><link rel='stylesheet' href='style.css'/></head><body><h1>{escape(title)}</h1></body></html>"

    # Embed every referenced image once.
    names = image_names(*[c.slides_md for c in chapters])
    for name in names:
        src = images_dir / name
        if not src.exists():
            log.warning("missing image for epub: %s", name)
            continue
        book.add_item(
            epub.EpubItem(
                uid=f"img_{name}",
                file_name=f"images/{name}",
                media_type=_MEDIA.get(src.suffix.lower(), "image/png"),
                content=src.read_bytes(),
            )
        )

    spine = ["nav", title_page]
    toc = []
    for ch in chapters:
        body = f"<h1>{escape(ch.title)}</h1>" + _slides_body_html(ch.slides_md)
        if (ch.qna_md or "").strip():
            body += "<h2>Practice Questions</h2>" + _qna_html(ch.qna_md)
        item = epub.EpubHtml(title=ch.title, file_name=f"chapter_{ch.index:02d}.xhtml", lang="en")
        item.content = f"<html><head><link rel='stylesheet' href='style.css'/></head><body>{body}</body></html>"
        item.add_item(css)
        book.add_item(item)
        spine.append(item)
        toc.append(item)

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    out_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(out_path), book)
    log.info("wrote %s (%d chapters, %d images)", out_path.name, len(chapters), len(names))
    return True
