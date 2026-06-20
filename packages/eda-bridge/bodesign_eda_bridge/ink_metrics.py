"""Ink/bbox quantitative metrics for emitted schematics (DD-6, A6).

Renders a `.kicad_sch`-derived PDF to a raster and measures:
  - ink_pct: fraction of non-background pixels (0-100).
  - content_fill_pct: content bounding box as a fraction of the page (0-100).

Toolchain gating (repo no-silent-fallback rail, E-DRAFT-006): when the render
toolchain (kicad-cli for PDF export, pdftoppm/poppler for PDF→raster, PIL for
pixel stats) is missing, this returns `available=False` + the missing-tool list.
It NEVER fabricates a metric.

Pure-python core: the pixel statistics are pure-python; the PDF render +
rasterise steps shell out to worker-side CLIs and are gated explicitly.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def _missing_tools() -> list[str]:
    missing: list[str] = []
    if shutil.which("kicad-cli") is None:
        missing.append("kicad-cli")
    if shutil.which("pdftoppm") is None:
        missing.append("pdftoppm")
    try:
        import PIL  # noqa: F401
    except ImportError:
        missing.append("PIL")
    return missing


def _unavailable(missing: list[str]) -> dict:
    return {
        "available": False,
        "missing_tools": missing,
        "ink_pct": None,
        "content_fill_pct": None,
        "dpi": None,
    }


def measure_schematic_ink(schematic_path: str | Path, dpi: int = 150) -> dict:
    """Measure ink% + content fill% of a schematic by rendering it to a raster.

    Returns an InkMetrics dict (see data-schema.json). On any missing tool or
    render failure, returns an explicit `available=False` payload — no fabricated
    numbers (E-DRAFT-006).
    """
    missing = _missing_tools()
    if missing:
        return _unavailable(missing)

    from PIL import Image

    schematic = Path(schematic_path)
    if not schematic.exists():
        return {
            "available": False,
            "missing_tools": ["schematic-not-found"],
            "ink_pct": None,
            "content_fill_pct": None,
            "dpi": None,
        }

    with tempfile.TemporaryDirectory(prefix="bodesign-ink-") as tmp:
        tmp_dir = Path(tmp)
        pdf_path = tmp_dir / f"{schematic.stem}.pdf"
        export = subprocess.run(
            ["kicad-cli", "sch", "export", "pdf", str(schematic), "-o", str(pdf_path)],
            capture_output=True,
            text=True,
        )
        if not pdf_path.exists():
            return {
                "available": False,
                "missing_tools": ["kicad-cli-pdf-export-failed"],
                "ink_pct": None,
                "content_fill_pct": None,
                "dpi": None,
            }

        png_prefix = tmp_dir / "page"
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(png_prefix)],
            capture_output=True,
            text=True,
        )
        pages = sorted(tmp_dir.glob("page*.png"))
        if not pages:
            return {
                "available": False,
                "missing_tools": ["pdftoppm-render-failed"],
                "ink_pct": None,
                "content_fill_pct": None,
                "dpi": None,
            }

        img = Image.open(pages[0]).convert("L")
        ink_pct, content_fill_pct = _measure_image(img)

    return {
        "available": True,
        "missing_tools": [],
        "ink_pct": round(ink_pct, 4),
        "content_fill_pct": round(content_fill_pct, 4),
        "dpi": dpi,
    }


def _measure_image(img, bg_threshold: int = 250) -> tuple[float, float]:
    """Compute (ink_pct, content_fill_pct) from a greyscale PIL image.

    A pixel is "ink" iff its luminance < bg_threshold (near-white = background).
    content bbox = tight box around all ink pixels. Pure-python pixel scan.
    """
    w, h = img.size
    total = w * h
    if total == 0:
        return 0.0, 0.0
    pixels = img.load()
    ink = 0
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if pixels[x, y] < bg_threshold:
                ink += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    ink_pct = 100.0 * ink / total
    if max_x < 0:
        return ink_pct, 0.0
    bbox_area = (max_x - min_x + 1) * (max_y - min_y + 1)
    content_fill_pct = 100.0 * bbox_area / total
    return ink_pct, content_fill_pct
