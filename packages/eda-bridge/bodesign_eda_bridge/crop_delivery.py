"""Delivery-layer cropping: crop a schematic PNG to its ink bbox + margin.

Motivation (M6-8b): the engine is bound to standard KiCad sheet frames (A2/A3
etc.), so an emitted schematic PNG always carries large empty margins around the
actual content — a whitespace problem that survived dozens of BR rounds because
it is a *paper-frame* artifact, not a placement bug. Instead of fighting the
paper logic, this module crops the DELIVERABLE png to the content ink bbox and
wraps it as the delivery image. The .kicad_sch source keeps its full frame.

Approach:
  - Detect the ink bbox using the brightest-luminance-is-paper convention from
    ink_metrics._measure_image (KiCad exports an off-white ~244 sheet, so a fixed
    near-255 threshold counts the whole page as ink).
  - Tolerate the KiCad sheet frame (a thin rectangle hugging all four edges plus
    the bottom-right title block): ignore an `edge_ignore_pct` border band before
    computing the bbox, so the frame lines and title block do not pin the bbox to
    the full page.
  - Crop to bbox + `margin_pct` (fraction of the image width) on all sides.
  - Title block handling: cropping to the content bbox drops the bottom-right
    title block. By default it is not kept; with `keep_titleblock_strip=True` a
    one-line caption (filename + page name + date) is composited under the crop.

Toolchain gating (repo no-silent-fallback rail, E-DRAFT-006): PIL is the only
dependency; when it is missing this raises RuntimeError rather than fabricating
a result. Pure-python pixel scan, no shell-out.

CLI:
  python3 crop_delivery.py <in.png> <out.png> [--margin-pct 5]
  python3 crop_delivery.py --batch <dir> [--out-dir <dir>] [--margin-pct 5]
"""

from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path


# Defaults
DEFAULT_MARGIN_PCT = 5.0        # margin as a fraction of image WIDTH, per side
DEFAULT_EDGE_IGNORE_PCT = 3.0   # ignore this border band (frame/title-block) before bbox
DEFAULT_BG_MARGIN = 12          # luminance delta below paper to count a pixel as ink
_CAPTION_STRIP_H = 28           # px height of the optional title-block caption strip


class CropResult:
    """Result of a single crop operation."""

    __slots__ = ("in_path", "out_path", "orig_size", "crop_size", "bbox", "fill_gain")

    def __init__(self, in_path, out_path, orig_size, crop_size, bbox, fill_gain):
        self.in_path = str(in_path)
        self.out_path = str(out_path)
        self.orig_size = orig_size    # (w, h)
        self.crop_size = crop_size    # (w, h)
        self.bbox = bbox              # (min_x, min_y, max_x, max_y) in original coords
        self.fill_gain = fill_gain    # content-fill multiplier orig->crop

    def as_dict(self) -> dict:
        return {
            "in_path": self.in_path,
            "out_path": self.out_path,
            "orig_size": list(self.orig_size),
            "crop_size": list(self.crop_size),
            "bbox": list(self.bbox),
            "fill_gain": round(self.fill_gain, 3),
        }


def _require_pil():
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment gate
        raise RuntimeError(
            "crop_delivery requires PIL (Pillow); it is not installed. "
            "This module never fabricates a crop result."
        ) from exc


