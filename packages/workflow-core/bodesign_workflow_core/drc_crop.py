"""
Visual DRC coordinate cropping utility for closed-loop multimodal inspection.

Parses violation coordinates from KiCad DRC reports and generates high-contrast,
localized 5mm x 5mm raster (PNG) or vector (SVG) visual crops with red target bounding
boxes and scale indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    PIL = None
    PIL_AVAILABLE = False


_COORD_TEXT_RE = re.compile(
    r'(?:@|at)\s*\(?\s*([-0-9.]+)\s*(?:mm)?\s*,\s*([-0-9.]+)\s*(?:mm)?\s*\)?',
    re.IGNORECASE,
)


@dataclass(slots=True)
class DrcViolationCoord:
    violation_id: str
    rule_type: str
    x: float
    y: float
    description: str = ""


@dataclass(slots=True)
class DrcVisualCrop:
    violation_id: str
    rule_type: str
    center_x: float
    center_y: float
    window_mm: float
    crop_file: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "rule_type": self.rule_type,
            "coordinate": [round(self.center_x, 4), round(self.center_y, 4)],
            "window_mm": self.window_mm,
            "crop_file": self.crop_file,
            "description": self.description,
        }


def extract_drc_coordinates(violations: list[dict[str, Any] | str]) -> list[DrcViolationCoord]:
    """
    Extracts 2D violation coordinates from KiCad JSON violation objects or text lines.
    """
    extracted: list[DrcViolationCoord] = []

    for idx, v in enumerate(violations, start=1):
        v_id = f"DRC-{idx:03d}"
        if isinstance(v, str):
            # Parse text report line
            m = _COORD_TEXT_RE.search(v)
            if m:
                extracted.append(
                    DrcViolationCoord(
                        violation_id=v_id,
                        rule_type="clearance" if "clearance" in v.lower() else "violation",
                        x=float(m.group(1)),
                        y=float(m.group(2)),
                        description=v.strip()[:160],
                    )
                )
        elif isinstance(v, dict):
            rule_type = v.get("type", "violation")
            desc = v.get("description", "")

            # 1. Check direct 'pos' or 'coord'
            pos = v.get("pos") or v.get("coordinate")
            if pos:
                if isinstance(pos, dict) and "x" in pos and "y" in pos:
                    extracted.append(
                        DrcViolationCoord(v_id, rule_type, float(pos["x"]), float(pos["y"]), desc)
                    )
                    continue
                elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    extracted.append(
                        DrcViolationCoord(v_id, rule_type, float(pos[0]), float(pos[1]), desc)
                    )
                    continue

            # 2. Check items inside violation
            items = v.get("items", [])
            item_coords = []
            for it in items:
                it_pos = it.get("pos")
                if isinstance(it_pos, dict) and "x" in it_pos and "y" in it_pos:
                    item_coords.append((float(it_pos["x"]), float(it_pos["y"])))
                elif isinstance(it_pos, (list, tuple)) and len(it_pos) >= 2:
                    item_coords.append((float(it_pos[0]), float(it_pos[1])))

            if item_coords:
                avg_x = sum(pt[0] for pt in item_coords) / len(item_coords)
                avg_y = sum(pt[1] for pt in item_coords) / len(item_coords)
                extracted.append(DrcViolationCoord(v_id, rule_type, avg_x, avg_y, desc))
            else:
                # 3. Fallback: search regex in description string
                m = _COORD_TEXT_RE.search(desc)
                if m:
                    extracted.append(
                        DrcViolationCoord(v_id, rule_type, float(m.group(1)), float(m.group(2)), desc)
                    )

    return extracted


def render_svg_crop(
    coord: DrcViolationCoord,
    out_path: Path,
    window_mm: float = 5.0,
) -> None:
    """Renders a standalone SVG diagnostic crop centered at violation coordinates."""
    hw = window_mm / 2.0
    xmin = coord.x - hw
    ymin = coord.y - hw
    box_size = 0.8  # 0.8mm highlight square

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{xmin:.4f} {ymin:.4f} {window_mm:.4f} {window_mm:.4f}" width="500" height="500">
  <rect x="{xmin:.4f}" y="{ymin:.4f}" width="{window_mm:.4f}" height="{window_mm:.4f}" fill="#181818" />
  <!-- Grid lines -->
  <line x1="{xmin:.4f}" y1="{coord.y:.4f}" x2="{coord.x + hw:.4f}" y2="{coord.y:.4f}" stroke="#333333" stroke-width="0.05" stroke-dasharray="0.2,0.2" />
  <line x1="{coord.x:.4f}" y1="{ymin:.4f}" x2="{coord.x:.4f}" y2="{coord.y + hw:.4f}" stroke="#333333" stroke-width="0.05" stroke-dasharray="0.2,0.2" />
  <!-- Red Highlight Target Box -->
  <rect x="{coord.x - box_size/2:.4f}" y="{coord.y - box_size/2:.4f}" width="{box_size:.4f}" height="{box_size:.4f}" fill="rgba(255, 50, 50, 0.3)" stroke="#ff3333" stroke-width="0.08" />
  <!-- Target Crosshair -->
  <circle cx="{coord.x:.4f}" cy="{coord.y:.4f}" r="0.15" fill="#ffcc00" />
</svg>"""
    out_path.write_text(svg_content, encoding="utf-8")


