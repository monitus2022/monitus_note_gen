"""Stage 1b: figure extraction.

Rasterizes figure regions (both embedded raster images and clustered vector
drawings), filters out logos/watermarks/small decorations, and associates each
region with the nearest PDF caption line whose text matches `Figure N`/`Table N`.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz  # PyMuPDF (new module name)

from .logging_setup import get_logger
from .models import Figure
from .parser import CAPTION_RE

log = get_logger("figures")


def _pt_to_px(pt: float, dpi: int) -> float:
    return pt * dpi / 72.0


def _caption_for(page: fitz.Page, rect: fitz.Rect) -> str | None:
    """Nearest caption-bearing text line below or above the region."""
    best: tuple[float, str] | None = None
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if not text or not CAPTION_RE.match(text):
                continue
            lrect = fitz.Rect(line.get("bbox", rect))
            # vertical distance if the line sits above or below the region
            if lrect.y0 >= rect.y1:
                dist = lrect.y0 - rect.y1
            elif lrect.y1 <= rect.y0:
                dist = rect.y0 - lrect.y1
            else:
                dist = 0.0  # overlapping
            if dist <= 80 and (best is None or dist < best[0]):
                best = (dist, text)
    return best[1] if best else None


def _vector_regions(
    page: fitz.Page,
    *,
    min_drawings: int = 4,
    min_area_pt: float = 8000.0,
    gap_pt: float = 15.0,
) -> list[fitz.Rect]:
    """Cluster drawings into candidate figure regions.

    Conservative: requires several primitive drawings whose union is reasonably
    large. This intentionally misses some figures rather than emitting tables and
    rule-lines as figures.
    """
    rects = [fitz.Rect(d["rect"]) for d in page.get_drawings() if d.get("rect")]
    rects = [r for r in rects if r.width > 2 and r.height > 2]
    if len(rects) < min_drawings:
        return []

    clusters: list[list[fitz.Rect]] = []
    for r in rects:
        placed = False
        for cluster in clusters:
            union = cluster[0]
            for other in cluster[1:]:
                union |= other
            expanded = fitz.Rect(union) + (-gap_pt, -gap_pt, gap_pt, gap_pt)
            if expanded.intersects(r):
                cluster.append(r)
                placed = True
                break
        if not placed:
            clusters.append([r])

    regions: list[fitz.Rect] = []
    for cluster in clusters:
        if len(cluster) < min_drawings:
            continue
        union = cluster[0]
        for other in cluster[1:]:
            union |= other
        if union.get_area() >= min_area_pt:
            regions.append(union)
    return regions


def collect_figures(
    doc: fitz.Document,
    images_dir: Path,
    *,
    dpi: int = 200,
    min_side_px: int = 50,
    max_repeat_pages: int = 5,
    include_vector: bool = True,
    slug: str = "fig",
) -> list[Figure]:
    """Extract, filter and rasterize figures across the whole document."""
    images_dir.mkdir(parents=True, exist_ok=True)
    min_side_pt = min_side_px * 72.0 / dpi

    # Pass 1: tally raster-image hashes to find repeated logos/watermarks.
    digest_pages: dict[str, set[int]] = {}
    for pno in range(doc.page_count):
        for info in doc[pno].get_image_info(hashes=True):
            if info.get("digest"):
                digest_pages.setdefault(info["digest"], set()).add(pno)

    figures: list[Figure] = []
    counter = 0

    for pno in range(doc.page_count):
        page = doc[pno]
        page_no = pno + 1
        regions: list[tuple[fitz.Rect, str, str | None]] = []

        for info in page.get_image_info(hashes=True):
            rect = fitz.Rect(info["bbox"])
            digest = info.get("digest")
            if digest and len(digest_pages.get(digest, ())) > max_repeat_pages:
                continue  # repeated many pages -> logo/watermark
            if rect.width < min_side_pt or rect.height < min_side_pt:
                continue
            regions.append((rect, "raster", None))

        if include_vector:
            for rect in _vector_regions(page):
                if rect.width < min_side_pt or rect.height < min_side_pt:
                    continue
                # skip if it substantially overlaps already-captured raster regions
                if any(rect.intersects(r) and (rect & r).get_area() > 0.5 * rect.get_area() for r, _, _ in regions):
                    continue
                regions.append((rect, "vector", None))

        for rect, kind, _ in regions:
            counter += 1
            fig_id = f"{slug}_{page_no:03d}_{counter:04d}"
            out = images_dir / f"{fig_id}.png"
            try:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), clip=rect, alpha=False
                )
                pix.save(str(out))
            except Exception as exc:  # pragma: no cover - guard rasterization
                log.warning("failed to rasterize %s: %s", fig_id, exc)
                continue
            figures.append(
                Figure(
                    id=fig_id,
                    page=page_no,
                    bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                    caption=_caption_for(page, rect),
                    kind=kind,
                    image_path=str(out),
                )
            )

    log.info("extracted %d figure(s)", len(figures))
    return figures


def attach_figures_to_sections(sections, figures: list[Figure]) -> None:
    """Assign each figure to the section whose page range contains it."""
    for fig in figures:
        owner = None
        for sec in sections:
            if sec.page <= fig.page:
                owner = sec
            else:
                break
        if owner is not None:
            owner.figures.append(fig)
