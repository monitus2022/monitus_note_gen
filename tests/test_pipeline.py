from pdf2study.config import Config
from pdf2study.pipeline import run


def _cfg(tmp_path, **kw):
    return Config(
        tmp_dir=tmp_path / "tmp",
        cache_dir=tmp_path / ".cache",
        local_sink_dir=tmp_path / "sink",
        **kw,
    )


def test_dry_run_writes_artifacts(sample_pdf, tmp_path):
    summary = run(_cfg(tmp_path, dry_run=True), sample_pdf, "testbook")
    book = tmp_path / "tmp" / "testbook"
    assert summary["dry_run"] is True
    assert summary["chunks"] >= 1
    assert summary["chapters"] >= 1
    assert summary["figures"] >= 1
    assert (book / "manifest.json").exists()
    assert list((book / "chunks").glob("chunk_*.json"))
    assert list((book / "images").glob("*.png"))


def test_local_upload_uses_key_layout(sample_pdf, tmp_path):
    summary = run(_cfg(tmp_path, dry_run=False, keep_temp=True), sample_pdf, "testbook")
    assert summary["uploaded_to"] == "local:books/testbook"
    base = tmp_path / "sink" / "books" / "testbook"
    assert (base / "manifest.json").exists()
    assert (base / "chunks").is_dir()
    assert any((base / "images").glob("*.png"))


def test_parse_cache_avoids_reparse(sample_pdf, tmp_path):
    cfg = _cfg(tmp_path, dry_run=True)
    run(cfg, sample_pdf, "testbook")
    assert list((tmp_path / ".cache" / "testbook" / "parse").glob("*"))
