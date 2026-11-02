# monitus_note_gen

Generate study material (slide decks + Q&A) from PDF textbooks, stored in a
private Cloudflare R2 bucket.

- Architecture & plan: [`PLAN.MD`](./PLAN.MD)
- Implementation: [`pdf2study/`](./pdf2study) — see [`pdf2study/README.md`](./pdf2study/README.md)

## Quick start

```bash
uv sync --extra dev --python /opt/homebrew/bin/python3.12
uv run pdf2study process books/your-book.pdf --book-slug your-book --dry-run
```