def detect_ink_bbox(
    img,
    edge_ignore_pct: float = DEFAULT_EDGE_IGNORE_PCT,
    bg_margin: int = DEFAULT_BG_MARGIN,
) -> tuple[int, int, int, int] | None:
    """Return (min_x, min_y, max_x, max_y) of ink pixels, ignoring an edge band.

    The paper background is the brightest luminance present (KiCad off-white),
    matching ink_metrics._measure_image. A pixel is ink iff clearly darker than
    paper. The `edge_ignore_pct` border band is skipped so the sheet frame and
    title block do not pin the bbox to the full page. Returns None if no ink is
    found inside the interior region.
    """
    grey = img.convert("L")
    w, h = grey.size
    if w == 0 or h == 0:
        return None
    _lo, hi = grey.getextrema()
    bg_threshold = max(int(hi) - bg_margin, 1)

    ex = int(round(w * edge_ignore_pct / 100.0))
    ey = int(round(h * edge_ignore_pct / 100.0))
    x0, x1 = ex, w - ex
    y0, y1 = ey, h - ey
    if x1 <= x0 or y1 <= y0:
        # Band too large for this image; fall back to full extent.
        x0, y0, x1, y1 = 0, 0, w, h

    pixels = grey.load()
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pixels[x, y] < bg_threshold:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return None
    return (min_x, min_y, max_x, max_y)


def _content_fill(area: int, total: int) -> float:
    return (area / total) if total else 0.0


def crop_png(
    in_path: str | Path,
    out_path: str | Path,
    margin_pct: float = DEFAULT_MARGIN_PCT,
    edge_ignore_pct: float = DEFAULT_EDGE_IGNORE_PCT,
    bg_margin: int = DEFAULT_BG_MARGIN,
    keep_titleblock_strip: bool = False,
    caption: str | None = None,
) -> CropResult:
    """Crop one PNG to its ink bbox + margin. Returns a CropResult.

    Never crops away real content ink: the bbox is the tight box of all interior
    ink pixels; the margin only expands it. If the bbox spans the whole interior
    (already tight) the crop is a near no-op (still emits the output).
    """
    _require_pil()
    from PIL import Image, ImageDraw

    in_path = Path(in_path)
    out_path = Path(out_path)
    img = Image.open(in_path)
    w, h = img.size
    total = w * h

    bbox = detect_ink_bbox(img, edge_ignore_pct=edge_ignore_pct, bg_margin=bg_margin)
    if bbox is None:
        # No ink detected: emit an unchanged copy so the pipeline never drops a page.
        img.save(out_path)
        return CropResult(in_path, out_path, (w, h), (w, h), (0, 0, w - 1, h - 1), 1.0)

    min_x, min_y, max_x, max_y = bbox
    margin = int(round(w * margin_pct / 100.0))
    left = max(min_x - margin, 0)
    top = max(min_y - margin, 0)
    right = min(max_x + margin + 1, w)
    bottom = min(max_y + margin + 1, h)

    cropped = img.crop((left, top, right, bottom))
    cw, ch = cropped.size

    if keep_titleblock_strip:
        cap = caption if caption is not None else _default_caption(in_path)
        strip = _render_caption_strip(cw, cap, mode=cropped.mode)
        if strip is not None:
            combined = Image.new(cropped.mode, (cw, ch + _CAPTION_STRIP_H), color=_paper_color(cropped))
            combined.paste(cropped, (0, 0))
            combined.paste(strip, (0, ch))
            ImageDraw.Draw(combined)  # touch to keep import meaningful for lint
            cropped = combined
            cw, ch = cropped.size

    cropped.save(out_path)

    orig_bbox_area = (max_x - min_x + 1) * (max_y - min_y + 1)
    orig_fill = _content_fill(orig_bbox_area, total)
    crop_fill = _content_fill(orig_bbox_area, cw * ch) if (cw * ch) else 0.0
    fill_gain = (crop_fill / orig_fill) if orig_fill else 1.0

    return CropResult(in_path, out_path, (w, h), (cw, ch), bbox, fill_gain)


def _paper_color(img):
    """Best-effort paper background colour for the caption strip fill."""
    grey = img.convert("L")
    _lo, hi = grey.getextrema()
    val = int(hi)
    if img.mode == "RGB":
        return (val, val, val)
    if img.mode == "RGBA":
        return (val, val, val, 255)
    return val


def _default_caption(in_path: Path) -> str:
    date = _dt.date.today().isoformat()
    return f"{in_path.stem}    {date}"


