"""Ollama HTTP client.

Thinking is disabled by default (`think: false`) because reasoning traces break
strict Marp/MkDocs formatting. `strip_wrappers` is a second line of defence.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from ..logging_setup import get_logger

log = get_logger("llm")


class OllamaClient:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen3.5:4b",
        *,
        think: bool = False,
        timeout: int = 300,
        retries: int = 2,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.think = think
        self.timeout = timeout
        self.retries = retries

    def chat(
        self,
        system: str,
        user: str,
        *,
        images: list[bytes] | None = None,
        temperature: float = 0.3,
        num_predict: int = 2048,
    ) -> str:
        message: dict = {"role": "user", "content": user}
        if images:
            message["images"] = [base64.b64encode(i).decode("ascii") for i in images]
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, message],
            "stream": False,
            "think": self.think,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
            except Exception as exc:  # noqa: BLE001 - retry any transport/JSON error
                last = exc
                log.warning("ollama request failed (attempt %d/%d): %s", attempt + 1, self.retries + 1, exc)
                if attempt < self.retries:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Ollama request failed after {self.retries + 1} attempts: {last}")

    def caption_image(self, image_path: str | Path, caption_hint: str | None = None) -> str:
        from ..prompts import CAPTION_SYSTEM, caption_user_prompt

        data = Path(image_path).read_bytes()
        return self.chat(CAPTION_SYSTEM, caption_user_prompt(caption_hint), images=[data], num_predict=128)


class OpenRouterClient:
    """OpenAI-compatible client for OpenRouter (default: DeepSeek V4.1 Flash).

    Same interface as `OllamaClient`, so the rest of the pipeline is unchanged.
    """

    def __init__(
        self,
        api_key: str | None,
        model: str = "deepseek/deepseek-v4.1-flash-1017",
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 300,
        retries: int = 3,
        app_title: str = "pdf2study",
    ):
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. Add it to .env (see .env.example) "
                "or run with --provider ollama."
            )
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.app_title = app_title

    def _user_content(self, user: str, images: list[bytes] | None):
        if not images:
            return user
        content: list[dict] = [{"type": "text", "text": user}]
        for img in images:
            b64 = base64.b64encode(img).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        return content

    def chat(
        self,
        system: str,
        user: str,
        *,
        images: list[bytes] | None = None,
        temperature: float = 0.3,
        num_predict: int = 2048,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": self._user_content(user, images)},
            ],
            "temperature": temperature,
            "max_tokens": num_predict,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_title:
            headers["X-Title"] = self.app_title

        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0]["message"]
                return message.get("content") or ""
            except Exception as exc:  # noqa: BLE001 - retry transport/HTTP errors
                last = exc
                log.warning("openrouter request failed (attempt %d/%d): %s", attempt + 1, self.retries + 1, exc)
                if attempt < self.retries:
                    time.sleep(2**attempt)
        raise RuntimeError(f"OpenRouter request failed after {self.retries + 1} attempts: {last}")

    def caption_image(self, image_path: str | Path, caption_hint: str | None = None) -> str:
        from ..prompts import CAPTION_SYSTEM, caption_user_prompt

        data = Path(image_path).read_bytes()
        return self.chat(CAPTION_SYSTEM, caption_user_prompt(caption_hint), images=[data], num_predict=128)
