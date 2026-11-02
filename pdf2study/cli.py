"""Command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import click

from .config import load_config
from .logging_setup import setup_logging
from .pipeline import run

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
