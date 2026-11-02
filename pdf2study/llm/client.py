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