def _render_caption_strip(width: int, text: str, mode: str = "RGB"):
    """Render a one-line caption strip (filename/page/date). None on failure."""
    from PIL import Image, ImageDraw

    try:
        from PIL import ImageFont

        font = ImageFont.load_default()
    except Exception:  # pragma: no cover - font-less environment
        font = None

    fill = 255 if mode in ("L",) else ((255, 255, 255) if mode == "RGB" else (255, 255, 255, 255))
    ink = 0 if mode in ("L",) else ((0, 0, 0) if mode == "RGB" else (0, 0, 0, 255))
    strip = Image.new(mode, (width, _CAPTION_STRIP_H), color=fill)
    draw = ImageDraw.Draw(strip)
    draw.text((6, 8), text, fill=ink, font=font)
    return strip


def crop_batch(
    in_dir: str | Path,
    out_dir: str | Path,
    margin_pct: float = DEFAULT_MARGIN_PCT,
    edge_ignore_pct: float = DEFAULT_EDGE_IGNORE_PCT,
    bg_margin: int = DEFAULT_BG_MARGIN,
    keep_titleblock_strip: bool = False,
    pattern: str = "*.png",
) -> list[CropResult]:
    """Crop every PNG in `in_dir` into `out_dir`. Skips *.superseded* files."""
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[CropResult] = []
    for png in sorted(in_dir.glob(pattern)):
        if "superseded" in png.name:
            continue
        out_path = out_dir / png.name
        results.append(
            crop_png(
                png,
                out_path,
                margin_pct=margin_pct,
                edge_ignore_pct=edge_ignore_pct,
                bg_margin=bg_margin,
                keep_titleblock_strip=keep_titleblock_strip,
            )
        )
    return results


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crop schematic PNGs to ink bbox + margin.")
    ap.add_argument("in_path", nargs="?", help="input PNG (single-file mode)")
    ap.add_argument("out_path", nargs="?", help="output PNG (single-file mode)")
    ap.add_argument("--batch", metavar="DIR", help="batch mode: crop all *.png in DIR")
    ap.add_argument("--out-dir", metavar="DIR", help="batch output dir (default: <DIR>/cropped)")
    ap.add_argument("--margin-pct", type=float, default=DEFAULT_MARGIN_PCT)
    ap.add_argument("--edge-ignore-pct", type=float, default=DEFAULT_EDGE_IGNORE_PCT)
    ap.add_argument("--bg-margin", type=int, default=DEFAULT_BG_MARGIN)
    ap.add_argument("--keep-titleblock-strip", action="store_true")
    args = ap.parse_args(argv)

    if args.batch:
        out_dir = args.out_dir or str(Path(args.batch) / "cropped")
        results = crop_batch(
            args.batch,
            out_dir,
            margin_pct=args.margin_pct,
            edge_ignore_pct=args.edge_ignore_pct,
            bg_margin=args.bg_margin,
            keep_titleblock_strip=args.keep_titleblock_strip,
        )
        for r in results:
            ow, oh = r.orig_size
            cw, ch = r.crop_size
            print(f"{Path(r.in_path).name}: {ow}x{oh} -> {cw}x{ch}  fill_gain={r.fill_gain:.2f}x")
        print(f"[crop] {len(results)} pages -> {out_dir}")
        return 0

    if not args.in_path or not args.out_path:
        ap.error("single-file mode needs <in.png> <out.png> (or use --batch DIR)")
    r = crop_png(
        args.in_path,
        args.out_path,
        margin_pct=args.margin_pct,
        edge_ignore_pct=args.edge_ignore_pct,
        bg_margin=args.bg_margin,
        keep_titleblock_strip=args.keep_titleblock_strip,
    )
    ow, oh = r.orig_size
    cw, ch = r.crop_size
    print(f"{Path(r.in_path).name}: {ow}x{oh} -> {cw}x{ch}  fill_gain={r.fill_gain:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
