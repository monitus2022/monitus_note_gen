"""Command-line interface."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from .config import load_config
from .logging_setup import setup_logging
from .pipeline import run
from .publish import publish as publish_notes

MODEL_PRESETS = {"smoke": "qwen3.5:4b", "production": "qwen3.5:9b"}
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4.1-flash-1017"


@click.group()
@click.version_option(package_name="pdf2study")
def main() -> None:
    """Private PDF-to-study pipeline (slides + Q&A -> Cloudflare R2)."""


@main.command()
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--book-slug", required=True, help="Stable identifier for this book, e.g. ai-engineering")
@click.option(
    "--provider",
    type=click.Choice(["openrouter", "ollama"]),
    default=None,
    help="LLM backend (default: openrouter; use 'ollama' for local)",
)
@click.option("--model", default=None, help="Model tag (overrides --model-preset / provider default)")
@click.option(
    "--model-preset",
    type=click.Choice(sorted(MODEL_PRESETS)),
    default=None,
    help="Convenience alias for a local Ollama tier (ignored unless --provider ollama)",
)
@click.option("--parser", type=click.Choice(["pymupdf", "docling", "mineru"]), default="pymupdf", show_default=True)
@click.option("--max-tokens", type=int, default=3500, show_default=True)
@click.option("--concurrency", type=int, default=1, show_default=True)
@click.option("--dpi", type=int, default=200, show_default=True)
@click.option("--caption-vlm/--no-caption-vlm", default=False, help="VLM captions for uncaptioned figures")
@click.option("--ocr", type=click.Choice(["auto", "always", "never"]), default="auto", show_default=True)
@click.option("--keep-temp", is_flag=True, default=False, help="Do not delete tmp_build/ after a run")
@click.option("--dry-run", is_flag=True, default=False, help="Stop after deterministic stages (no upload)")
@click.option("--limit", type=int, default=None, help="Process only the first N chapters")
@click.option("--no-cache", is_flag=True, default=False, help="Disable the content-hash cache")
@click.option("--generate/--no-generate", default=True, help="Run LLM generation (default on)")
@click.option("--render/--no-render", default=True, help="Render PPTX/PDF decks")
@click.option("--sink", type=click.Choice(["local", "r2"]), default="local", show_default=True)
@click.option("--local-sink-dir", type=click.Path(path_type=Path), default=Path("tmp_local_sink"), show_default=True)
@click.option("--tmp-dir", type=click.Path(path_type=Path), default=Path("tmp_build"), show_default=True)
@click.option("--cache-dir", type=click.Path(path_type=Path), default=Path(".cache"), show_default=True)
@click.option("--verbose", is_flag=True, default=False)
def process(
    pdf: Path,
    book_slug: str,
    provider: str | None,
    model: str | None,
    model_preset: str | None,
    parser: str,
    max_tokens: int,
    concurrency: int,
    dpi: int,
    caption_vlm: bool,
    ocr: str,
    keep_temp: bool,
    dry_run: bool,
    limit: int | None,
    no_cache: bool,
    generate: bool,
    render: bool,
    sink: str,
    local_sink_dir: Path,
    tmp_dir: Path,
    cache_dir: Path,
    verbose: bool,
) -> None:
    """Parse PDF, chunk it, write artifacts and (unless --dry-run) upload."""
    setup_logging(verbose)
    if model is None and provider == "ollama":
        model = MODEL_PRESETS.get(model_preset or "smoke")
    cfg = load_config(
        provider=provider,
        model=model,
        parser=parser,
        max_tokens=max_tokens,
        concurrency=concurrency,
        dpi=dpi,
        caption_vlm=caption_vlm,
        ocr=ocr,
        keep_temp=keep_temp,
        dry_run=dry_run,
        limit=limit,
        no_cache=no_cache,
        generate=generate,
        render=render,
        sink=sink,
        local_sink_dir=local_sink_dir,
        tmp_dir=tmp_dir,
        cache_dir=cache_dir,
    )
    summary = run(cfg, pdf, book_slug)
    click.echo(json.dumps(summary, indent=2))


@main.command()
@click.option("--book-slug", required=True)
@click.option("--site-repo", required=True, type=click.Path(path_type=Path), help="Local clone of the MkDocs site repo")
@click.option("--dest", required=True, help="Destination folder under the site's docs/, e.g. books/ai-engineering")
@click.option("--base-branch", default="dev", show_default=True, help="Branch the PR targets")
@click.option("--source", type=click.Choice(["auto", "local", "r2"]), default="auto", show_default=True)
@click.option("--image-base-url", default=None, help="Rewrite figures to <url>/books/<slug>/images/... (else dropped)")
@click.option("--title", default=None, help="Override the book title shown on the index page")
@click.option("--no-push", is_flag=True, default=False, help="Commit locally but do not push")
@click.option("--tmp-dir", type=click.Path(path_type=Path), default=Path("tmp_build"), show_default=True)
@click.option("--verbose", is_flag=True, default=False)
def publish(
    book_slug: str,
    site_repo: Path,
    dest: str,
    base_branch: str,
    source: str,
    image_base_url: str | None,
    title: str | None,
    no_push: bool,
    tmp_dir: Path,
    verbose: bool,
) -> None:
    """Publish generated notes as markdown into the MkDocs site repo (PR branch)."""
    setup_logging(verbose)
    cfg = load_config(tmp_dir=tmp_dir)
    result = publish_notes(
        cfg,
        book_slug,
        site_repo,
        dest,
        base_branch=base_branch,
        source=source,
        image_base_url=image_base_url,
        title=title,
        push=not no_push,
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    click.echo(json.dumps(result, indent=2))
