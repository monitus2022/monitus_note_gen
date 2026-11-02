"""Storage backends: a common protocol plus a local filesystem sink and R2."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Protocol

from ..logging_setup import get_logger

log = get_logger("storage")

# Explicit overrides where mimetypes is unreliable across platforms.
_CONTENT_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def content_type_for(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    if ext in _CONTENT_TYPES:
        return _CONTENT_TYPES[ext]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


class StorageBackend(Protocol):
    def put_file(self, local_path: str | Path, key: str) -> None: ...
    def put_bytes(self, data: bytes, key: str, content_type: str | None = None) -> None: ...
    def put_json(self, data: Any, key: str) -> None: ...


def sync_directory(backend: StorageBackend, local_dir: str | Path, prefix: str) -> list[str]:
    """Walk `local_dir` and upload every file under `prefix`, preserving layout."""
    local_dir = Path(local_dir)
    if not local_dir.exists():
        return []
    uploaded: list[str] = []
    for path in sorted(local_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(local_dir).as_posix()
            key = f"{prefix.rstrip('/')}/{rel}"
            backend.put_file(path, key)
            uploaded.append(key)
    log.info("synced %d file(s) under %s", len(uploaded), prefix)
    return uploaded


from .local import LocalSink  # noqa: E402
from .r2 import R2StorageManager  # noqa: E402

__all__ = ["StorageBackend", "LocalSink", "R2StorageManager", "sync_directory", "content_type_for"]
