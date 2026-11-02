"""Runtime configuration, loaded from environment (.env) and CLI overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class R2Config:
    access_key_id: str | None = None
    secret_access_key: str | None = None
    account_id: str | None = None
    bucket: str = "pdf-study-storage"

    @property
    def endpoint_url(self) -> str | None:
        if not self.account_id:
            return None
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def is_complete(self) -> bool:
        return bool(self.access_key_id and self.secret_access_key and self.account_id)


@dataclass
class Config:
    # paths
    project_root: Path = field(default_factory=lambda: Path.cwd())
    tmp_dir: Path = field(default_factory=lambda: Path("tmp_build"))
    cache_dir: Path = field(default_factory=lambda: Path(".cache"))

    # ollama
    ollama_host: str = "http://localhost:11434"
    model: str = "qwen3.5:4b"

    # pipeline
    parser: str = "pymupdf"  # pymupdf | docling | mineru
    max_tokens: int = 3500
    concurrency: int = 1
    dpi: int = 200
    caption_vlm: bool = False
    ocr: str = "auto"  # auto | always | never
    keep_temp: bool = False
    dry_run: bool = False
    limit: int | None = None
    no_cache: bool = False
    generate: bool = True
    render: bool = True

    # destination
    sink: str = "local"  # local | r2
    local_sink_dir: Path = field(default_factory=lambda: Path("tmp_local_sink"))

    r2: R2Config = field(default_factory=R2Config)

    def book_tmp(self, slug: str) -> Path:
        return self.tmp_dir / slug


def load_config(**overrides) -> Config:
    """Load .env (if present) then apply overrides, ignoring None values."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)

    cfg = Config(
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        r2=R2Config(
            access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            account_id=os.getenv("R2_ACCOUNT_ID"),
            bucket=os.getenv("R2_BUCKET_NAME", "pdf-study-storage"),
        ),
    )

    for key, value in overrides.items():
        if value is not None and hasattr(cfg, key):
            setattr(cfg, key, value)

    return cfg
