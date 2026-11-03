"""EPUB rendering: a single e-reader file per book.

Slides content only (headings + embedded figures), with a nested table of
contents (chapters -> sections) and a visible Contents page. The Q&A is
intentionally excluded.
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


def _slides_html(slides_md: str) -> tuple[str, list[dict]]:
    """Return (html, toc_tokens) for a chapter's slide content."""
    md = re.sub(r"(?m)^\s*#\s+.*$", "", slides_md, count=1)  # drop duplicate title
    md = _IMG.sub(lambda m: f"![{m.group(1)}](images/{Path(m.group(2)).name})", md)
    md = re.sub(r"(?m)^---\s*$", "", md)  # drop slide separators
    conv = markdown.Markdown(extensions=["tables", "sane_lists", "toc"])
    return conv.convert(md), conv.toc_tokens


def _qna_html(qna_md: str) -> str:  # retained for reference; not used in EPUB
    lines: list[str] = []
    for line in qna_md.splitlines():
        if re.match(r"^\?\?\? tip", line):
            continue
        if line.startswith("    "):
            line = line[4:]
        line = re.sub(r"^(\s*)- \[[ xX]\] ", r"\1- ", line)  # checkbox -> bullet
        lines.append(line)
    return markdown.markdown("\n".join(lines), extensions=["tables", "sane_lists"])


def _sub_links(tokens: list[dict], file_name: str) -> list:
    """Nested epub.Link entries from markdown toc tokens."""
    out: list = []
    for t in tokens:
        link = epub.Link(f"{file_name}#{t['id']}", t["name"], uid=f"{file_name}-{t['id']}")
        children = _sub_links(t.get("children", []), file_name)
        out.append((link, children) if children else link)
    return out


def _flatten(tokens: list[dict], file_name: str) -> list[tuple[str, str]]:
    flat: list[tuple[str, str]] = []
    for t in tokens:
        flat.append((f"{file_name}#{t['id']}", t["name"]))
        flat.extend(_flatten(t.get("children", []), file_name))
    return flat


def _contents_page(entries: list[tuple[str, str, list[tuple[str, str]]]]) -> str:
    html = ["<h1>Contents</h1>", "<ul>"]
    for file_name, title, subs in entries:
        html.append(f"<li><a href='{file_name}'>{escape(title)}</a>")
        if subs:
            html.append("<ul>")
            html.extend(f"<li><a href='{href}'>{escape(label)}</a></li>" for href, label in subs)
            html.append("</ul>")
        html.append("</li>")
    html.append("</ul>")
    return "".join(html)


def render_epub(chapters, images_dir: str | Path, out_path: str | Path, *, title: str, slug: str) -> bool:
    """Build a single EPUB from chapter artifacts (attrs: index, title, slides_md, qna_md)."""
    images_dir = Path(images_dir)
    out_path = Path(out_path)

    book = epub.EpubBook()
    book.set_identifier(f"pdf2study-{slug}")
    book.set_title(title)
    book.set_language("en")
    book.add_author("pdf2study")

    css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=_CSS)
    book.add_item(css)

    title_page = epub.EpubHtml(title=title, file_name="title.xhtml", lang="en")
    title_page.content = (
        f"<html><head><link rel='stylesheet' href='style.css'/></head>"
        f"<body><h1>{escape(title)}</h1></body></html>"
    )

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

    contents_entries: list[tuple[str, str, list[tuple[str, str]]]] = []
    spine = ["nav", title_page]
    toc: list = []
    for ch in chapters:
        file_name = f"chapter_{ch.index:02d}.xhtml"
        slides_html, tokens = _slides_html(ch.slides_md)
        body = f"<h1>{escape(ch.title)}</h1>" + slides_html
        subs = _flatten(tokens, file_name)

        item = epub.EpubHtml(title=ch.title, file_name=file_name, lang="en")
        item.content = f"<html><head><link rel='stylesheet' href='style.css'/></head><body>{body}</body></html>"
        item.add_item(css)
        book.add_item(item)

        sub_links = _sub_links(tokens, file_name)
        toc.append((item, sub_links) if sub_links else item)
        contents_entries.append((file_name, ch.title, subs))
        spine.append(item)

    # Visible Contents page.
    contents = epub.EpubHtml(title="Contents", file_name="contents.xhtml", lang="en")
    contents.content = (
        f"<html><head><link rel='stylesheet' href='style.css'/></head>"
        f"<body>{_contents_page(contents_entries)}</body></html>"
    )
    contents.add_item(css)
    book.add_item(contents)
    spine.insert(2, contents)

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    out_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(out_path), book)
    log.info("wrote %s (%d chapters, %d images)", out_path.name, len(chapters), len(names))
    return True
