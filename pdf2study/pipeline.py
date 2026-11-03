"""Pipeline orchestration: deterministic stages for milestone 1.

Stages implemented here: parse -> figures -> chunk -> write artifacts ->
manifest -> upload. LLM generation, reduction, rendering and OCR are added in
later milestones.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pymupdf as fitz  # PyMuPDF (new module name)

from .cache import ContentCache, hash_key
from .chunker import HierarchicalChunker
from .config import Config
from .figures import attach_figures_to_sections, collect_figures
from .generate import caption_figures, generate_chapters, write_artifacts
from .llm import build_client
from .logging_setup import get_logger
from .manifest import build_manifest
from .models import ParsedDocument, Section
from .ocr import maybe_ocr
from .parser import PyMuPDFParser
from .render import render_epub, render_pdf, render_pptx
from .storage import LocalSink, R2StorageManager, sync_directory
from .validate import markdown_to_text

log = get_logger("pipeline")


def sha256_file(path: str | Path, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def _parser_for(cfg: Config):
    if cfg.parser == "pymupdf":
        return PyMuPDFParser()
    raise NotImplementedError(
        f"parser '{cfg.parser}' is not implemented yet (milestone 4). Use --parser pymupdf."
    )


def _serialize_parsed(parsed: ParsedDocument) -> dict:
    return {
        "title": parsed.title,
        "parser": parsed.parser,
        "toc": parsed.toc,
        "sections": [
            {"title": s.title, "level": s.level, "page": s.page, "markdown": s.markdown}
            for s in parsed.sections
        ],
    }


def _parse(cfg: Config, doc: fitz.Document, pdf_path: Path, cache: ContentCache) -> ParsedDocument:
    if not cache.enabled:
        return _parser_for(cfg).parse(str(pdf_path), dpi=cfg.dpi)

    key = hash_key(sha256_file(pdf_path), cfg.parser)
    cached = cache.get_json("parse", key)
    if cached:
        log.info("using cached parse (%d sections)", len(cached.get("sections", [])))
        return ParsedDocument(
            title=cached.get("title"),
            toc=cached.get("toc", []),
            parser=cached.get("parser", cfg.parser),
            sections=[Section(**s) for s in cached.get("sections", [])],
        )

    parsed = _parser_for(cfg).parse(str(pdf_path), dpi=cfg.dpi)
    cache.put_json("parse", key, _serialize_parsed(parsed))
    return parsed


def _limit_sections(sections: list[Section], n_chapters: int) -> tuple[list[Section], int | None]:
    """Keep only the first `n_chapters` top-level sections.

    Returns the kept sections and the last page they cover (so figure extraction
    can be limited to the same range).
    """
    starts = [i for i, s in enumerate(sections) if s.level <= 1]
    if len(starts) <= n_chapters:
        return sections, None
    end = starts[n_chapters]
    last_page = sections[end].page - 1
    return sections[:end], last_page


def _backend(cfg: Config):
    if cfg.sink == "r2":
        return R2StorageManager(cfg.r2)
    return LocalSink(cfg.local_sink_dir)


def _render_decks(book_tmp: Path, chapters) -> None:
    slides_dir = book_tmp / "slides"
    decks_dir = book_tmp / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    for ch in chapters:
        md = slides_dir / f"chapter_{ch.index:02d}_slides.md"
        render_pptx(md, decks_dir / f"chapter_{ch.index:02d}_slides.pptx")
        render_pdf(md, decks_dir / f"chapter_{ch.index:02d}_slides.pdf")


def run(cfg: Config, pdf_path: str | Path, slug: str, client=None) -> dict:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    book_tmp = Path(cfg.tmp_dir) / slug
    images_dir = book_tmp / "images"
    chunks_dir = book_tmp / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    cache = ContentCache(Path(cfg.cache_dir) / slug, enabled=not cfg.no_cache)

    effective_pdf = maybe_ocr(cfg, pdf_path, slug)
    doc = fitz.open(effective_pdf)
    try:
        parsed = _parse(cfg, doc, effective_pdf, cache)
        limit_page: int | None = None
        if cfg.limit:
            parsed.sections, limit_page = _limit_sections(parsed.sections, cfg.limit)
        pages = set(range(1, limit_page + 1)) if limit_page else None
        figures = collect_figures(doc, images_dir, dpi=cfg.dpi, slug="fig", pages=pages)
    finally:
        doc.close()

    if cfg.caption_vlm and not cfg.dry_run:
        client = client or build_client(cfg)
        caption_figures(client, cache, figures)

    attach_figures_to_sections(parsed.sections, figures)

    chunks = HierarchicalChunker(slug, max_tokens=cfg.max_tokens).chunk(parsed.sections)
    for ch in chunks:
        (chunks_dir / f"{ch.chunk_id}.json").write_text(
            json.dumps(ch.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    manifest = build_manifest(slug=slug, parsed=parsed, chunks=chunks, model=cfg.model)
    (book_tmp / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fulltext_chars = 0
    if cfg.fulltext:
        fulltext = markdown_to_text("\n\n".join(s.markdown for s in parsed.sections))
        (book_tmp / "fulltext.txt").write_text(fulltext, encoding="utf-8")
        fulltext_chars = len(fulltext)
        log.info("wrote fulltext.txt (%d chars)", fulltext_chars)

    summary = {
        "slug": slug,
        "sections": len(parsed.sections),
        "chapters": len(manifest["chapters"]),
        "chunks": len(chunks),
        "figures": len(figures),
        "fulltext_chars": fulltext_chars,
        "tmp_dir": str(book_tmp),
        "dry_run": cfg.dry_run,
    }

    if cfg.dry_run:
        log.info("dry-run: stopping before generation/upload")
        return summary

    if cfg.generate:
        client = client or build_client(cfg)
        chapters = generate_chapters(client, cache, chunks, concurrency=cfg.concurrency)
        write_artifacts(book_tmp, chapters)
        summary["chapters_generated"] = len(chapters)
        if cfg.render:
            _render_decks(book_tmp, chapters)
        if cfg.epub:
            render_epub(
                chapters,
                images_dir,
                book_tmp / f"{slug}.epub",
                title=parsed.title or slug,
                slug=slug,
            )
            summary["epub"] = f"{slug}.epub"

    backend = _backend(cfg)
    prefix = f"books/{slug}"
    sync_directory(backend, book_tmp, prefix)
    summary["uploaded_to"] = f"{cfg.sink}:{prefix}"
    summary["sink"] = cfg.sink

    if cfg.r2_public_bucket and images_dir.exists() and any(images_dir.iterdir()):
        try:
            pub = R2StorageManager(cfg.r2, bucket=cfg.r2_public_bucket)
            public_prefix = f"books/{slug}/images"
            sync_directory(pub, images_dir, public_prefix)
            summary["public_images"] = f"r2:{cfg.r2_public_bucket}/{public_prefix}"
        except Exception as exc:  # noqa: BLE001 - public hosting is optional
            log.warning("public figure upload failed (continuing): %s", exc)

    if not cfg.keep_temp:
        shutil.rmtree(book_tmp, ignore_errors=True)
        log.info("cleaned %s", book_tmp)

    return summary
