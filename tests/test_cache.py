from pdf2study.cache import ContentCache, hash_key


def test_hash_key_is_stable_and_order_sensitive():
    assert hash_key("a", "b") == hash_key("a", "b")
    assert hash_key("a", "b") != hash_key("b", "a")
    assert hash_key({"x": 1, "y": 2}) == hash_key({"y": 2, "x": 1})


def test_cached_text_roundtrip(tmp_path):
    cache = ContentCache(tmp_path, enabled=True)
    calls = {"n": 0}

    def produce():
        calls["n"] += 1
        return "hello"

    assert cache.cached_text("ns", "k", produce) == "hello"
    assert cache.cached_text("ns", "k", produce) == "hello"
    assert calls["n"] == 1  # second call served from cache


def test_disabled_cache_never_stores(tmp_path):
    cache = ContentCache(tmp_path, enabled=False)
    cache.put_text("ns", "k", "v")
    assert cache.get_text("ns", "k") is None
