"""Validation, parsing and repair of model output.

Slides come back as Marp Markdown (normalized here). Q&A is requested in a
simple delimited form (`Q:` / `A)`..`D)` / `ANSWER:` / `WHY:`) and *we* render
the MkDocs callouts, so small models cannot corrupt the final format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_THINK_RE = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*\n(.*?)\n```\s*$", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")


def strip_wrappers(text: str) -> str:
    """Remove reasoning blocks and a single surrounding code fence."""
    text = _THINK_RE.sub("", text)
    m = _FENCE_RE.match(text.strip())
    if m:
        text = m.group(1)
    return text.strip()


# --------------------------------------------------------------------- slides

def split_slides(markdown: str) -> list[str]:
    blocks: list[str] = []
    buf: list[str] = []
    for line in markdown.splitlines():
        if line.strip() == "---":
            block = "\n".join(buf).strip()
            if block:
                blocks.append(block)
            buf = []
        else:
            buf.append(line)
    tail = "\n".join(buf).strip()
    if tail:
        blocks.append(tail)
    return blocks


@dataclass
class Slide:
    title: str = ""
    bullets: list[str] = field(default_factory=list)
    images: list[tuple[str, str]] = field(default_factory=list)
    body: list[str] = field(default_factory=list)


def parse_slide(block: str) -> Slide:
    slide = Slide()
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = _HEADING_RE.match(line)
        if heading and not slide.title:
            slide.title = heading.group(1).strip()
            continue
        img = _IMAGE_RE.search(line)
        if img:
            slide.images.append((img.group(1), img.group(2)))
            continue
        if re.match(r"^[-*+]\s+", line):
            slide.bullets.append(re.sub(r"^[-*+]\s+", "", line).strip())
            continue
        slide.body.append(line)
    if not slide.title and slide.bullets:
        slide.title = slide.bullets.pop(0)
    return slide


def normalize_slides(markdown: str) -> str:
    text = strip_wrappers(markdown)
    blocks = [b for b in split_slides(text) if b]
    return "\n\n---\n\n".join(blocks) + ("\n" if blocks else "")


def validate_deck(markdown: str) -> list[str]:
    issues: list[str] = []
    blocks = split_slides(markdown)
    if not blocks:
        return ["deck is empty"]
    for i, block in enumerate(blocks, 1):
        slide = parse_slide(block)
        if not slide.title:
            issues.append(f"slide {i}: missing heading")
        if len(slide.bullets) > 6:
            issues.append(f"slide {i}: too many bullets ({len(slide.bullets)})")
    return issues


# ----------------------------------------------------------------------- Q&A

@dataclass
class QnAItem:
    question: str
    options: list[str]  # exactly four, in A..D order
    answer: str  # one of A/B/C/D
    why: str = ""

    def key(self) -> str:
        text = re.sub(r"\s+", " ", self.question).strip().lower()
        return text[:160]


_Q_START = re.compile(r"(?im)^\s*Q\s*[:\)]\s*")
_OPTION = re.compile(r"^([A-D])[\).:]\s*(.+)$", re.IGNORECASE)
_ANSWER = re.compile(r"(?i)^ANSWER\s*[:\-]\s*([A-D])")
_WHY = re.compile(r"(?i)^WHY\s*[:\-]\s*(.*)$")


def _parse_block(block: str) -> QnAItem | None:
    lines = block.splitlines()
    question = re.sub(r"(?i)^\s*Q\s*[:\)]\s*", "", lines[0]).strip()
    options: dict[str, str] = {}
    answer: str | None = None
    why: list[str] = []
    mode = "q"
    for line in lines[1:]:
        s = line.strip()
        if not s:
            continue
        m_opt = _OPTION.match(s)
        if m_opt and mode in ("q", "opt"):
            options[m_opt.group(1).upper()] = m_opt.group(2).strip()
            mode = "opt"
            continue
        m_ans = _ANSWER.match(s)
        if m_ans:
            answer = m_ans.group(1).upper()
            mode = "answer"
            continue
        m_why = _WHY.match(s)
        if m_why:
            why = [m_why.group(1).strip()]
            mode = "why"
            continue
        if mode == "q":
            question += " " + s
        elif mode == "why":
            why.append(s)
    if len(options) < 4 or not answer:
        return None
    return QnAItem(
        question=question.strip(),
        options=[options.get(k, "") for k in "ABCD"],
        answer=answer,
        why=" ".join(w for w in why if w).strip(),
    )


def parse_qna_raw(text: str) -> list[QnAItem]:
    text = strip_wrappers(text)
    starts = [m.start() for m in _Q_START.finditer(text)]
    if not starts:
        return []
    starts.append(len(text))
    items: list[QnAItem] = []
    for i in range(len(starts) - 1):
        item = _parse_block(text[starts[i] : starts[i + 1]])
        if item:
            items.append(item)
    return items


def dedupe_items(items: list[QnAItem]) -> list[QnAItem]:
    seen: set[str] = set()
    kept: list[QnAItem] = []
    for item in items:
        key = item.key()
        if key and key not in seen:
            seen.add(key)
            kept.append(item)
    return kept


def render_qna(items: list[QnAItem], start: int = 1) -> str:
    out: list[str] = []
    for i, item in enumerate(items, start=start):
        topic = item.question if len(item.question) <= 70 else item.question[:67].rstrip() + "..."
        lines = [f"### Question {i}: {topic}", "", item.question, ""]
        for letter, opt in zip("ABCD", item.options):
            lines.append(f"- [ ] {letter}) {opt}")
        lines += ["", '??? tip "Reveal Answer & Explanation"', f"    **Correct Answer:** {item.answer}"]
        if item.why:
            lines += ["", f"    **Explanation:** {item.why}"]
        out.append("\n".join(lines))
    return "\n\n".join(out) + ("\n" if out else "")
