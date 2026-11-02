# Architecture & Implementation Plan: `pdf2study` (Private R2 Storage)

> Repo: `monitus_note_gen` · Package/CLI: `pdf2study`
> (The old document mixed three names — `pdf-study-pipeline`, `pdf2study`, `monitus_note_gen`. This plan standardizes on package `pdf2study` inside the `monitus_note_gen` repo.)

---

## 1. System Overview

```text
        [Raw PDF Textbook (local, .gitignore)]
                     │
                     ▼
      [Stage 0: OCR Fallback Check] ──(no text layer)──▶ [ocrmypdf] ──┐
                     │                                                │
                     ▼◀───────────────────────────────────────────────┘
      [Stage 1: Layout Parsing (Docling / MinerU)]
        • reading order, headings, tables, formulas
        • figure regions + captions
        • (fallback) PyMuPDF only
                     │
                     ├──────────────▶ [Stage 1b: Figure Extraction]
                     │                  rasterize regions, filter logos,
                     │                  reuse PDF captions, optional VLM
                     ▼
      [Stage 2: Hierarchical Chunking]  (token-budgeted, header-aware)
                     │
                     ▼
      [Stage 3a: MAP — per chunk, small prompts]
         ├── Pass A: slide fragment (Marp)
         └── Pass B: Q&A items (MCQ, MkDocs callouts)
                     │
                     ▼
      [Stage 3b: REDUCE — per chapter, fragments only]
         • deterministic concatenation + dedupe
         • optional editorial pass (order, dividers, validity, style)
                     │
                     ▼
      [Stage 4: Rendering]  (Marp CLI → PPTX + PDF)
                     │
                     ▼
      [Stage 5: Private R2 Upload]
         books/<slug>/{manifest.json, chunks, slides, qna, decks, images}
                     │
                     ▼
      [Stage 6: Cleanup]  (only after successful sync)
```

Key principle: **chapter-level artifacts, chunk-level prompts.** A chapter is never fed to the LLM at once; see §6.

---

## 2. Goals / Non-Goals

**Goals**
- Turn a PDF textbook into (a) per-chapter Marp slide decks (PPTX + PDF) and (b) per-chapter MkDocs Q&A pages.
- Include textbook **figures** in the material with captions/alt-text.
- Run fully locally (Ollama) and store everything in a private Cloudflare R2 bucket.
- Be **resumable**: a crash must not regenerate completed work.
- Produce **validated** output (valid Marp + valid MkDocs), not raw model text.

**Non-Goals**
- No chat/RAG serving layer (metadata is designed to make one possible later).
- No multi-tenant auth; R2 credentials are operator-supplied.
- No real-time generation; this is a batch CLI.

---

## 3. Technology Stack

| Concern | Choice | Notes |
|---|---|---|
| Runtime | Python 3.11+ | |
| Layout parsing | **Docling** (primary), **MinerU** (optional) | reading order, tables, figure regions + captions |
| Low-level PDF | **PyMuPDF** | figure rasterization, OCR detection, `--parser pymupdf` fallback |
| OCR | **ocrmypdf** (+ Tesseract) | only when a page has no text layer |
| LLM | Local **Ollama** | staged rollout: smoke tier → production tier (§7); verify tags |
| VLM (optional) | Ollama vision model | only for figures lacking a caption |
| Storage | **Cloudflare R2** via `boto3` | S3 API |
| Slides | **Marp CLI** | rendered through `subprocess` |
| CLI | `click` | |
| Config | `python-dotenv` + CLI flags | |
| Token estimate | `tiktoken` (approx.) or word-count | approximate is fine; Qwen tokenizer differs |

> **Watch:** confirm the Ollama tags before coding. Earlier drafts referenced `qwen3.5:9b` / `:27b`, which may not exist. Pick real tags (e.g. a Qwen3 dense/MoE text model + a Qwen-VL vision model) and make them configurable. 27B-class models are tight on 32 GB once context + a concurrent pass are loaded.

### `requirements.txt` (pin exact versions)

```text
pymupdf==<pin>
docling==<pin>          # primary parser
boto3==<pin>
click==<pin>
python-dotenv==<pin>
tiktoken==<pin>         # optional, approximate
# optional:
# mineru==<pin>         # alternate parser
# ocrmypdf==<pin>       # OCR fallback
```

### `.env.example`

```env
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_BUCKET_NAME=pdf-study-storage
OLLAMA_HOST=http://localhost:11434
```

---

## 4. Stage 1 — Layout Parsing

