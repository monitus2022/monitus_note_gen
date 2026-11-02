import base64
import json

import pytest

from pdf2study.config import Config
from pdf2study.llm import build_client
from pdf2study.llm.client import OpenRouterClient


def test_missing_key_raises():
    with pytest.raises(ValueError):
        OpenRouterClient(api_key=None)


def test_chat_builds_openai_payload(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "hello"}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, payload=json, headers=headers)
        return FakeResp()

    monkeypatch.setattr("pdf2study.llm.client.requests.post", fake_post)

    client = OpenRouterClient(api_key="k", model="deepseek/deepseek-v4.1-flash-1017")
    out = client.chat("sys", "usr", num_predict=64)
    assert out == "hello"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert captured["payload"]["model"] == "deepseek/deepseek-v4.1-flash-1017"
    assert captured["payload"]["max_tokens"] == 64
    assert captured["payload"]["messages"][0]["role"] == "system"


def test_chat_encodes_images(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(
        "pdf2study.llm.client.requests.post",
        lambda url, json=None, headers=None, timeout=None: (captured.update(payload=json) or FakeResp()),
    )
    OpenRouterClient(api_key="k").chat("s", "u", images=[b"\x89PNG"])
    content = captured["payload"]["messages"][1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_build_client_selects_provider():
    orc = build_client(Config(provider="openrouter", openrouter_api_key="k", model="m"))
    assert isinstance(orc, OpenRouterClient)
    oll = build_client(Config(provider="ollama", ollama_host="http://x", model="qwen3.5:4b"))
    assert type(oll).__name__ == "OllamaClient"
