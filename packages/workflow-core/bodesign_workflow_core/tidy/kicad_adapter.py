"""
KiCad PCB S-expression adapter for layout tidy operations.

Applies grid snapping and silkscreen-over-pad tidy directly to `.kicad_pcb` files
using robust regex and bracket scanning without requiring GUI or pcbnew.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .grid import snap_coord
from .silk_tidy import FootprintSilkRecord, PadGeometry, tidy_footprint_silk


_FOOTPRINT_START_RE = re.compile(r'\(\s*footprint\s+("[^"]*"|\S+)', re.IGNORECASE)
_AT_RE = re.compile(r'\(\s*at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\s*\)', re.IGNORECASE)
_PAD_RE = re.compile(
    r'\(\s*pad\s+("[^"]*"|\S+)\s+(\S+)\s+(\S+)\s+'
    r'\(\s*at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+[-0-9.]+)?\s*\)\s+'
    r'\(\s*size\s+([-0-9.]+)\s+([-0-9.]+)\s*\)',
    re.IGNORECASE,
)
_REF_PROP_RE = re.compile(
    r'\(\s*property\s+"Reference"\s+("[^"]*")\s+'
    r'\(\s*at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\s*\)',
    re.IGNORECASE,
)
_FP_TEXT_REF_RE = re.compile(
    r'\(\s*fp_text\s+reference\s+("[^"]*")\s+'
    r'\(\s*at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\s*\)',
    re.IGNORECASE,
)


def tidy_kicad_pcb_content(
    pcb_text: str,
    actions: list[str] | None = None,
    grid_mm: float = 0.1,
    silk_clearance_mm: float = 0.25,
) -> tuple[str, dict[str, int]]:
    """
    Applies layout tidy operations on raw `.kicad_pcb` text.
    Supported actions: "grid_snap", "silk_tidy".
    """
    effective_actions = set(actions or ["grid_snap", "silk_tidy"])
    snapped_count = 0
    silk_fixed_count = 0
    footprint_count = 0

    output_chunks: list[str] = []
    last_idx = 0

    for m in _FOOTPRINT_START_RE.finditer(pcb_text):
        start_pos = m.start()
        output_chunks.append(pcb_text[last_idx:start_pos])

        # Scan balanced footprint block
        depth = 0
        in_string = False
        escaped = False
        end_pos = start_pos

        for i in range(start_pos, len(pcb_text)):
            ch = pcbtext_ch = pcb_text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break

        fp_chunk = pcb_text[start_pos:end_pos]
        footprint_count += 1

        # 1. Grid Snap Footprint Origin
        if "grid_snap" in effective_actions:
            # First `(at x y ...)` inside footprint is its placement
            at_match = _AT_RE.search(fp_chunk)
            if at_match:
                fx = float(at_match.group(1))
                fy = float(at_match.group(2))
                frot = at_match.group(3)
                s_fx = snap_coord(fx, grid_mm)
                s_fy = snap_coord(fy, grid_mm)

                if abs(s_fx - fx) > 1e-4 or abs(s_fy - fy) > 1e-4:
                    snapped_count += 1
                    rot_str = f" {frot}" if frot is not None else ""
                    new_at = f"(at {s_fx:.4f} {s_fy:.4f}{rot_str})"
                    fp_chunk = fp_chunk[:at_match.start()] + new_at + fp_chunk[at_match.end():]

        # 2. Silkscreen Tidy
        if "silk_tidy" in effective_actions:
            # Parse pads
            pads: list[PadGeometry] = []
            for pm in _PAD_RE.finditer(fp_chunk):
                pname = pm.group(1).strip('"')
                px = float(pm.group(4))
                py = float(pm.group(5))
                pw = float(pm.group(6))
                ph = float(pm.group(7))
                pads.append(PadGeometry(name=pname, rel_x=px, rel_y=py, width=pw, height=ph))

            # Find reference text
            ref_match = _REF_PROP_RE.search(fp_chunk)
            is_legacy = False
            if not ref_match:
                ref_match = _FP_TEXT_REF_RE.search(fp_chunk)
                is_legacy = True

            if ref_match and pads:
                ref_text = ref_match.group(1).strip('"')
                rx = float(ref_match.group(2))
                ry = float(ref_match.group(3))
                rrot = float(ref_match.group(4)) if ref_match.group(4) else 0.0

                silk_rec = FootprintSilkRecord(
                    refdes=ref_text,
                    origin_x=0.0,
                    origin_y=0.0,
                    pads=pads,
                    silk_ref_text=ref_text,
                    silk_pos_x=rx,
                    silk_pos_y=ry,
                    silk_rotation=rrot,
                )

                tidied_rec, changed = tidy_footprint_silk(silk_rec, clearance_mm=silk_clearance_mm)
                if changed:
                    silk_fixed_count += 1
                    new_rx = tidied_rec.silk_pos_x
                    new_ry = tidied_rec.silk_pos_y
                    new_rot = tidied_rec.silk_rotation

                    # Substitute new position into reference property
                    if is_legacy:
                        new_prop = f'(fp_text reference "{ref_text}" (at {new_rx:.4f} {new_ry:.4f} {new_rot:.1f})'
                    else:
                        new_prop = f'(property "Reference" "{ref_text}" (at {new_rx:.4f} {new_ry:.4f} {new_rot:.1f})'

                    fp_chunk = fp_chunk[:ref_match.start()] + new_prop + fp_chunk[ref_match.end():]

        output_chunks.append(fp_chunk)
        last_idx = end_pos

    output_chunks.append(pcb_text[last_idx:])
    updated_pcb = "".join(output_chunks)

    stats = {
        "footprints_processed": footprint_count,
        "footprints_snapped": snapped_count,
        "silk_overlaps_resolved": silk_fixed_count,
    }
    return updated_pcb, stats


def tidy_kicad_pcb(
    pcb_path: str | Path,
    actions: list[str] | None = None,
    grid_mm: float = 0.1,
    silk_clearance_mm: float = 0.25,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    """Reads a .kicad_pcb file, performs layout tidy operations, and writes back."""
    src = Path(pcb_path)
    if not src.exists():
        raise FileNotFoundError(f"KiCad PCB file not found: {src}")

    content = src.read_text(encoding="utf-8")
    updated_content, stats = tidy_kicad_pcb_content(
        content,
        actions=actions,
        grid_mm=grid_mm,
        silk_clearance_mm=silk_clearance_mm,
    )

    dest = Path(out_path) if out_path else src
    dest.write_text(updated_content, encoding="utf-8")

    return {
        "source": str(src),
        "destination": str(dest),
        "actions": actions or ["grid_snap", "silk_tidy"],
        "stats": stats,
    }
