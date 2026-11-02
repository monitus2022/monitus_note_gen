"""Publish generated artifacts as MkDocs pages into a separate site repo.

Markdown only: chapter pages reuse the slide bullets as a summary, append the
Q&A, and either drop figure images or rewrite them to an absolute base URL.
Publishing always happens on a `publish/<slug>` branch based on `dev`, so
Cloudflare Pages builds a preview deploy; nothing is written to `main`.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import requests

from .config import Config
from .logging_setup import get_logger

log = get_logger("publish")

_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].rstrip("-")) or "chapter"


def transform_images(markdown: str, image_base_url: str | None, book_slug: str) -> str:
    """Keep markdown self-contained.

    - With `image_base_url`: rewrite figure refs to an absolute URL (images stay off-repo).
    - Without: remove image-only lines entirely.
    """
    if image_base_url:
        base = image_base_url.rstrip("/")
        return _IMG.sub(
            lambda m: f"![{m.group(1)}]({base}/books/{book_slug}/images/{Path(m.group(2)).name})",
            markdown,
        )
    out: list[str] = []
    for line in markdown.splitlines():
        if _IMG.search(line) and line.strip().startswith("!["):
            continue
        out.append(_IMG.sub("", line))
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text)


def build_pages(
    manifest: dict,
    slides: dict[int, str],
    qna: dict[int, str],
    book_slug: str,
    *,
    image_base_url: str | None = None,
) -> dict[str, str]:
    """Return {relative_path: markdown} for the MkDocs docs folder."""
    pages: dict[str, str] = {}
    rows: list[tuple[int, str, str, int]] = []
    total_questions = 0

    for ch in manifest.get("chapters", []):
        idx = ch["index"]
        title = ch.get("title", f"Chapter {idx}")
        sl = transform_images(slides.get(idx, ""), image_base_url, book_slug).strip()
        qn_md = (qna.get(idx) or "").strip()
        n_q = len(re.findall(r"^### Question \d+", qn_md, re.M))
        total_questions += n_q

        body = sl or f"# {title}"
        body += "\n\n## Practice Questions\n\n"
        body += qn_md if qn_md else "_No questions generated for this chapter._"
        body += "\n"

        fname = f"{idx:02d}_{slugify(title)}.md"
        pages[fname] = body
        rows.append((idx, title, fname, n_q))

    lines = [
        f"# {manifest.get('title') or book_slug}",
        "",
        f"_Generated from `{manifest.get('model', 'unknown')}` on "
        f"{(manifest.get('generated_at') or '')[:10]}. "
        f"{total_questions} practice questions across {len(rows)} chapters._",
        "",
        "## Chapters",
        "",
        "| # | Chapter | Questions |",
        "| --- | --- | --- |",
    ]
    for idx, title, fname, n_q in rows:
        lines.append(f"| {idx} | [{title}]({fname}) | {n_q} |")
    pages["index.md"] = "\n".join(lines) + "\n"
    return pages


# ------------------------------------------------------------------ sources

def _load_local(cfg: Config, slug: str) -> tuple[dict, dict[int, str], dict[int, str]]:
    book = Path(cfg.tmp_dir) / slug
    manifest = json.loads((book / "manifest.json").read_text(encoding="utf-8"))
    slides, qna = {}, {}
    for ch in manifest["chapters"]:
        slides[ch["index"]] = (book / ch["slides"]).read_text(encoding="utf-8")
        qna[ch["index"]] = (book / ch["qna"]).read_text(encoding="utf-8")
    return manifest, slides, qna


def _load_r2(cfg: Config, slug: str) -> tuple[dict, dict[int, str], dict[int, str]]:
    import boto3

    r2 = cfg.r2
    if not r2.is_complete():
        raise ValueError("R2 is not configured; use --source local or set R2_* in .env")
    cl = boto3.client(
        "s3",
        endpoint_url=r2.endpoint_url,
        aws_access_key_id=r2.access_key_id,
        aws_secret_access_key=r2.secret_access_key,
        region_name="auto",
    )
    prefix = f"books/{slug}/"

    def get_text(key: str) -> str:
        return cl.get_object(Bucket=r2.bucket, Key=prefix + key)["Body"].read().decode("utf-8")

    manifest = json.loads(get_text("manifest.json"))
    slides = {ch["index"]: get_text(ch["slides"]) for ch in manifest["chapters"]}
    qna = {ch["index"]: get_text(ch["qna"]) for ch in manifest["chapters"]}
    return manifest, slides, qna


def load_source(cfg: Config, slug: str, source: str = "auto") -> tuple[dict, dict[int, str], dict[int, str]]:
    if source == "local" or (source == "auto" and (Path(cfg.tmp_dir) / slug / "manifest.json").exists()):
        return _load_local(cfg, slug)
    return _load_r2(cfg, slug)


# --------------------------------------------------------------------- git

def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), check=check, capture_output=True, text=True
    )


def _remote_slug(repo: Path) -> str | None:
    try:
        url = _git(repo, "remote", "get-url", "origin").stdout.strip()
    except subprocess.CalledProcessError:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _open_pr(token: str, repo_slug: str, base: str, head: str, title: str, body: str) -> str | None:
    api = f"https://api.github.com/repos/{repo_slug}/pulls"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = requests.post(api, headers=headers, json={"title": title, "head": head, "base": base, "body": body}, timeout=60)
    if r.status_code in (200, 201):
        return r.json().get("html_url")
    if r.status_code == 422:  # already open
        owner = repo_slug.split("/")[0]
        q = requests.get(api, headers=headers, params={"head": f"{owner}:{head}", "state": "open"}, timeout=60)
        if q.ok and q.json():
            return q.json()[0].get("html_url")
    log.warning("could not create PR (%s): %s", r.status_code, r.text[:200])
    return None


def publish(
    cfg: Config,
    slug: str,
    site_repo: str | Path,
    dest: str,
    *,
    base_branch: str = "dev",
    source: str = "auto",
    image_base_url: str | None = None,
    push: bool = True,
    github_token: str | None = None,
    commit_message: str | None = None,
) -> dict:
    repo = Path(site_repo).expanduser().resolve()
    if not (repo / ".git").exists():
        raise FileNotFoundError(f"not a git repo: {repo}")

    dirty = _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        raise RuntimeError("site repo has uncommitted changes; commit or stash them first")

    manifest, slides, qna = load_source(cfg, slug, source)
    pages = build_pages(manifest, slides, qna, slug, image_base_url=image_base_url)

    _git(repo, "fetch", "origin", "--prune")
    branch = f"publish/{slug}"
    original = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _git(repo, "checkout", "-B", branch, f"origin/{base_branch}")

    dest_dir = repo / "docs" / dest
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("*.md"):
        old.unlink()
    for name, content in pages.items():
        (dest_dir / name).write_text(content, encoding="utf-8")

    rel = f"docs/{dest}"
    _git(repo, "add", "--", rel)
    try:
        if not _git(repo, "status", "--porcelain", "--", rel).stdout.strip():
            log.info("no changes to publish")
            return {"branch": branch, "changed": False, "pages": len(pages)}

        _git(repo, "commit", "-m", commit_message or f"docs({slug}): publish generated study notes")
        result = {"branch": branch, "changed": True, "pages": len(pages)}

        repo_slug = _remote_slug(repo)
        if repo_slug:
            result["compare_url"] = f"https://github.com/{repo_slug}/compare/{base_branch}...{branch}?expand=1"

        if push:
            _git(repo, "push", "--force-with-lease", "-u", "origin", branch)
            result["pushed"] = True
            if repo_slug and github_token:
                pr = _open_pr(
                    github_token,
                    repo_slug,
                    base_branch,
                    branch,
                    f"docs({slug}): generated study notes",
                    f"Automated publish of `{slug}` ({len(pages)} pages).\n\nPreview deploy will be created by Cloudflare Pages.",
                )
                if pr:
                    result["pr_url"] = pr
        return result
    finally:
        # Leave the user's clone on the branch they were on before publishing.
        if original and original != branch:
            _git(repo, "checkout", original, check=False)
