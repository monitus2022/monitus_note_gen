"""Cloudflare R2 client (S3-compatible API via boto3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import R2Config
from ..logging_setup import get_logger
from ..storage import content_type_for

log = get_logger("storage.r2")


class R2StorageManager:
    def __init__(self, config: R2Config):
        if not config.is_complete():
            raise ValueError(
                "R2 is not configured. Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and "
                "R2_ACCOUNT_ID in .env (see .env.example)."
            )
        import boto3  # imported lazily so local-sink runs don't need it wired up

        self.bucket = config.bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="auto",
        )

    def put_file(self, local_path: str | Path, key: str) -> None:
        ctype = content_type_for(local_path)
        self._client.upload_file(
            str(local_path), self.bucket, key, ExtraArgs={"ContentType": ctype}
        )
        log.debug("r2 put %s (%s)", key, ctype)

    def put_bytes(self, data: bytes, key: str, content_type: str | None = None) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        log.debug("r2 put %s", key)

    def put_json(self, data: Any, key: str) -> None:
        self.put_bytes(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
            key,
            "application/json; charset=utf-8",
        )
