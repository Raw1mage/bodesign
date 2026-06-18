#!/usr/bin/env bash
# render_sch_png.sh — render KiCad schematic(s) to a directly-openable PNG preview.
#
# Standard C03 step (see ../GUIDE.md SOP step 2): after bodesign_compose_schematic
# returns ERC-clean, produce a PNG next to each .kicad_sch so a human can review the
# sheet without opening KiCad. kicad-cli has no direct PNG export for schematics, so
# the route is: sch -> PDF (kicad-cli) -> PNG (pdftoppm). The embedded lib_symbols in
# the .kicad_sch make this self-contained (no symbol-lib resolution needed).
#
# The PNG is a REVIEW artifact, not a deliverable gate — ERC (the kicad-cli validation
# block from compose) remains the correctness check. Do not treat a rendered PNG as
# evidence of correctness.
#
# Usage:
#   render_sch_png.sh <file.kicad_sch | dir-of-sheets> [dpi]   # default dpi=150
# Examples:
#   render_sch_png.sh generated/sch_radio/aiguard_radio.kicad_sch
#   render_sch_png.sh generated/                                # every sheet under it
#
# Requires: kicad-cli (KiCad 9) + pdftoppm (poppler-utils). If pdftoppm is absent,
# fall back to `kicad-cli sch export svg` and convert with rsvg-convert/inkscape, or
# just ship the PDF — say so rather than silently skipping the preview.
set -euo pipefail

DPI="${2:-150}"

command -v kicad-cli >/dev/null || { echo "render_sch_png: kicad-cli not found" >&2; exit 1; }
command -v pdftoppm  >/dev/null || { echo "render_sch_png: pdftoppm not found (poppler-utils); fall back to SVG/PDF" >&2; exit 1; }

render_one() {
  local sch="$1" dir stem
  dir="$(dirname "$sch")"; stem="$(basename "$sch" .kicad_sch)"
  kicad-cli sch export pdf --output "$dir/$stem.pdf" "$sch" >/dev/null
  pdftoppm -png -r "$DPI" "$dir/$stem.pdf" "$dir/$stem" >/dev/null
  for png in "$dir/$stem"-*.png; do echo "rendered: $png"; done
}

arg="${1:?usage: render_sch_png.sh <file.kicad_sch|dir> [dpi]}"
if [ -d "$arg" ]; then
  found=0
  while IFS= read -r f; do found=1; render_one "$f"; done < <(find "$arg" -name '*.kicad_sch')
  [ "$found" = 1 ] || { echo "render_sch_png: no .kicad_sch under $arg" >&2; exit 1; }
else
  render_one "$arg"
fi