Create a `PDFParser` abstraction with pluggable backends so the pipeline doesn't care which engine runs.

```python
class PDFParser(Protocol):
    def parse(self, pdf_path: str) -> "ParsedDocument": ...
```

`ParsedDocument` is a normalized model independent of backend:

```python
@dataclass
class Figure:
    id: str            # e.g. "fig_03_002"
    page: int
    bbox: tuple        # (x0, y0, x1, y1) in PDF points
    caption: str | None
    kind: str          # "raster" | "vector" | "table"

@dataclass
class Section:
    title: str
    level: int
    page: int
    markdown: str
    figures: list[Figure]

@dataclass
class ParsedDocument:
    title: str | None
    toc: list[dict]
    sections: list[Section]
    parser: str        # "docling" | "mineru" | "pymupdf"
```

**Backends**
- `DoclingParser` (default): `DocumentConverter` → structured doc. Gives reading order, heading hierarchy, `PictureItem`s with caption association, TableFormer tables. Replaces the fragile font-size TOC heuristic entirely.
- `MinerUParser` (optional): `--parser mineru`; strongest on formulas/scientific layout.
- `PyMuPDFParser` (fallback): `pymupdf4llm.to_markdown()` for the whole document **once** (not per section), plus `doc.get_toc()` with a heading heuristic when TOC is empty.

**Efficiency rule:** convert the document to Markdown **once**, then slice sections from it. Never re-parse page ranges per section.

---

## 5. Stage 1b — Figure Extraction & Captioning

The rule: **rasterize regions, don't just call `get_images()`.** Vector charts return no embedded image.

1. **Collect candidate regions**
   - Raster embedded images: `page.get_image_info(hashes=True, xrefs=True)` (bbox + dedupe digest).
   - Vector figures: cluster `page.get_drawings()` bounding boxes above a size threshold.
   - Or take `PictureItem` regions directly from Docling.
2. **Rasterize** each region: `page.get_pixmap(clip=rect, dpi=200)` → `tmp_build/<slug>/images/<fig_id>.png`. Uniform output for raster, vector, and table-complex cases.
3. **Filter junk**
   - Drop images smaller than a threshold (e.g. min side < 50 px).
   - Drop any image whose dedupe hash appears on more than N pages (logos / watermarks / headers).
4. **Captions**
   - **Primary: reuse the real PDF caption** associated by the layout model (accurate + free).
   - **Optional (`--caption-vlm`):** only for figures *without* a caption, run a VLM to produce a caption + alt-text. Reasoning: textbooks' own captions beat a VLM's; don't pay VLM cost where a real caption exists.
5. **Provenance:** every figure records `page`, `bbox`, `caption`, `alt`, and the `chunk_id`/section that references it (scan body text for "Figure N" mentions to link them).
6. **DPI:** ~150–200 for slides; higher only if OCR'ing figure text.

> **Marp gotcha:** Marp CLI blocks local file access by default. Rendering slides that reference images requires `--allow-local-files`, or images render broken/blank.

---

## 6. Stage 2–3 — Chunking & Context Strategy (map-reduce)

### 2. Chunking (`HierarchicalChunker`)
- Consume `ParsedDocument.sections`.
- Estimate tokens (`tiktoken` approx. or word count; label as an estimate).
- If a section exceeds `max_tokens` (default **3500**), split on Markdown headers (`##`, `###`) then on `\n\n`.
- Attach parent metadata to every chunk: `{book, chapter, section, chunk_id, order}`.
- Store each chunk as JSON under `chunks/`.

### 3a. Map — per chunk (small prompts)
For each chunk, two isolated requests (never share context between chunks):
- `generate_slide_fragment(chunk, meta) -> str` (Marp markdown fragment)
- `generate_qna_items(chunk, meta) -> list[QnAItem]` (MCQ items)

Both prompts stay ~2–4k tokens → safe for the context window and better latency/quality than giant prompts.

### 3b. Reduce — per chapter (fragments only)
- **Slides:** concatenate fragments in chapter order; insert a section-divider slide per top-level section. An optional **editor pass** sees only titles/bullets (short) to dedupe, reorder, unify style, and enforce Marp validity.
- **Q&A:** concatenate items; dedupe by question hash; optional editor pass for phrasing/answer-key consistency.
- Output one `chapter_NN_slides.md` and one `chapter_NN_qna.md` per chapter.

> This is why "per chapter" is safe: the LLM only ever sees one chunk (map) or the already-generated short fragments (reduce). No chapter is ever fed in whole.

