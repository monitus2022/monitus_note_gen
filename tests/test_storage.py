from pdf2study.storage import LocalSink, content_type_for, sync_directory


def test_content_type_overrides():
    assert content_type_for("a.md").startswith("text/markdown")
    assert content_type_for("a.png") == "image/png"
    assert content_type_for("a.pptx").endswith("presentationml.presentation")


def test_sync_directory_preserves_layout(tmp_path):
    src = tmp_path / "src"
    (src / "chunks").mkdir(parents=True)
    (src / "chunks" / "c1.json").write_text("{}")
    (src / "manifest.json").write_text("{}")
    sink = LocalSink(tmp_path / "out")
    keys = sync_directory(sink, src, "books/x")
    assert "books/x/chunks/c1.json" in keys
    assert "books/x/manifest.json" in keys
    assert (tmp_path / "out" / "books" / "x" / "manifest.json").exists()


def test_r2_manager_allows_bucket_override():
    from pdf2study.config import R2Config
    from pdf2study.storage.r2 import R2StorageManager

    cfg = R2Config(access_key_id="a", secret_access_key="b", account_id="acct", bucket="main")
    assert R2StorageManager(cfg, bucket="public-figures").bucket == "public-figures"
    assert R2StorageManager(cfg).bucket == "main"
