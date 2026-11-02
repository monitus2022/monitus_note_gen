# pdf2study

Turn PDF textbooks into per-chapter **Marp** slide decks and **MkDocs** Q&A pages,
uploaded to a private **Cloudflare R2** bucket. Runs fully locally via Ollama.

See [`PLAN.MD`](../PLAN.MD) for the full architecture.

## Status

| Milestone | State |
|---|---|
| M1 — deterministic core (parse, figures, chunk, manifest, cache, CLI `--dry-run`) | ✅ done |
| M2 — Ollama generation, map/reduce, Marp render, validation | ⏳ next |
| M3 — live R2 upload + manifest | ⏳ |
| M4 — OCR fallback, VLM captions, Docling backend | ⏳ |

## Install

This machine has an **x86_64 conda** Python first on `PATH`; force the arm64
interpreter so wheels resolve correctly:

```bash
uv sync --extra dev --python /opt/homebrew/bin/python3.12
```

## Usage

```bash
# Deterministic stages only (no LLM, no upload):
uv run pdf2study process books/mybook.pdf --book-slug mybook --dry-run --keep-temp

# Write artifacts then upload to a local sink mirroring the R2 layout:
uv run pdf2study process books/mybook.pdf --book-slug mybook --sink local

# Live upload (requires R2 credentials in .env):
cp pdf2study/.env.example .env   # fill in, then:
uv run pdf2study process books/mybook.pdf --book-slug mybook --sink r2
```

### Key options

| Flag | Meaning |
|---|---|
| `--model-preset smoke\|production` | `qwen3.5:4b` / `qwen3.5:9b` |
| `--model` | explicit Ollama tag (overrides preset) |
| `--parser pymupdf\|docling\|mineru` | parsing backend (only `pymupdf` implemented) |
| `--dry-run` | stop before generation/upload |
| `--limit N` | only the first N chapters |
| `--sink local\|r2` | destination backend |
| `--keep-temp` / `--no-cache` | debugging |

## R2 layout

```text
books/<slug>/
├── manifest.json
├── chunks/chunk_0001.json
└── images/fig_001_0001.png
# slides/, qna/, decks/ are produced in M2+
```

## Tests

```bash
uv run pytest
```