---

## 7. Stage 3 — LLM Client & Prompting

`OllamaClient`:
- Talks to `http://localhost:11434/api/generate` (or the `ollama` Python client).
- Configurable text model; separate configurable VLM for `--caption-vlm`.
- Methods: `generate_slide_fragment`, `generate_qna_items`, `edit_chapter`, `caption_figure`.
- Retry with backoff on transient failures; strict "output only markdown" instruction.

**Note on parallelism:** Ollama serializes requests by default (`OLLAMA_NUM_PARALLEL`). Running the slide and Q&A passes concurrently can double memory. Keep concurrency configurable (`--concurrency`) and default to 1.

`prompts.py`:
- `MARP_FRAGMENT_PROMPT` — valid Marp markdown, ≤4 bullets/slide, no front matter, no code fences.
- `QNA_PROMPT` — MCQ items in MkDocs collapsible callout form (see §9).
- `CHAPTER_EDITOR_PROMPT` — dedupe/reorder/style over fragments only.
- `FIGURE_CAPTION_PROMPT` — VLM caption + alt-text.

All prompts carry a `prompt_version` string that participates in the cache key (§13).

### Model Strategy: Staged Rollout (small → larger)

Start with a **small model as a vertical slice**, not as a content-quality verdict. Model size and
pipeline correctness are independent axes.

- **Smoke-test tier** (e.g. a Qwen3-4B-class model, Q4_K_M): fast and low-memory. Use `--limit 2`
  to exercise the *entire* pipeline end-to-end — parse → figures → chunk → map/reduce → validate →
  Marp render → R2 → manifest. Judge the **plumbing** (does Marp actually render? are `??? tip`
  callouts valid? do figure paths resolve?), **not** the notes.
- **Production tier** (e.g. a Qwen3-8B/9B-class model): swap in with `--model` once the pipeline is
  proven. Better format adherence and content quality.

**Why the swap is cheap:** the cache key includes the model, so switching models invalidates **only
LLM caches**. Parsing, OCR, figure, and caption caches survive → the re-run is incremental.

Caveats:
- A small model violates strict Marp/MkDocs formatting more often. Extra validation failures are a
  signal that the repair layer (§12) is working — not a reason to abandon the small model.
- Keep prompts identical across tiers; don't tune prompts to compensate for small-model quirks
  (that would optimize for the wrong target).
- Verify real Ollama tags exist for **both** tiers before coding.
- Convenience: expose `--model-preset smoke|production` so switching tiers is one flag.

---

## 8. Stage 4 — Rendering (`MarpRenderer`)

System commands via `subprocess.run`:

```bash
npx @marp-team/marp-cli <input_md> --pptx -o <out.pptx> --allow-local-files
npx @marp-team/marp-cli <input_md> --pdf  -o <out.pdf>  --allow-local-files
```

Dependencies to document and detect:
- `--pdf` requires a headless **Chrome/Chromium**.
- `--pptx` requires **LibreOffice** (`soffice`) available on PATH.
- If Node/Chrome/LibreOffice are missing, catch the error, warn clearly, and **preserve the raw `.md` + images** so nothing generated is lost.

---

## 9. Q&A Format & MkDocs Configuration

Prompt output (MCQ):

```markdown
### Question 1: [Topic]

What is the primary trade-off when implementing PEFT?

- [ ] A) Higher memory usage during training
- [ ] B) Reduced model accuracy compared to zero-shot
- [ ] C) Lower memory footprint at the cost of freezing base model parameters
- [ ] D) Increased latency during inference

??? tip "Reveal Answer & Explanation"
    **Correct Answer:** C

    **Explanation:** PEFT freezes base parameters and trains a small set of extras, reducing memory.
```

Required MkDocs extensions (document these — `???` silently fails otherwise):

```yaml
markdown_extensions:
  - pymdownx.details
  - pymdownx.superfences
  - attr_list
```

> Note: `- [ ]` renders as task-list checkboxes, not radio buttons. That is acceptable for self-study, but if you want true selectable answers, either keep the callout answer or switch to a small JS/HTML block. Decide per taste; default is the callout form above.

---

## 10. Stage 5 — Cloudflare R2 Layout

```text
pdf-study-storage/
└── books/
    └── <book_slug>/
        ├── manifest.json
        ├── chunks/
        │   └── chunk_001.json
        ├── slides/
        │   ├── chapter_01_slides.md
        │   └── chapter_02_slides.md
        ├── qna/
        │   ├── chapter_01_qna.md
        │   └── chapter_02_qna.md
        ├── decks/
        │   ├── chapter_01_slides.pptx
        │   ├── chapter_01_slides.pdf
        │   └── ...
        └── images/
            ├── fig_01_001.png
            └── fig_02_003.png
```

