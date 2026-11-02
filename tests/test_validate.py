from pdf2study.validate import (
    dedupe_items,
    normalize_slides,
    parse_qna_raw,
    render_qna,
    split_slides,
    strip_wrappers,
    validate_deck,
)


def test_strip_wrappers_removes_think_and_fence():
    raw = "```markdown\n<thinking>hmm</thinking>\n## Title\n- a\n```"
    out = strip_wrappers(raw)
    assert "thinking" not in out
    assert out.startswith("## Title")
    assert "```" not in out


def test_split_and_normalize_deck():
    md = "## A\n- one\n---\n## B\n- two\n"
    assert len(split_slides(md)) == 2
    normalized = normalize_slides("## A\n- one\n\n---\n\n## B\n- two")
    assert normalized.count("---") == 1
    assert validate_deck(normalized) == []


def test_validate_deck_flags_missing_heading():
    assert validate_deck("just text no heading") != []


RAW_QNA = """Q: What is X?
A) one
B) two
C) three
D) four
ANSWER: C
WHY: because.

Q: What is Y?
A) a
B) b
C) c
D) d
ANSWER: A
WHY: reason.
"""


def test_parse_and_render_qna():
    items = parse_qna_raw(RAW_QNA)
    assert len(items) == 2
    assert items[0].answer == "C"
    assert items[0].options == ["one", "two", "three", "four"]

    md = render_qna(items)
    assert "### Question 1:" in md
    assert "### Question 2:" in md
    assert "- [ ] A) one" in md
    assert '??? tip "Reveal Answer & Explanation"' in md
    assert md.count("Correct Answer") == 2  # one per question


def test_dedupe_items_by_question_text():
    items = parse_qna_raw(RAW_QNA + RAW_QNA)
    assert len(dedupe_items(items)) == 2


def test_parse_qna_drops_incomplete_blocks():
    partial = "Q: Only question?\nA) one\nB) two\nANSWER: A\n"
    assert parse_qna_raw(partial) == []
