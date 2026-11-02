"""Normalized data model returned by all parser backends."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Figure:
    """A figure/table region extracted from the PDF."""

    id: str  # e.g. "fig_03_002"
    page: int  # 1-based page number
    bbox: tuple[float, float, float, float]  # PDF points (x0, y0, x1, y1)
    caption: str | None = None
    alt: str | None = None  # optional VLM-generated alt text
    kind: str = "raster"  # "raster" | "vector"
    image_path: str | None = None  # local path after rasterization
    referenced_by: list[str] = field(default_factory=list)  # chunk ids

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Section:
    title: str
    level: int
    page: int
    markdown: str
    figures: list[Figure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class ParsedDocument:
    title: str | None
    sections: list[Section]
    toc: list[dict] = field(default_factory=list)
    parser: str = "pymupdf"

    def chapter_count(self) -> int:
        """Count top-level (level-1) sections, treating sections as chapters."""
        return sum(1 for s in self.sections if s.level <= 1) or len(self.sections)