`manifest.json` (the missing piece that makes the bucket navigable):

```json
{
  "slug": "ai-engineering",
  "title": "AI Engineering",
  "parser": "docling",
  "model": "<ollama-tag>",
  "prompt_version": "v1",
  "generated_at": "2026-11-02T12:00:00Z",
  "chapters": [
    {
      "index": 1,
      "title": "Introduction",
      "slides": "slides/chapter_01_slides.md",
      "deck_pptx": "decks/chapter_01_slides.pptx",
      "deck_pdf": "decks/chapter_01_slides.pdf",
      "qna": "qna/chapter_01_qna.md",
      "chunks": ["chunks/chunk_001.json"],
      "figures": [
        {"id": "fig_01_001", "image": "images/fig_01_001.png", "caption": "Figure 1.1 ..."}
      ]
    }
  ]
}
```

`R2StorageManager`:
- `upload_file(local_path, r2_key)` — sets correct `ContentType` per extension.
- `upload_json(data, r2_key)`.
- `sync_build_directory(local_dir, book_slug)` — generic walk; maps relative paths to `books/<slug>/...`; writes `manifest.json` last.

---

## 11. Stage 0 — OCR Fallback

- Before parsing, detect pages whose extracted text is empty or below a threshold (`page.get_text().strip()`).
- If any are found and OCR is enabled, run `ocrmypdf` to add a text layer, then re-parse the OCR'd PDF.
- Flag: `--ocr auto|always|never` (default `auto`). `auto` = OCR only when text-less pages exist.
- Cache the OCR'd PDF so it isn't recomputed.

---

## 12. Validation & Repair (never trust raw model output)

Post-process every LLM artifact before use:
- Strip surrounding ```markdown / ``` fences.
- **Slides:** ensure `---` separators are at line starts and not accidentally split inside content; no stray front matter; each slide has a heading; referenced image paths exist.
- **Q&A:** validate `??? tip "..."` blocks are followed by 4-space-indented bodies; options present; answer key is one of A–D.
- On failure, retry once with a stricter prompt; if it still fails, fall back to the raw fragment and log a warning.
- Optionally flag low-confidence answer keys for later human review.

---

## 13. Resume & Caching (primary hardening)

- Compute a **cache key** = `sha256(chunk_text + model + prompt_version + task)` for each unit of work.
- Store outputs under a local cache dir (`.cache/<slug>/`) keyed by that hash:
  - per-chunk slide fragment
  - per-chunk Q&A items
  - per-chapter reduce result
  - figure captions
  - parsed document + OCR result
- On run, **skip any unit whose cache entry exists**. Add `--no-cache` to force.
- This makes a long textbook run resumable across crashes and cheap to re-run after prompt tweaks (only affected caches invalidate via `prompt_version`).

---

## 14. CLI & Configuration

```bash
python -m pdf2study process path/to/book.pdf \
  --book-slug ai-engineering \
  --model <ollama-text-tag> \   # explicit tag
  --model-preset smoke|production \  # convenience alias (overridden by --model)
  --parser docling \        # docling | mineru | pymupdf
  --ocr auto \
  --caption-vlm \           # opt-in VLM captions for uncaptioned figures
  --concurrency 1 \
  --max-tokens 3500 \
  --keep-temp \
  --dry-run \               # parse + chunk only, no LLM/R2
  --limit 2                 # process first N chapters (testing)
```

Pipeline steps:
1. OCR check (+ optional OCR).
2. Parse → `ParsedDocument`; extract figures.
3. Chunk → `tmp_build/<slug>/chunks/`.
4. Map: per-chunk slide fragments + Q&A items (cached).
5. Reduce: per-chapter slide decks + Q&A (cached).
6. Render PPTX/PDF into `decks/`.
7. Write `manifest.json`; `sync_build_directory()` → R2.
8. Clean `tmp_build/` **only on full success** (never on failure; honor `--keep-temp`).

---

## 15. Logging, Errors, Observability

- Structured logging (`logging`), per-stage progress with counts.
- Clear, actionable errors for: no text layer + OCR disabled, missing Node/Chrome/LibreOffice, Ollama unreachable, R2 auth failure.
- Per-book run summary: chapters, chunks, figures, cache hits, failures.

