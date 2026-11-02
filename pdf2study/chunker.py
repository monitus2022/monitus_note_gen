"""Stage 2: hierarchical chunking.

Splits sections into token-budgeted chunks along Markdown headers, then double
line breaks, carrying parent metadata (book, chapter, section, order).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .logging_setup import get_logger
from .models import Figure, Section

log = get_logger("chunker")

try:  # optional; Qwen's tokenizer differs, so this is an approximation
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

except Exception:  # pragma: no cover - offline / missing tiktoken

    def count_tokens(text: str) -> int:
        return max(1, int(len(text.split()) * 1.33))


_HEADER_RE = re.compile(r"(?m)^(#{2,6})\s+.+$")


@dataclass
class Chunk:
    chunk_id: str
    order: int
    book: str
    chapter: str
    section: str
    level: int
    page: int
    text: str
    tokens: int
    figures: list[Figure] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class HierarchicalChunker:
    def __init__(self, book_slug: str, max_tokens: int = 3500):
        self.book_slug = book_slug
        self.max_tokens = max_tokens

    def chunk(self, sections: list[Section]) -> list[Chunk]:
        chunks: list[Chunk] = []
        order = 0
        chapter = sections[0].title if sections else "Document"

        for sec in sections:
            if sec.level <= 1:
                chapter = sec.title
            for piece in self._split(sec.markdown):
                order += 1
                chunks.append(
                    Chunk(
                        chunk_id=f"chunk_{order:04d}",
                        order=order,
                        book=self.book_slug,
                        chapter=chapter,
                        section=sec.title,
                        level=sec.level,
                        page=sec.page,
                        text=piece,
                        tokens=count_tokens(piece),
                        figures=list(sec.figures),
                    )
                )
        log.info("produced %d chunk(s) across %d section(s)", len(chunks), len(sections))
        return chunks

    def _split(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if count_tokens(text) <= self.max_tokens:
            return [text]

        # 1) split on markdown headers, keeping the header with its body
        parts = self._split_on_headers(text)
        # 2) split oversized parts on blank lines
        pieces: list[str] = []
        for part in parts:
            pieces.extend(self._split_on_breaks(part))
        return [p.strip() for p in pieces if p.strip()]

    def _split_on_headers(self, text: str) -> list[str]:
        matches = list(_HEADER_RE.finditer(text))
        if not matches:
            return [text]
        parts: list[str] = []
        if matches[0].start() > 0:
            parts.append(text[: matches[0].start()])
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            parts.append(text[m.start():end])
        return parts

    def _split_on_breaks(self, text: str) -> list[str]:
        if count_tokens(text) <= self.max_tokens:
            return [text]
        paras = re.split(r"\n\s*\n", text)
        out: list[str] = []
        buf: list[str] = []
        buf_tokens = 0
        for para in paras:
            t = count_tokens(para)
            if buf and buf_tokens + t > self.max_tokens:
                out.append("\n\n".join(buf))
                buf, buf_tokens = [], 0
            # hard-split a single oversized paragraph
            if t > self.max_tokens:
                out.append("\n\n".join(buf))
                buf, buf_tokens = [], 0
                out.extend(self._hard_split(para))
                continue
            buf.append(para)
            buf_tokens += t
        if buf:
            out.append("\n\n".join(buf))
        return out

    def _hard_split(self, para: str) -> list[str]:
        words = para.split()
        step = max(1, int(len(words) * self.max_tokens / max(1, count_tokens(para))))
        return [
            " ".join(words[i : i + step])
            for i in range(0, len(words), step)
        ]
