# Architecture & Implementation Plan: `monitus_note_gen`

## 1. System Overview

```
                                  +---------------------------------------+
                                  |            Input PDF File             |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |    Stage 1: Layout-Aware Parsing      |
                                  |      (PyMuPDF / PyMuPDF4LLM)          |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |    Stage 2: Hierarchical Chunking     |
                                  |   (TOC First -> Font/Heading Fallback)|
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      Stage 3: LLM Processing          |
                                  |      (Ollama Local API / Qwen)        |
                                  +---------+-------------------+---------+
                                            |                   |
                                            v                   v
                             +----------------------+   +----------------------+
                             | Pass 3A: Marp Slides |   |  Pass 3B: MkDocs Q&A |
                             +----------+-----------+   +----------+-----------+
                                        |                          |
                                        v                          v
                             +----------------------+   +----------------------+
                             |  Stage 4: Rendering  |   | Stage 5: Static Deck |
                             |   (Marp CLI Exec)    |   |  (MkDocs Card/Grid)  |
                             +----------+-----------+   +----------------------+
                                        |
                                        +-------------------+
                                        |                   |
                                        v                   v
                             +------------------+   +------------------+
                             |   .pptx Output   |   |   .pdf Output    |
                             +------------------+   +------------------+

```

---

## 2. Technical Stack Specifications

* **Language & Runtime:** Python 3.11+
* **LLM Engine:** Local Ollama instance (defaulting to `qwen2.5:14b` or `qwen2.5-coder:7b`/`14b` via `http://localhost:11434/api/generate`)
* **PDF Parser:** `pymupdf` and `pymupdf4llm`
* **Slide Generator:** `Marp CLI` (`@marp-team/marp-cli` executed via Python `subprocess`)
* **Output Artifacts:**
* `.md` Marp slide source files
* `.pptx` PowerPoint presentation files
* `.pdf` Slide deck files (optimized for tablet/e-reader)
* `.md` MkDocs-compatible Q&A revision pages featuring Material collapsible blocks (`??? tip "Reveal Answer"`)



---

## 3. Detailed Component Requirements

### Stage 1: Document Parsing & TOC Extraction

1. **Primary Navigation (TOC):** Extract Table of Contents metadata using `doc.get_toc()`. If valid entries exist, use starting page numbers and outline titles as standard structural bounds.
2. **Fallback Navigation (Structural Analysis):**
* Inspect page spans for font size variations, weight, and heading line patterns (`Chapter X`, `X.Y Section Title`).
* Group consecutive blocks into a single section hierarchy map containing:
* `chapter_title`
* `section_title`
* `start_page` / `end_page`
* `raw_markdown`





### Stage 2: Context-Aware Chunking

1. Target maximum chunk sizes set to **4,000 tokens** (leaving room within local Ollama context limits).
2. Use section boundaries as primary split boundaries.
3. If a section exceeds the token limit, perform secondary recursive splitting on Markdown subheadings (`###`, `####`), falling back to paragraph breaks (`\n\n`) to avoid breaking sentences.

### Stage 3: Ollama Prompting (Parallel Passes)

#### Pass A: Marp Slide Generation Prompt

* Instruct Ollama to condense the provided Markdown chunk into **Marp-formatted Markdown**.
* Enforce rules:
* Top of file includes slide frontmatter metadata (`marp: true`, `theme: default`).
* Use `---` as explicit slide delimiters.
* Max 1 main topic per slide.
* Max 3–4 bullet points per slide with active bolding for key terms.
* Code blocks must preserve language tags (e.g., `python ... `).



#### Pass B: MkDocs Interactive Q&A Prompt

* Execute in a separate, clean API request using the same input chunk.
* Output structured Markdown compatible with MkDocs Material extension syntax:
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



### Stage 4: Marp Rendering Automation

* Check if `npx` or `marp` is available in system `PATH`.
* Run rendering commands against the generated `.md` slide deck:
* Export to PPTX: `npx @marp-team/marp-cli input_slides.md --pptx -o output_deck.pptx`
* Export to PDF: `npx @marp-team/marp-cli input_slides.md --pdf -o output_deck.pdf`



---

## 4. Coding Agent Instructions (`AGENTS.md` / OpenCode Task)

Copy and paste the specification prompt below directly into your OpenCode setup.

