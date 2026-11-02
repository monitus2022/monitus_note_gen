"""Marp CLI rendering to PDF.

Requires Node/npx and a headless Chrome (present on this machine). Local images
require `--allow-local-files`; without it the render silently drops them.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger("render.marp")


def marp_available() -> bool:
    return shutil.which("npx") is not None


def render_pdf(md_path: str | Path, out_path: str | Path, *, timeout: int = 600) -> bool:
    md_path, out_path = Path(md_path), Path(out_path)
    if not marp_available():
        log.warning("npx not found; skipping PDF render for %s (raw .md preserved)", md_path.name)
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx",
        "--yes",
        "@marp-team/marp-cli",
        str(md_path),
        "--pdf",
        "-o",
        str(out_path),
        "--allow-local-files",
        "--no-stdin",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
        log.info("rendered %s", out_path.name)
        return True
    except subprocess.CalledProcessError as exc:
        log.warning("marp PDF render failed for %s: %s", md_path.name, exc.stderr.decode(errors="ignore")[:400])
        return False
    except subprocess.TimeoutExpired:
        log.warning("marp PDF render timed out for %s", md_path.name)
        return False