---

## 16. Testing & Dry-Run

- `--dry-run` and `--limit` for fast iteration without LLM/R2.
- Unit tests: chunker token/split behavior, prompt-output validators, cache-key stability, R2 key mapping.
- Fixture: a small multi-page PDF with a raster figure, a vector chart, a table, and one text-less (scanned) page to exercise OCR + figure paths.

---

## 17. Project Structure

```text
pdf2study/
├── __init__.py
├── main.py              # click CLI
├── parser.py            # PDFParser protocol + Docling/MinerU/PyMuPDF backends
├── figures.py           # region detection, rasterization, filtering, captioning
├── ocr.py               # text-layer detection + ocrmypdf fallback
├── chunker.py           # HierarchicalChunker
├── llm_client.py        # OllamaClient (text + VLM)
├── prompts.py           # prompt templates + prompt_version
├── validate.py          # Marp/MkDocs output validation & repair
├── reduce.py            # chapter assembly/editor pass
├── cache.py             # content-hash cache
├── renderer.py          # MarpRenderer
├── r2_storage.py        # R2StorageManager
├── manifest.py          # manifest.json builder
├── requirements.txt
├── .env.example
├── mkdocs.example.yml   # required extensions
└── README.md
```

---

## 18. Implementation Phases

0. **Smoke test (small model):** once phases 1–7 exist, run the full pipeline with the
   smoke-test tier on `--limit 2`. Only after the plumbing is green, switch to the production
   model and regenerate (LLM caches invalidate; parse/figure caches survive).
1. **Skeleton + config**: CLI, `.env`, cache module, logging. `--dry-run` end-to-end.
2. **Parsing**: PyMuPDF fallback first (fast to validate), then Docling backend + normalized model.
3. **Figures**: region detection, rasterization, filtering, PDF-caption reuse.
4. **Chunking + map generation**: slide fragments + Q&A items, validation/repair, caching.
5. **Reduce + rendering**: chapter assembly + Marp (`--allow-local-files`, dependency detection).
6. **R2 + manifest**: upload, generic sync, manifest.
7. **OCR fallback** + optional VLM captioning.
8. **Tests + docs**.

---

## 19. Open Decisions / Risks

- **Ollama model tags**: must be verified, not assumed (for both smoke and production tiers).
- **Do not judge content quality from the smoke-test tier**: it validates plumbing only.
- **Prompt drift across tiers**: keep prompts identical so 4B tuning doesn't cap 9B quality.
- **Docling/MinerU dependency weight** (torch, models): document install size; keep PyMuPDF path usable without them.
- **`--pptx` requires LibreOffice, `--pdf` requires Chrome**: environment-dependent; fail loudly.
- **MCQ answer-key correctness**: only mitigated by validation/flagging, not solved; consider an optional verification pass.
- **tiktoken ≠ Qwen tokenizer**: budgets are approximations.
- **Figure dedupe thresholds**: tune on real books (logos/watermarks vary).

---

## 20. Coding Agent Directive (embeddable)

```markdown
# Task: Private PDF-to-Study Pipeline (`pdf2study`) with Cloudflare R2

Implement a modular Python CLI (`python -m pdf2study`) that ingests a PDF textbook and produces,
per chapter: a Marp slide deck (PPTX + PDF) and an MkDocs Q&A page, then uploads everything to a
private Cloudflare R2 bucket.

Requirements:
- Layout-aware parsing (Docling primary; optional MinerU; PyMuPDF fallback) producing a normalized
  ParsedDocument with sections, tables, and figure regions + captions.
- Figure handling: rasterize regions (not just embedded images), filter logos/watermarks, reuse PDF
  captions, optional opt-in VLM captions+alt-text.
- OCR fallback (ocrmypdf) when pages lack a text layer.
- Chunking with parent metadata; token budget ~3500.
- Map-reduce generation per chapter: per-chunk slide fragments + Q&A items, then per-chapter assembly.
- Output validation/repair (strip fences; enforce valid Marp `---` and MkDocs `??? tip` blocks).
- Content-hash caching for resumability; --no-cache to override.
- Marp rendering with --allow-local-files; detect Node/Chrome/LibreOffice and degrade gracefully.
- R2 upload of chunks, slides, qna, decks, images, and a manifest.json.
- Clean tmp_build/ only on success; support --dry-run, --limit, --keep-temp, --concurrency.

Deliverables: the module tree in §17, pinned requirements.txt, .env.example, mkdocs.example.yml,
README, and tests.
```
