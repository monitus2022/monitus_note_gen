# pdf2study

Turn PDF textbooks into per-chapter **Marp** slide decks and **MkDocs** Q&A pages,
uploaded to a private **Cloudflare R2** bucket. Runs fully locally via Ollama.

See [`PLAN.MD`](../PLAN.MD) for the full architecture.

## Status

| Milestone | State |
|---|---|
| M1 — deterministic core (parse, figures, chunk, manifest, cache, CLI `--dry-run`) | ✅ done |
| M2 — Ollama generation, map/reduce, Marp PDF + python-pptx render, validation | ✅ done (smoke-tested) |
| M3 — live R2 upload + manifest | ⏳ blocked: bucket `pdf-study-storage` must be created |
| M4 — OCR fallback, VLM captions; Docling backend | 🔬 OCR + VLM captions done, Docling deferred |

- **OCR** (`ocr.py`): detects image-only pages and runs `ocrmypdf` when present
  (`--ocr auto|always|never`); warns and continues if it isn't installed.
- **VLM captions** (`--caption-vlm`): uncaptioned figures get one-sentence
  descriptions from the multimodal `qwen3.5` model (cached).
- **Docling backend**: not implemented (heavy dependency; not installed). `--parser pymupdf` only.

### Generation model

Slides are requested as Marp Markdown. Q&A is **not** requested as MkDocs markdown:
the model returns a simple delimited form (`Q:` / `A)`–`D)` / `ANSWER:` / `WHY:`)
and `pdf2study` renders the `??? tip` callouts itself. This keeps small models from
corrupting the final format. Thinking is disabled (`think: false`) and any reasoning
traces are stripped as a fallback.

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

# Cloud generation (default provider) then upload to a local sink:
uv run pdf2study process books/mybook.pdf --book-slug mybook --sink local

# Local generation via Ollama (no cloud, no cost):
uv run pdf2study process books/mybook.pdf --book-slug mybook \
  --provider ollama --model-preset smoke

# Live upload (requires R2 credentials in .env):
cp pdf2study/.env.example .env   # fill in, then:
uv run pdf2study process books/mybook.pdf --book-slug mybook --sink r2
```

### Model provider

| Provider | Default model | Notes |
|---|---|---|
| `openrouter` (default) | `deepseek/deepseek-v4.1-flash-1017` | cloud; needs `OPENROUTER_API_KEY` |
| `ollama` | `qwen3.5:4b` (`smoke`) / `qwen3.5:9b` (`production`) | local, free, keeps data on-device |

The full book is ~310 chunks / ~350k input + ~190k output tokens — roughly **$0.15–$1.00**
on OpenRouter depending on model. Both providers implement the same client interface
(`chat`, `caption_image`), so switching is a single flag.

### Key options

| Flag | Meaning |
|---|---|
| `--provider openrouter\|ollama` | LLM backend (default openrouter) |
| `--model-preset smoke\|production` | local Ollama tag (`qwen3.5:4b` / `:9b`) |
| `--model` | explicit model tag (overrides preset / provider default) |
| `--parser pymupdf\|docling\|mineru` | parsing backend (only `pymupdf` implemented) |
| `--dry-run` | stop before generation/upload |
| `--limit N` | only the first N chapters |
| `--sink local\|r2` | destination backend |
| `--generate/--no-generate` | run LLM generation (default on) |
| `--render/--no-render` | render PPTX/PDF decks (default on) |
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
