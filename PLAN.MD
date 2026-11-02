# Architecture & Implementation Plan: `pdf-study-pipeline` (R2 Private Storage)

## 1. System Overview

```
                      [Raw PDF Textbook (Local .gitignore)] 
                                        │
                                        ▼
                           [Stage 1: PyMuPDF Parsing] 
                                        │
                                        ▼
                         [Stage 2: Hierarchical Chunking]
                                        │
                                        ▼
                            [Stage 3: Ollama / Qwen]
                             (Parallel LLM Passes)
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
  [Pass A: Marp Slides]                                 [Pass B: MkDocs Q&A]
             │                                                     │
             ▼                                                     ▼
  [Stage 4: Marp Rendering]                             [Interactive Q&A MD]
  (.pptx & .pdf Generation)                                        │
             │                                                     │
             └──────────────────────────┬──────────────────────────┘
                                        │
                                        ▼
                    [Stage 5: Private R2 Bucket Upload]
                    (All Chunks, Slides, Decks, and Q&A)

```

---

## 2. Updated Technology Stack

* **Language & Runtime:** Python 3.11+
* **LLM Engine:** Local Ollama (`qwen3.5:9b` for 16GB M1 Pro, or `qwen3.5:27b` for 32GB)
* **PDF Parser:** `pymupdf` and `pymupdf4llm`
* **Private Storage:** **Cloudflare R2** via `boto3` (S3 API Endpoint)
* **Slide Generator:** `Marp CLI` (`@marp-team/marp-cli` executed via Python `subprocess`)
* **Local Temp Directory:** `./tmp_build/` (cleared after bucket sync, managed via `.gitignore`)

---

## 3. Cloudflare R2 Bucket Object Key Structure

Everything will be securely stored under an isolated path prefix inside your private R2 bucket (`pdf-study-storage`):

```text
pdf-study-storage/
└── books/
    └── <book_slug>/
        ├── chunks/
        │   ├── chunk_001.json
        │   └── chunk_002.json
        ├── slides/
        │   ├── chapter_1_slides.md
        │   └── chapter_2_slides.md
        ├── decks/
        │   ├── chapter_1_slides.pptx
        │   ├── chapter_1_slides.pdf
        │   ├── chapter_2_slides.pptx
        │   └── chapter_2_slides.pdf
        └── qna/
            ├── chapter_1_qna.md
            └── chapter_2_qna.md

```

---

## 4. Coding Agent Instructions (`AGENTS.md` / OpenCode Directive)

Copy and paste the specification prompt below directly into **OpenCode**.

```markdown
# Task Directive: Private PDF-to-Study Pipeline with Cloudflare R2 Storage

Implement a modular Python command-line utility in a new directory `pdf2study` that ingests PDF textbooks, extracts hierarchical section chunks, utilizes a local Ollama instance (Qwen 3.5) to auto-generate Marp slides and MkDocs-compatible Q&A pages, renders slide decks to PPTX/PDF, and uploads ALL outputs to a private Cloudflare R2 bucket.

## Project Structure

```

pdf2study/
├── main.py
├── parser.py
├── chunker.py
├── r2_storage.py
├── llm_client.py
├── renderer.py
├── prompts.py
├── requirements.txt
├── .env.example
└── README.md

```

---

## Detailed Component Specifications

### Step 1: `requirements.txt` & `.env.example`
`requirements.txt`:
```text
pymupdf>=1.23.0
pymupdf4llm>=0.0.5
boto3>=1.34.0
requests>=2.31.0
click>=8.1.0
tiktoken>=0.5.0
python-dotenv>=1.0.0

```

`.env.example`:

```env
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_BUCKET_NAME=pdf-study-storage

