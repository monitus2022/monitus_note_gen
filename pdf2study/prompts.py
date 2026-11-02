"""Prompt templates and builders.

`PROMPT_VERSION` participates in the LLM cache key: bump it whenever a prompt
changes so stale artifacts are invalidated without discarding parse/figure caches.
"""

from __future__ import annotations

from .chunker import Chunk
from .models import Figure

PROMPT_VERSION = "v2"

SLIDE_SYSTEM = """You write concise, accurate study slides in Marp Markdown.
Rules:
- Output ONLY Marp slide Markdown. No preamble, no commentary, no code fences.
- Separate slides with a line containing exactly three dashes: ---
- Every slide begins with a level-2 heading: ## <short title>
- At most 4 bullet points per slide; each bullet <= 20 words.
- Use only facts present in the source text. Never invent numbers or citations.
- When a figure is provided and relevant, place it on its own line as:
  ![<caption>](../images/<id>.png)"""

QNA_SYSTEM = """You write exam-style multiple-choice questions for self-study.
Rules:
- Output ONLY the questions in the exact plain-text format below. No preamble,
  no headings, no code fences.
- Produce every question as a separate block, each block containing exactly one
  ANSWER line. Never combine answers.

Q: <question text>
A) <option>
B) <option>
C) <option>
D) <option>
ANSWER: <A/B/C/D>
WHY: <one or two sentences>

Base answers strictly on the source text. Do not invent facts."""

CAPTION_SYSTEM = """You describe figures from a textbook for accessibility and search.
Reply with ONE plain sentence capturing what the figure shows. No preamble."""


def _figure_block(figures: list[Figure]) -> str:
    if not figures:
        return ""
    lines = ["Available figures (use only if relevant):"]
    for f in figures:
        path = f"../images/{f.id}.png"
        cap = (f.caption or "figure").strip()
        lines.append(f'- {f.id}: caption="{cap}" -> ![{cap}]({path})')
    return "\n".join(lines) + "\n\n"


def slide_fragment_prompt(chunk: Chunk) -> tuple[str, str]:
    user = (
        f"Book: {chunk.book}\nChapter: {chunk.chapter}\nSection: {chunk.section}\n\n"
        "Create 1-3 revision slides summarising the source text below.\n\n"
        f"{_figure_block(chunk.figures)}"
        f"SOURCE:\n{chunk.text}"
    )
    return SLIDE_SYSTEM, user


def qna_fragment_prompt(chunk: Chunk) -> tuple[str, str]:
    user = (
        f"Book: {chunk.book}\nChapter: {chunk.chapter}\nSection: {chunk.section}\n\n"
        "Write 2-4 multiple-choice questions covering the source text below, using "
        "the exact Q/A/B/C/D/ANSWER/WHY format.\n\n"
        f"SOURCE:\n{chunk.text}"
    )
    return QNA_SYSTEM, user


def caption_user_prompt(caption_hint: str | None) -> str:
    hint = f'The PDF caption reads: "{caption_hint}".\n' if caption_hint else ""
    return f"{hint}Describe this figure in one sentence."
