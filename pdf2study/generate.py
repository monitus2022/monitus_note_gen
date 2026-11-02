"""Stage 3: generation (map per chunk, reduce per chapter)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cache import ContentCache, hash_key
from .chunker import Chunk
from .llm.client import OllamaClient
from .logging_setup import get_logger
from .models import Figure
from .prompts import PROMPT_VERSION, qna_fragment_prompt, slide_fragment_prompt
from .validate import dedupe_items, normalize_slides, parse_qna_raw, render_qna, strip_wrappers

log = get_logger("generate")


def caption_figures(client, cache: ContentCache, figures: list[Figure]) -> None:
    """Fill `Figure.alt` for uncaptioned figures via the (multimodal) model."""
    for fig in figures:
        if fig.caption or not fig.image_path:
            continue
        try:
            size = Path(fig.image_path).stat().st_size
        except OSError:
            continue
        key = hash_key(fig.id, size, client.model, PROMPT_VERSION, "caption")

        def produce(path=fig.image_path, hint=fig.caption) -> str:
            return client.caption_image(path, hint).strip()

        fig.alt = cache.cached_text("caption", key, produce)


@dataclass
class ChapterArtifacts:
    index: int
    title: str
    slides_md: str
    qna_md: str


def _group(chunks: list[Chunk]) -> dict[str, list[Chunk]]:
    grouped: dict[str, list[Chunk]] = {}
    for ch in chunks:
        grouped.setdefault(ch.chapter, []).append(ch)
    return grouped


def map_chunk(client: OllamaClient, cache: ContentCache, chunk: Chunk) -> tuple[str, str]:
    """Generate (slide_fragment, raw_qna) for one chunk, cached by content.

    Q&A is cached as the raw delimited text; the MkDocs rendering happens at
    chapter-assembly time so numbering is continuous.
    """
    base = (chunk.text, client.model, PROMPT_VERSION)

    def produce_slides() -> str:
        system, user = slide_fragment_prompt(chunk)
        return normalize_slides(client.chat(system, user))

    def produce_qna() -> str:
        system, user = qna_fragment_prompt(chunk)
        return strip_wrappers(client.chat(system, user))

    slides = cache.cached_text("llm_slides", hash_key(*base, "slides"), produce_slides)
    qna = cache.cached_text("llm_qna", hash_key(*base, "qna"), produce_qna)
    return slides, qna


def generate_chapters(
    client: OllamaClient, cache: ContentCache, chunks: list[Chunk]
) -> list[ChapterArtifacts]:
    out: list[ChapterArtifacts] = []
    for index, (title, chapter_chunks) in enumerate(_group(chunks).items(), start=1):
        slide_parts: list[str] = []
        qna_items = []
        for chunk in chapter_chunks:
            slides, qna_raw = map_chunk(client, cache, chunk)
            if slides.strip():
                slide_parts.append(slides.strip())
            qna_items.extend(parse_qna_raw(qna_raw))
            log.info("generated %s (chapter %d)", chunk.chunk_id, index)
        slides_md = f"# {title}\n\n---\n\n" + "\n\n---\n\n".join(slide_parts) + "\n"
        qna_md = render_qna(dedupe_items(qna_items))
        out.append(ChapterArtifacts(index, title, slides_md, qna_md))
    return out


def write_artifacts(book_tmp: Path, chapters: list[ChapterArtifacts]) -> list[Path]:
    slides_dir = book_tmp / "slides"
    qna_dir = book_tmp / "qna"
    slides_dir.mkdir(parents=True, exist_ok=True)
    qna_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for ch in chapters:
        s = slides_dir / f"chapter_{ch.index:02d}_slides.md"
        q = qna_dir / f"chapter_{ch.index:02d}_qna.md"
        s.write_text(ch.slides_md, encoding="utf-8")
        q.write_text(ch.qna_md, encoding="utf-8")
        written.extend([s, q])
    return written
