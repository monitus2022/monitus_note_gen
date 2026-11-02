"""Local filesystem sink - mirrors the R2 key layout on disk for testing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger
from ..storage import content_type_for

log = get_logger("storage.local")


class LocalSink:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dest(self, key: str) -> Path:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    def put_file(self, local_path: str | Path, key: str) -> None:
        data = Path(local_path).read_bytes()
        self._dest(key).write_bytes(data)
        log.debug("local put %s (%s)", key, content_type_for(local_path))

    def put_bytes(self, data: bytes, key: str, content_type: str | None = None) -> None:
        self._dest(key).write_bytes(data)
        log.debug("local put %s (%s)", key, content_type or "?")

    def put_json(self, data: Any, key: str) -> None:
        self.put_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), key, "application/json")
