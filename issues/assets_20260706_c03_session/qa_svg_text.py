"""SVG-rendered text bbox QA — the ground-truth visual overlap gate.

Prior qa_bbox.py only inspected (global_label)/(label) s-exprs in the .kicad_sch
MODEL, ignoring IC symbol pin-name / pin-number text and refdes/value — so dense
MCU pin smears and connector-label blobs passed the model QA while the RENDERED
page was unreadable. This gate reads the actual kicad-cli SVG output and takes
EVERY <text> element's rendered box:

    box = [x, x+textLength(or len*font*0.6), min(y..), max(y..)+font]
    anchored per text-anchor (start=+x, end=-x, middle=±w/2)

Two text boxes whose intersection area exceeds THRESH * min(area) are a
violation. Same-anchor identical strings (the invisible opacity=0 measurement
copy KiCad emits before its stroked <g>) are de-duplicated: KiCad emits each
label twice (an opacity:0 <text> + a stroked <g><path> vector). We key on
(round(x,2), round(y,2), content) and keep one.

Run: python3 qa_svg_text.py <svg1> <svg2> ...
Exit 0 iff every file has 0 violations.
"""
import re, sys
from collections import defaultdict

THRESH = 0.15      # overlap-area / min-box-area to count as a violation
# a real char is ~0.6*font-size wide in the KiCad stroke font; textLength when
# present is authoritative.
CW_FACTOR = 0.6

TEXT_RE = re.compile(
    r'<text\s+x="(-?[0-9.]+)"\s+y="(-?[0-9.]+)"'
    r'(?:[^>]*?textLength="(-?[0-9.]+)")?'
    r'[^>]*?font-size="(-?[0-9.]+)"'
    r'(?:[^>]*?text-anchor="(start|middle|end)")?'
    r'[^>]*?>([^<]*)</text>',
    re.DOTALL,
)


def parse_texts(svg):
    out = []
    seen = set()
    for m in TEXT_RE.finditer(svg):
        x = float(m.group(1)); y = float(m.group(2))
        tlen = float(m.group(3)) if m.group(3) else None
        fs = float(m.group(4))
        anchor = m.group(5) or "start"
        content = m.group(6).strip()
        if not content:
            continue
        key = (round(x, 2), round(y, 2), content)
        if key in seen:
            continue
        seen.add(key)
        w = tlen if tlen is not None else len(content) * fs * CW_FACTOR
        h = fs
        # y is the text BASELINE; box spans [y - h*0.8, y + h*0.2] roughly.
        if anchor == "start":
            x0, x1 = x, x + w
        elif anchor == "end":
            x0, x1 = x - w, x
        else:  # middle
            x0, x1 = x - w / 2, x + w / 2
        y0, y1 = y - h * 0.8, y + h * 0.2
        out.append({"c": content, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                    "area": max((x1 - x0), 1e-6) * max((y1 - y0), 1e-6)})
    return out


def overlap_area(a, b):
    ix = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    iy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    if ix <= 0 or iy <= 0:
        return 0.0
    return ix * iy


def qa(path):
    svg = open(path).read()
    texts = parse_texts(svg)
    # spatial bucket to avoid O(n^2) on 800+ texts: 5mm grid
    G = 5.0
    grid = defaultdict(list)
    for t in texts:
        gx0 = int(t["x0"] // G); gx1 = int(t["x1"] // G)
        gy0 = int(t["y0"] // G); gy1 = int(t["y1"] // G)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                grid[(gx, gy)].append(t)
    checked = set()
    violations = []
    cells = list(grid.values())
    for bucket in cells:
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                a, b = bucket[i], bucket[j]
                pair = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
                if pair in checked:
                    continue
                checked.add(pair)
                ov = overlap_area(a, b)
                if ov > THRESH * min(a["area"], b["area"]):
                    violations.append((a["c"], b["c"],
                                       round(a["x0"], 1), round(a["y0"], 1),
                                       round(ov / min(a["area"], b["area"]), 2)))
    name = path.split("/")[-1]
    violations.sort(key=lambda v: -v[4])
    n = len(violations)
    tag = "PASS" if n == 0 else "FAIL"
    ex = ""
    if violations:
        ex = "\n    " + "\n    ".join(
            f"{a!r} X {b!r} @({x},{y}) ov={r}" for a, b, x, y, r in violations[:8])
    print(f"[{name}] texts={len(texts)} overlaps={n} -> {tag}{ex}")
    return n == 0


if __name__ == "__main__":
    allok = True
    for p in sys.argv[1:]:
        allok &= qa(p)
    print("=== SVG-TEXT QA:", "ALL PASS" if allok else "SOME FAIL", "===")
    sys.exit(0 if allok else 1)
