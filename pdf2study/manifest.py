"""Build the per-book manifest.json that makes the bucket navigable."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chunker import Chunk
from .models import Figure, ParsedDocument


def _group_chapters(parsed: ParsedDocument, chunks: list[Chunk]) -> list[dict[str, Any]]:
    order: list[str] = []
    by_chapter: dict[str, dict[str, Any]] = {}
    for ch in chunks:
        if ch.chapter not in by_chapter:
            by_chapter[ch.chapter] = {
                "index": len(order) + 1,
                "title": ch.chapter,
                "first_page": ch.page,
                "chunks": [],
                "sections": [],
                "figures": [],
            }
            order.append(ch.chapter)
        entry = by_chapter[ch.chapter]
        entry["first_page"] = min(entry["first_page"], ch.page)
        entry["chunks"].append(ch.chunk_id)
        if ch.section not in entry["sections"]:
            entry["sections"].append(ch.section)

    # attach each figure to the chapter whose page range contains it
    ordered = sorted(order, key=lambda t: by_chapter[t]["first_page"])
    for fig in _all_figures(parsed):
        owner = ordered[0] if ordered else None
        for ch_title in ordered:
            if by_chapter[ch_title]["first_page"] <= fig.page:
                owner = ch_title
            else:
                break
        if owner:
            fig_dict = fig.to_dict()
            fig_dict["image_path"] = f"images/{Path(fig.id).name}.png"
            by_chapter[owner]["figures"].append(fig_dict)

    result: list[dict[str, Any]] = []
    for ch_title in order:
        entry = by_chapter[ch_title]
        entry.pop("first_page", None)
        idx = entry["index"]
        entry["slides"] = f"slides/chapter_{idx:02d}_slides.md"
        entry["qna"] = f"qna/chapter_{idx:02d}_qna.md"
        entry["deck_pdf"] = f"decks/chapter_{idx:02d}_slides.pdf"
        entry["deck_pptx"] = f"decks/chapter_{idx:02d}_slides.pptx"
        result.append(entry)
    return result


def _all_figures(parsed: ParsedDocument) -> list[Figure]:
    seen: set[str] = set()
    figs: list[Figure] = []
    for sec in parsed.sections:
        for f in sec.figures:
            if f.id not in seen:
                seen.add(f.id)
                figs.append(f)
    return figs


def build_manifest(
    *,
    slug: str,
    parsed: ParsedDocument,
    chunks: list[Chunk],
    model: str,
    prompt_version: str = "v1",
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": parsed.title or slug,
        "parser": parsed.parser,
        "model": model,
        "prompt_version": prompt_version,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "chapters": _group_chapters(parsed, chunks),
    }
