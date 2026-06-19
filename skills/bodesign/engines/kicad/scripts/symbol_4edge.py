#!/usr/bin/env python3
"""symbol_4edge — re-place a KiCad symbol's pins onto all FOUR edges in datasheet pin-number order.

bodesign emit_symbol packs pins onto 1-2 edges (a long strip), which does not read as a chip.
A real schematic symbol is a body rectangle with pins distributed around all 4 edges. This tool
takes a VALID .kicad_sym (so KiCad's strict parser stays happy — only pin coordinates/angles and
the body rectangle are rewritten), sorts pins by datasheet number (numeric first, then BGA balls),
and lays them sequentially L -> B -> R -> T (QFP convention). Validate with `kicad-cli sym upgrade`
and preview with `kicad-cli sym export svg` + cairosvg.

Usage: symbol_4edge.py <in.kicad_sym> <out.kicad_sym>
"""
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
# pin blocks: type, name, number (positions ignored, we re-place)
pins = re.findall(
    r'\(pin (\w+) line\s*\(at [^)]*\)\s*\(length [^)]*\)\s*'
    r'\(name "([^"]+)"[^\n]*\)\s*\(number "([^"]+)"[^\n]*\)\s*\)', src, re.S)
def keynum(n):
    m = re.match(r'^(\d+)$', n)
    return (0, int(n)) if m else (1, n)   # numeric first, then alpha (BGA balls)
pins.sort(key=lambda p: keynum(p[2]))
N = len(pins); PITCH = 2.54; LEN = 5.08
base, rem = divmod(N, 4)
sizes = [base + (1 if i < rem else 0) for i in range(4)]  # L, B, R, T
nL, nB, nR, nT = sizes
half_h = max(nL, nR, 1) / 2 * PITCH + PITCH
half_w = max(nB, nT, 1) / 2 * PITCH + 12.7   # extra room for pin-name text
# snap to grid
half_w = round(half_w / 1.27) * 1.27; half_h = round(half_h / 1.27) * 1.27
out = []
i = 0
def emit(typ, name, num, x, y, ang):
    out.append(f'\t\t\t(pin {typ} line\n\t\t\t\t(at {x} {y} {ang})\n\t\t\t\t(length {LEN})\n'
               f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
               f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)')
# Left: top->bottom, angle 0, x outside left
y0 = (nL - 1) / 2 * PITCH
for k in range(nL):
    t,nm,no = pins[i]; emit(t,nm,no, round(-(half_w+LEN),2), round(y0-k*PITCH,2), 0); i+=1
# Bottom: left->right, angle 90, y outside bottom
x0 = -(nB - 1) / 2 * PITCH
for k in range(nB):
    t,nm,no = pins[i]; emit(t,nm,no, round(x0+k*PITCH,2), round(-(half_h+LEN),2), 90); i+=1
# Right: bottom->top, angle 180
y0 = -(nR - 1) / 2 * PITCH
for k in range(nR):
    t,nm,no = pins[i]; emit(t,nm,no, round(half_w+LEN,2), round(y0+k*PITCH,2), 180); i+=1
# Top: right->left, angle 270
x0 = (nT - 1) / 2 * PITCH
for k in range(nT):
    t,nm,no = pins[i]; emit(t,nm,no, round(x0-k*PITCH,2), round(half_h+LEN,2), 270); i+=1
pin_sec = "\n".join(out)
rect = (f'\t\t\t(rectangle\n\t\t\t\t(start {-half_w} {half_h})\n\t\t\t\t(end {half_w} {-half_h})\n'
        f'\t\t\t\t(stroke (width 0.254) (type default))\n\t\t\t\t(fill (type background))\n\t\t\t)')
# replace the _0_1 rectangle body and the _1_1 pin section
src = re.sub(r'(\(symbol "[^"]+_0_1"\s*).*?(\n\t\t\))', r'\1' + rect + r'\2', src, count=1, flags=re.S)
src = re.sub(r'(\(symbol "[^"]+_1_1"\s*).*?(\n\t\t\)\n\t\)\n\))', r'\1\n' + pin_sec + r'\2', src, count=1, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(src)
print(f"N={N} sides L/B/R/T={sizes} half_w={half_w} half_h={half_h}")
