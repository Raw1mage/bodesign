"""SVG-rendered text-overlap QA (BR2 · 2026-07-06).

The ground-truth visual gate. Model-layer QA (inspecting label anchors in the
.kicad_sch s-expr) has a structural blind spot: it ignores IC pin-name/
pin-number text, refdes/value, and power-port Value glyphs — so dense pin smears
and connector-label blobs passed model QA while the RENDERED page was unreadable
(aiguard C03 v03: 2 rounds of false "QA passed" vs fresh-eyes FAIL).

This gate reads the actual kicad-cli SVG and takes EVERY <text> element's
rendered box. Two boxes whose intersection exceeds THRESH*min(area) = violation.

Seed: issues/assets_20260706_c03_session/qa_svg_text.py (verified — the only
model gate that aligned with fresh-eyes visual judgement).

Known baselines (aiguard CCM 5 pages, for regression floor):
  01_power=13 02_mcu=6 03_memory=18 04_wireless=3 05_stamp=2
Any engine text change may only lower these, never raise.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

THRESH = 0.15       # overlap-area / min-box-area to count as a violation
CW_FACTOR = 0.6     # a stroke-font char is ~0.6*font-size wide

TEXT_RE = re.compile(
    r'<text\s+x="(-?[0-9.]+)"\s+y="(-?[0-9.]+)"'
    r'(?:[^>]*?textLength="(-?[0-9.]+)")?'
    r'[^>]*?font-size="(-?[0-9.]+)"'
    r'(?:[^>]*?text-anchor="(start|middle|end)")?'
    r'[^>]*?>([^<]*)</text>',
    re.DOTALL,
)


@dataclass
class TextQAReport:
    path: str
    texts: int
    violations: list[tuple] = field(default_factory=list)  # (a, b, x, y, ratio)

    @property
    def ok(self) -> bool:
        return not self.violations

    def summary(self) -> str:
        n = len(self.violations)
        tag = "PASS" if n == 0 else "FAIL"
        ex = ""
        if self.violations:
            ex = "\n    " + "\n    ".join(
                f"{a!r} X {b!r} @({x},{y}) ov={r}"
                for a, b, x, y, r in self.violations[:8])
        return f"[{self.path.split('/')[-1]}] texts={self.texts} overlaps={n} -> {tag}{ex}"


def parse_texts(svg: str) -> list[dict]:
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
        if key in seen:  # KiCad emits opacity:0 measurement copy + stroked <g>
            continue
        seen.add(key)
        w = tlen if tlen is not None else len(content) * fs * CW_FACTOR
        h = fs
        if anchor == "start":
            x0, x1 = x, x + w
        elif anchor == "end":
            x0, x1 = x - w, x
        else:
            x0, x1 = x - w / 2, x + w / 2
        y0, y1 = y - h * 0.8, y + h * 0.2
        out.append({"c": content, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                    "area": max((x1 - x0), 1e-6) * max((y1 - y0), 1e-6)})
    return out


def _overlap_area(a, b) -> float:
    ix = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    iy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    if ix <= 0 or iy <= 0:
        return 0.0
    return ix * iy


def qa_svg_text(path: str,
                peripheral_texts: set[str] | None = None) -> TextQAReport:
    """Text-overlap gate over a kicad-cli SVG.

    peripheral_texts (DD-8, eda_draftsman-v2 task 1.5) scopes the gate's
    jurisdiction to the artifacts the DRAFTER draws (net labels / power ports),
    NOT vendor symbol-body internal pin-name<->pin-name overlaps:
      - None (default): CURRENT whole-page behaviour — every text<->text pair
        counts (preserves the documented CCM per-page baselines).
      - a set of strings: a violation counts ONLY IF at least one of the two
        overlapping texts' rendered `content` is in the set (i.e. at least one
        side is a drafter-drawn net label). A pure symbol-text<->symbol-text
        overlap (neither side in the set) is EXCLUDED — the drafter has no
        authority over the vendor symbol's internal pin-name grid (DD-1).

    Edge case: a net-label string could coincidentally equal a pin-name string;
    a symbol-internal overlap between two such texts would then be counted. The
    set-membership test is on rendered `content`, so this residual risk is
    accepted per the DD-8 baseline. Future hardening: distinguish drafter labels
    from pin names by SVG attributes (KiCad renders them with different
    stroke/class), which parse_texts does not currently capture.
    """
    with open(path) as f:
        svg = f.read()
    texts = parse_texts(svg)
    G = 5.0  # 5mm spatial bucket to avoid O(n^2) on 800+ texts
    grid = defaultdict(list)
    for t in texts:
        for gx in range(int(t["x0"] // G), int(t["x1"] // G) + 1):
            for gy in range(int(t["y0"] // G), int(t["y1"] // G) + 1):
                grid[(gx, gy)].append(t)
    checked = set()
    violations = []
    for bucket in grid.values():
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                a, b = bucket[i], bucket[j]
                pair = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
                if pair in checked:
                    continue
                checked.add(pair)
                if peripheral_texts is not None and not (
                        a["c"] in peripheral_texts or b["c"] in peripheral_texts):
                    # scoped gate: neither side is a drafter-drawn label -> a
                    # vendor symbol-internal overlap, outside jurisdiction (DD-8)
                    continue
                ov = _overlap_area(a, b)
                if ov > THRESH * min(a["area"], b["area"]):
                    violations.append((a["c"], b["c"],
                                       round(a["x0"], 1), round(a["y0"], 1),
                                       round(ov / min(a["area"], b["area"]), 2)))
    violations.sort(key=lambda v: -v[4])
    return TextQAReport(path=path, texts=len(texts), violations=violations)


def main(argv: list[str]) -> int:
    allok = True
    for p in argv:
        rep = qa_svg_text(p)
        print(rep.summary())
        allok &= rep.ok
    print("=== SVG-TEXT QA:", "ALL PASS" if allok else "SOME FAIL", "===")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
