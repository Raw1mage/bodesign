#!/usr/bin/env bash
# Render a generated hybrid .kicad_sch to a cropped white-background PNG.
# Usage: render_hybrid_sch.sh <in.kicad_sch> <out.png> [width]
set -e
SCH="$1"; OUT="$2"; WIDTH="${3:-3000}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
kicad-cli sch export svg --exclude-drawing-sheet --no-background-color -o "$TMP" "$SCH" >/dev/null
SVG="$(ls "$TMP"/*.svg | head -1)"
cairosvg "$SVG" -o "$TMP/full.png" -b white --output-width "$WIDTH"
python3 - "$TMP/full.png" "$OUT" <<'PY'
import sys
from PIL import Image, ImageChops
im=Image.open(sys.argv[1]).convert("RGB")
bb=ImageChops.difference(im,Image.new("RGB",im.size,(255,255,255))).convert("L").getbbox()
p=25; b=(max(0,bb[0]-p),max(0,bb[1]-p),min(im.width,bb[2]+p),min(im.height,bb[3]+p))
im.crop(b).save(sys.argv[2])
PY
echo "wrote $OUT"
