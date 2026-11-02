from pdf2study.cache import ContentCache
from pdf2study.chunker import Chunk
from pdf2study.generate import generate_chapters, map_chunk

SLIDES = "## Overview\n- point one\n- point two\n"
QNA = """Q: What is X?
A) one
B) two
C) three
D) four
ANSWER: B
WHY: because.
"""


class FakeClient:
    model = "fake:1"

    def __init__(self):
        self.calls = 0

    def chat(self, system, user, **kw):
        self.calls += 1
        return SLIDES if "Marp" in system else QNA


def _chunks():
    return [
        Chunk("chunk_0001", 1, "book", "Chapter 1", "Sec", 1, 1, "text a", 3),
        Chunk("chunk_0002", 2, "book", "Chapter 1", "Sec", 1, 2, "text b", 3),
        Chunk("chunk_0003", 3, "book", "Chapter 2", "Sec", 1, 3, "text c", 3),
    ]


def test_map_chunk_caches(tmp_path):
    cache = ContentCache(tmp_path)
    client = FakeClient()
    chunk = _chunks()[0]
    map_chunk(client, cache, chunk)
    first = client.calls
    map_chunk(client, cache, chunk)  # served from cache
    assert client.calls == first


def test_generate_chapters_groups_renders_and_dedupes(tmp_path):
    cache = ContentCache(tmp_path / "cache")
    chapters = generate_chapters(FakeClient(), cache, _chunks())
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].slides_md.startswith("# Chapter 1")
    assert "## Overview" in chapters[0].slides_md
    # Q&A rendered to MkDocs callouts, deduped across the chapter's two chunks
    assert "### Question 1:" in chapters[0].qna_md
    assert '??? tip "Reveal Answer & Explanation"' in chapters[0].qna_md
    assert chapters[0].qna_md.count("Correct Answer") == 1
