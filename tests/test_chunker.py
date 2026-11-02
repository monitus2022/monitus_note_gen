from pdf2study.chunker import HierarchicalChunker, count_tokens
from pdf2study.models import Section


def test_small_section_is_single_chunk():
    sections = [Section(title="Ch1", level=1, page=1, markdown="short text")]
    chunks = HierarchicalChunker("book", max_tokens=3500).chunk(sections)
    assert len(chunks) == 1
    assert chunks[0].chapter == "Ch1"
    assert chunks[0].chunk_id == "chunk_0001"


def test_oversized_section_splits_on_headers():
    body = "\n\n".join(f"## Sub{i}\n\n" + ("word " * 200) for i in range(10))
    sections = [Section(title="Big", level=1, page=1, markdown=body)]
    chunks = HierarchicalChunker("book", max_tokens=300).chunk(sections)
    assert len(chunks) > 1
    assert all(c.tokens <= 600 for c in chunks)  # pieces roughly bounded


def test_parent_metadata_carries_chapter():
    sections = [
        Section(title="Chapter A", level=1, page=1, markdown="a"),
        Section(title="Sub", level=2, page=1, markdown="b"),
        Section(title="Chapter B", level=1, page=2, markdown="c"),
    ]
    chunks = HierarchicalChunker("book").chunk(sections)
    assert [c.chapter for c in chunks] == ["Chapter A", "Chapter A", "Chapter B"]
    assert count_tokens("hello world") > 0
