"""Content-hash cache for resumable, incremental runs.

A cache key is derived from the inputs that affect an artifact's content
(chunk text, model, prompt version, task). Switching models or bumping a
prompt version invalidates only the affected LLM artifacts; parsing, OCR and
figure caches survive.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Callable, TypeVar

from .logging_setup import get_logger

log = get_logger("cache")

T = TypeVar("T")


def hash_key(*parts: Any) -> str:
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, (dict, list)):
            part = json.dumps(part, sort_keys=True, ensure_ascii=False)
        h.update(str(part).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class ContentCache:
    """Simple filesystem-backed cache: key -> bytes, with JSON and text helpers."""

    def __init__(self, root: Path, enabled: bool = True):
        self.root = Path(root)
        self.enabled = enabled
        if enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path:
        return self.root / namespace / key

    def get_bytes(self, namespace: str, key: str) -> bytes | None:
        if not self.enabled:
            return None
        p = self._path(namespace, key)
        if p.exists():
            return p.read_bytes()
        return None

    def put_bytes(self, namespace: str, key: str, data: bytes) -> None:
        if not self.enabled:
            return
        p = self._path(namespace, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_json(self, namespace: str, key: str) -> Any | None:
        raw = self.get_bytes(namespace, key)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    def put_json(self, namespace: str, key: str, data: Any) -> None:
        self.put_bytes(
            namespace, key, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        )

    def get_text(self, namespace: str, key: str) -> str | None:
        raw = self.get_bytes(namespace, key)
        return raw.decode("utf-8") if raw is not None else None

    def put_text(self, namespace: str, key: str, text: str) -> None:
        self.put_bytes(namespace, key, text.encode("utf-8"))

    def cached_text(self, namespace: str, key: str, produce: Callable[[], str]) -> str:
        """Return cached text or compute+store it."""
        hit = self.get_text(namespace, key)
        if hit is not None:
            log.debug("cache hit %s/%s", namespace, key[:12])
            return hit
        value = produce()
        self.put_text(namespace, key, value)
        return value

    def has(self, namespace: str, key: str) -> bool:
        return self.enabled and self._path(namespace, key).exists()

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
