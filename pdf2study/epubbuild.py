"""Rebuild a book's EPUB from already-produced artifacts (R2 or local)."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .generate import ChapterArtifacts
from .logging_setup import get_logger
from .publish import load_source
from .render.epub import image_names, render_epub

log = get_logger("epub")


def _fetch_images(cfg: Config, slug: str, names: list[str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    missing = [n for n in names if not (dest / n).exists()]
    if not missing:
        return
    if not cfg.r2.is_complete():
        log.warning("%d image(s) not found locally and R2 not configured", len(missing))
        return
    import boto3

    r2 = cfg.r2
    cl = boto3.client(
        "s3",
        endpoint_url=r2.endpoint_url,
        aws_access_key_id=r2.access_key_id,
        aws_secret_access_key=r2.secret_access_key,
        region_name="auto",
    )
    for name in missing:
        try:
            data = cl.get_object(Bucket=r2.bucket, Key=f"books/{slug}/images/{name}")["Body"].read()
            (dest / name).write_bytes(data)
        except Exception as exc:  # noqa: BLE001
            log.warning("could not fetch image %s: %s", name, exc)


def build_book_epub(
    cfg: Config,
    slug: str,
    *,
    source: str = "auto",
    out_path: str | Path | None = None,
    title: str | None = None,
) -> Path:
    manifest, slides, qna = load_source(cfg, slug, source)
    title = title or manifest.get("title") or slug
    chapters = [
        ChapterArtifacts(ch["index"], ch["title"], slides.get(ch["index"], ""), qna.get(ch["index"], ""))
        for ch in manifest["chapters"]
    ]

    images_dir = Path(cfg.tmp_dir) / slug / "images"
    names = image_names(*[c.slides_md for c in chapters])
    _fetch_images(cfg, slug, names, images_dir)

    out_path = Path(out_path) if out_path else Path(cfg.tmp_dir) / slug / f"{slug}.epub"
    render_epub(chapters, images_dir, out_path, title=title, slug=slug)
    return out_path