```markdown
# Task Directive: PDF-to-Study-Suite Pipeline Implementation

You are to implement a modular Python command-line utility in a new directory `pdf2study` that ingests PDF textbooks, extracts hierarchical section chunks, and utilizes a local Ollama instance to auto-generate Marp slides, PPTX decks, PDF slides, and MkDocs-compatible Q&A study pages.

## Directory Structure to Create

```

pdf2study/
├── main.py
├── parser.py
├── chunker.py
├── llm_client.py
├── renderer.py
├── prompts.py
├── requirements.txt
└── README.md

```

## Step-by-Step Implementation Instructions

### Step 1: `requirements.txt`
Dependencies to include:
- `pymupdf>=1.23.0`
- `pymupdf4llm>=0.0.5`
- `requests>=2.31.0`
- `click>=8.1.0`
- `tiktoken>=0.5.0`

### Step 2: `parser.py`
Create a `PDFParser` class using PyMuPDF:
1. `extract_toc_or_fallback(pdf_path: str) -> List[Dict]`:
   - Attempt to call `doc.get_toc()`. If entries exist, map out structured sections with `title`, `level`, and `page`.
   - If TOC is empty, scan text spans per page analyzing font sizes (`span["size"]`) and bold styling to locate chapter/section boundaries.
2. `extract_section_content(doc, start_page, end_page) -> str`:
   - Use `pymupdf4llm.to_markdown()` for the specific page range to retain Markdown tables, bold text, and code blocks.

### Step 3: `chunker.py`
Create a `HierarchicalChunker` module:
1. Accept extracted sections from `parser.py`.
2. Estimate token count using `tiktoken` (or word count approximation: 1 token ≈ 0.75 words).
3. If a section chunk exceeds `max_tokens` (default: 4000), split along Markdown headers (`##`, `###`), or double line breaks (`\n\n`).
4. Attach parent metadata to every sub-chunk: `{"chapter": ..., "section": ..., "chunk_id": ...}`.

### Step 4: `prompts.py`
Define system prompts:
1. `MARP_SLIDE_PROMPT`: Directs the LLM to write valid Marp slide Markdown separated by `---`. Max 4 bullets per slide.
2. `MKDOCS_QNA_PROMPT`: Directs the LLM to generate Multiple Choice Questions (MCQs) where answers are formatted strictly with:
   ```markdown
   ??? tip "Reveal Answer & Explanation"
       **Correct Answer:** [Letter]
       
       **Explanation:** [Detailed summary]

```

### Step 5: `llm_client.py`

Create an `OllamaClient` class:

1. Communicate with local Ollama API (`http://localhost:11434/api/generate`).
2. Implement configurable model selection (default: `qwen2.5:14b`).
3. Methods:
* `generate_slides(chunk_text: str, meta: dict) -> str`
* `generate_qna(chunk_text: str, meta: dict) -> str`


4. Run each request as an isolated POST request with distinct prompts to prevent context pollution. Include a retry mechanism with backoff for connection timeouts.

### Step 6: `renderer.py`

Create a `MarpRenderer` module:

1. Execute system commands using Python `subprocess.run`:
* `npx @marp-team/marp-cli <input_md> --pptx -o <output_pptx>`
* `npx @marp-team/marp-cli <input_md> --pdf -o <output_pdf>`


2. Catch errors gracefully if Node/NPX is missing, alerting the user while preserving the generated `.md` files.

### Step 7: `main.py`

Create a CLI interface using `click`:

```bash
python main.py process path/to/book.pdf --model qwen2.5:14b --output-dir ./output

```

CLI Steps:

1. Parse PDF and display detected TOC / section structure in console.
2. Chunk text and process via `OllamaClient`.
3. Save generated Markdown files:
* `./output/slides/chapter_X_slides.md`
* `./output/qna/chapter_X_qna.md`


4. Call `MarpRenderer` to render PPTX and PDF slides into `./output/decks/`.

Ensure clean error handling, logging, and type hints throughout all files.

```

---

## 5. Execution Workflow for You

1. Save the above code block as your prompt/instructions file for OpenCode (e.g., `INSTRUCTIONS.md`).
2. Run OpenCode in your project workspace directory.
3. OpenCode will generate the Python modules, CLI tool, and prompts automatically.
4. Execute the pipeline locally:
   ```bash
   python main.py process my_textbook.pdf --output-dir ./study_output

```
