import json
import subprocess
from pathlib import Path

from pdf2study.config import Config
from pdf2study.publish import build_pages, publish, slugify, transform_images


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def test_slugify():
    assert slugify("1. Introduction to Building AI Applications!") == "1-introduction-to-building-ai-applications"
    assert slugify("!!!") == "chapter"


def test_transform_images_drops_and_rewrites():
    md = "# T\n\n![fig](../images/fig_001.png)\n\n- bullet\n"
    dropped = transform_images(md, None, "book")
    assert "fig_001.png" not in dropped
    assert "- bullet" in dropped

    rewritten = transform_images(md, "https://cdn.example.com", "book")
    assert "https://cdn.example.com/books/book/images/fig_001.png" in rewritten


def _manifest():
    return {
        "title": "My Book",
        "model": "m",
        "generated_at": "2026-01-01T00:00:00Z",
        "chapters": [
            {"index": 1, "title": "Intro", "slides": "slides/chapter_01_slides.md", "qna": "qna/chapter_01_qna.md"},
            {"index": 2, "title": "Deep Dive", "slides": "slides/chapter_02_slides.md", "qna": "qna/chapter_02_qna.md"},
        ],
    }


def test_build_pages_structure():
    slides = {1: "# Intro\n\n---\n\n## A\n- one\n\n![f](../images/f.png)\n", 2: "# Deep Dive\n\n---\n\n## B\n- two\n"}
    qna = {1: "### Question 1: X\n\nbody\n", 2: ""}
    pages = build_pages(_manifest(), slides, qna, "book")
    assert set(pages) == {"index.md", "01_intro.md", "02_deep-dive.md"}
    assert "[Intro](01_intro.md)" in pages["index.md"]
    assert "## Practice Questions" in pages["01_intro.md"]
    assert "f.png" not in pages["01_intro.md"]  # image dropped by default
    assert "No questions generated" in pages["02_deep-dive.md"]
    assert "1 practice questions" in pages["index.md"]


def _setup_site(tmp: Path) -> Path:
    remote = tmp / "remote.git"
    _git(tmp, "init", "--bare", "remote.git")
    work = tmp / "site"
    _git(tmp, "init", "site")
    _git(work, "config", "user.email", "t@t.t")
    _git(work, "config", "user.name", "test")
    (work / "docs").mkdir()
    (work / "docs" / "index.md").write_text("# site\n")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "init")
    _git(work, "branch", "-M", "main")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-u", "origin", "main")
    _git(work, "checkout", "-b", "dev")
    _git(work, "push", "-u", "origin", "dev")
    return work


def _setup_book(tmp: Path) -> Config:
    book = tmp / "tmp_build" / "book"
    (book / "slides").mkdir(parents=True)
    (book / "qna").mkdir(parents=True)
    (book / "manifest.json").write_text(json.dumps(_manifest()))
    (book / "slides" / "chapter_01_slides.md").write_text("# Intro\n\n---\n\n## A\n- one\n")
    (book / "slides" / "chapter_02_slides.md").write_text("# Deep Dive\n\n---\n\n## B\n- two\n")
    (book / "qna" / "chapter_01_qna.md").write_text("### Question 1: X\n\nbody\n")
    (book / "qna" / "chapter_02_qna.md").write_text("")
    return Config(tmp_dir=tmp / "tmp_build")


def test_publish_commits_pushes_and_restores_branch(tmp_path):
    site = _setup_site(tmp_path)
    cfg = _setup_book(tmp_path)

    result = publish(cfg, "book", site, "books/book", base_branch="dev", source="local", push=True)
    assert result["changed"] is True
    assert result["pushed"] is True
    assert result["pages"] == 3

    # push landed on the remote under the publish branch
    remote = tmp_path / "remote.git"
    listing = _git(remote, "ls-tree", "-r", "--name-only", "publish/book").stdout
    assert "docs/books/book/index.md" in listing
    published = [p for p in listing.splitlines() if p.startswith("docs/books/book/")]
    assert len(published) == 3 and all(p.endswith(".md") for p in published)  # markdown only
    assert ".png" not in listing
    assert "docs/index.md" in listing  # pre-existing site content preserved

    # user's clone restored to the branch they were on
    assert _git(site, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "dev"