```

### Step 2: `r2_storage.py` (Cloudflare R2 Client)

Create an `R2StorageManager` class using `boto3`:

1. Initialize the S3 client using Cloudflare R2 endpoint:
* `endpoint_url`: `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`
* `aws_access_key_id`: `R2_ACCESS_KEY_ID`
* `aws_secret_access_key`: `R2_SECRET_ACCESS_KEY`
* `region_name`: `auto`


2. Methods:
* `upload_file(local_path: str, r2_key: str)`: Upload local file to R2 bucket.
* `upload_json(data: dict, r2_key: str)`: Serialize dictionary to JSON string and upload directly to R2.
* `sync_build_directory(local_dir: str, book_slug: str)`: Traverse temporary output build directory and upload all files matching the target key structure.



### Step 3: `parser.py`

Create a `PDFParser` class using PyMuPDF:

1. `extract_toc_or_fallback(pdf_path: str) -> List[Dict]`:
* Attempt to call `doc.get_toc()`. If entries exist, map out structured sections with `title`, `level`, and `page`.
* If TOC is empty, scan text spans per page analyzing font sizes (`span["size"]`) and bold styling to locate chapter/section boundaries.


2. `extract_section_content(doc, start_page, end_page) -> str`:
* Use `pymupdf4llm.to_markdown()` for the specific page range to retain Markdown tables, bold text, and code blocks.



### Step 4: `chunker.py`

Create a `HierarchicalChunker` module:

1. Accept extracted sections from `parser.py`.
2. Estimate token count using `tiktoken` (or word count approximation: 1 token ≈ 0.75 words).
3. If a section chunk exceeds `max_tokens` (default: 4000), split along Markdown headers (`##`, `###`), or double line breaks (`\n\n`).
4. Attach parent metadata to every sub-chunk: `{"chapter": ..., "section": ..., "chunk_id": ...}`.

### Step 5: `prompts.py`

Define system prompts:

1. `MARP_SLIDE_PROMPT`: Directs the LLM to write valid Marp slide Markdown separated by `---`. Max 4 bullets per slide.
2. `MKDOCS_QNA_PROMPT`: Directs the LLM to generate Multiple Choice Questions (MCQs) formatted strictly with MkDocs collapsible callout syntax:
```markdown
### Question 1: [Topic Heading]

What is the primary trade-off when implementing parameter-efficient fine-tuning (PEFT)?

- [ ] A) Higher memory usage during training
- [ ] B) Reduced model accuracy compared to zero-shot
- [ ] C) Lower memory footprint at the cost of freezing base model parameters
- [ ] D) Increased latency during inference

??? tip "Reveal Answer & Explanation"
    **Correct Answer:** C

    **Explanation:** PEFT techniques freeze the base model parameters and train a small set of extra parameters, significantly reducing GPU memory requirements during training.

```



### Step 6: `llm_client.py`

Create an `OllamaClient` class:

1. Communicate with local Ollama API (`http://localhost:11434/api/generate`).
2. Configurable model selection (default: `qwen3.5:9b`).
3. Methods:
* `generate_slides(chunk_text: str, meta: dict) -> str`
* `generate_qna(chunk_text: str, meta: dict) -> str`


4. Execute separate isolated requests per chunk with retry logic to avoid context bleed.

### Step 7: `renderer.py`

Create a `MarpRenderer` module:

1. Execute system commands using Python `subprocess.run`:
* `npx @marp-team/marp-cli <input_md> --pptx -o <output_pptx>`
* `npx @marp-team/marp-cli <input_md> --pdf -o <output_pdf>`


2. Catch errors gracefully if Node/NPX is missing, alerting the user while preserving raw generated `.md` files.

### Step 8: `main.py`

Create a CLI interface using `click`:

```bash
python main.py process path/to/book.pdf --model qwen3.5:9b --book-slug ai-engineering

```

CLI Steps:

1. Parse PDF and extract structural chunks.
2. Store extracted text chunks into `./tmp_build/<book_slug>/chunks/`.
3. Process chunks through `OllamaClient` to generate slide `.md` files and Q&A `.md` files into `./tmp_build/<book_slug>/slides/` and `./tmp_build/<book_slug>/qna/`.
4. Call `MarpRenderer` to render PPTX and PDF decks into `./tmp_build/<book_slug>/decks/`.
5. Invoke `R2StorageManager.sync_build_directory()` to upload all files to Cloudflare R2 under `books/<book_slug>/`.
6. Clean up `./tmp_build/` directory locally after successful sync.

```

```