def render_png_crop(
    coord: DrcViolationCoord,
    out_path: Path,
    window_mm: float = 5.0,
    pixels_per_mm: int = 100,
) -> None:
    """Renders a 100px/mm high-contrast diagnostic PNG crop using PIL."""
    if not PIL_AVAILABLE:
        # Fallback to SVG if PIL is not installed
        render_svg_crop(coord, out_path.with_suffix(".svg"), window_mm)
        return

    img_size = int(window_mm * pixels_per_mm)  # 500x500 px
    img = Image.new("RGBA", (img_size, img_size), (24, 24, 24, 255))
    draw = ImageDraw.Draw(img)

    cx = img_size / 2.0
    cy = img_size / 2.0

    # Draw grid ticks (every 1.0mm)
    tick_px = pixels_per_mm
    for offset in range(-int(window_mm // 2), int(window_mm // 2) + 1):
        ox = cx + offset * tick_px
        oy = cy + offset * tick_px
        draw.line([(ox, 0), (ox, img_size)], fill=(45, 45, 45, 255), width=1)
        draw.line([(0, oy), (img_size, oy)], fill=(45, 45, 45, 255), width=1)

    # Highlight box (0.8mm x 0.8mm = 80x80 px)
    box_px = int(0.8 * pixels_per_mm)
    hbx = int(cx - box_px / 2)
    hby = int(cy - box_px / 2)
    draw.rectangle([hbx, hby, hbx + box_px, hby + box_px], fill=(255, 50, 50, 80), outline=(255, 60, 60, 255), width=3)

    # Target crosshair center
    ch_len = 16
    draw.line([(cx - ch_len, cy), (cx + ch_len, cy)], fill=(255, 204, 0, 255), width=2)
    draw.line([(cx, cy - ch_len), (cx, cy + ch_len)], fill=(255, 204, 0, 255), width=2)

    # Scale bar in bottom right corner (1.0 mm)
    bar_x1 = img_size - 130
    bar_y = img_size - 30
    bar_x2 = bar_x1 + pixels_per_mm
    draw.line([(bar_x1, bar_y), (bar_x2, bar_y)], fill=(220, 220, 220, 255), width=3)
    draw.text((bar_x1 + 25, bar_y - 20), "1.0 mm", fill=(200, 200, 200, 255))

    # Header title text
    header = f"[{coord.violation_id}] {coord.rule_type.upper()} ({coord.x:.2f}, {coord.y:.2f})"
    draw.text((15, 15), header, fill=(255, 100, 100, 255))

    img.save(str(out_path), "PNG")


def generate_drc_visual_crops(
    violations: list[dict[str, Any] | str],
    output_dir: Path | str,
    window_mm: float = 5.0,
    preferred_format: str = "png",
) -> list[DrcVisualCrop]:
    """
    Parses violation coordinates and generates localized visual crops.
    Returns metadata list of generated visual crop artifacts.
    """
    coords = extract_drc_coordinates(violations)
    if not coords:
        return []

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    crops: list[DrcVisualCrop] = []

    for c in coords:
        filename = f"{c.violation_id}_{c.rule_type}.{preferred_format}"
        crop_path = out_dir / filename

        if preferred_format.lower() == "png" and PIL_AVAILABLE:
            render_png_crop(c, crop_path, window_mm=window_mm)
        else:
            filename = f"{c.violation_id}_{c.rule_type}.svg"
            crop_path = out_dir / filename
            render_svg_crop(c, crop_path, window_mm=window_mm)

        crops.append(
            DrcVisualCrop(
                violation_id=c.violation_id,
                rule_type=c.rule_type,
                center_x=c.x,
                center_y=c.y,
                window_mm=window_mm,
                crop_file=str(crop_path),
                description=c.description,
            )
        )

    return crops
