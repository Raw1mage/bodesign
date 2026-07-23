"""M6-8 routing QA: interior wire-crossing counter for an emitted .kicad_sch.

A "crossing" = two wire segments that intersect at a point interior to BOTH
segments (a shared endpoint is a legal junction/tap, NOT a crossing). This is the
machine metric behind the user's 03a ruling ("12+ unordered crossings"). Pure
geometry, no KiCad dependency — parses (wire (pts ...)) directly.
"""
from __future__ import annotations

import re
import sys

_WIRE_RE = re.compile(
    r"\(wire \(pts \(xy (-?[\d.]+) (-?[\d.]+)\) \(xy (-?[\d.]+) (-?[\d.]+)\)\)"
)

Seg = tuple[tuple[float, float], tuple[float, float]]


def _segments(sch_text: str) -> list[Seg]:
    out: list[Seg] = []
    for m in _WIRE_RE.finditer(sch_text):
        x1, y1, x2, y2 = map(float, m.groups())
        out.append(((x1, y1), (x2, y2)))
    return out


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _shares_endpoint(s1: Seg, s2: Seg, eps: float = 1e-6) -> bool:
    for p in s1:
        for q in s2:
            if abs(p[0] - q[0]) < eps and abs(p[1] - q[1]) < eps:
                return True
    return False


def _proper_cross(s1: Seg, s2: Seg, eps: float = 1e-9) -> bool:
    """True iff s1 and s2 cross at a point INTERIOR to both (not at an endpoint)."""
    if _shares_endpoint(s1, s2):
        return False
    a, b = s1
    c, d = s2
    d1 = _orient(c, d, a)
    d2 = _orient(c, d, b)
    d3 = _orient(a, b, c)
    d4 = _orient(a, b, d)
    # strict straddle both ways = proper interior crossing
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
       ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    return False


def count_interior_crossings(sch_text: str) -> int:
    segs = _segments(sch_text)
    n = 0
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if _proper_cross(segs[i], segs[j]):
                n += 1
    return n


# ---------------------------------------------------------------------------
# M7-4.1 增量 CrossingRegistry（L4 檢核層）
# ---------------------------------------------------------------------------
# 移植 drawmiat idef0_renderer.py:520-594 CrossingRegistry：正交線段的**增量**
# 交叉偵測。route 路徑改變時只重算「涉及該 route」的交叉，不全掃全集——這是
# L4 repair loop 能 bounded（每次修一條 route 只重算受影響交叉）的效能前提。
#
# 與上方 batch count_interior_crossings 的關係：batch 版解析 .kicad_sch 文字做
# 一次性事後統計（E2 交付機檢用）；Registry 版持有 live route 狀態供 repair
# loop 增量查詢。兩者交叉定義一致（h-seg × v-seg 內部穿越，共享端點不計），
# 但 Registry 限定正交線段（bodesign router 產出全為正交 wire，與 drawmiat 同）。

_EPS_COLINEAR = 0.01   # 判定線段水平/垂直的容差
_EPS_INTERIOR = 0.1    # 內部穿越的邊界內縮（端點接觸不算交叉）


class CrossingRegistry:
    """正交線段的增量交叉偵測器（移植 drawmiat CrossingRegistry）。

    維護所有 route 的水平/垂直線段，以 route_idx 索引。route 路徑改變時，
    只重算涉及該 route 的交叉，而非整個集合。

    用法：
        reg = CrossingRegistry()
        reg.update(route_idx, path)      # 新增或替換一條 route 的線段
        reg.remove(route_idx)            # 移除一條 route（re-route 前）
        n = reg.count()                  # 總交叉數
        n = reg.count_for(route_idx)     # 涉及某 route 的交叉數
        crossings = reg.all()            # 全部交叉記錄

    交叉定義：一條 h-seg 與一條**不同 route** 的 v-seg 在雙方內部相交
    （共享端點的 T 接是合法 junction，不算交叉）。同一 route 內的線段不互算。
    """

    def __init__(self) -> None:
        # route_idx → [{'y','x_min','x_max','tag'}]
        self._h_segs: dict[object, list[dict]] = {}
        # route_idx → [{'x','y_min','y_max','tag'}]
        self._v_segs: dict[object, list[dict]] = {}
        # [{'h_route','v_route','h_tag','v_tag','x','y'}]
        self._crossings: list[dict] = []

    def update(self, route_idx, path, tag: str = "?") -> None:
        """註冊或替換一條 route 的全部線段，並重算其交叉。"""
        self.remove(route_idx)
        h_segs: list[dict] = []
        v_segs: list[dict] = []
        for i in range(len(path) - 1):
            p1, p2 = path[i], path[i + 1]
            if abs(p1[1] - p2[1]) < _EPS_COLINEAR:  # 水平
                h_segs.append({
                    "y": p1[1], "x_min": min(p1[0], p2[0]),
                    "x_max": max(p1[0], p2[0]), "tag": tag,
                })
            elif abs(p1[0] - p2[0]) < _EPS_COLINEAR:  # 垂直
                v_segs.append({
                    "x": p1[0], "y_min": min(p1[1], p2[1]),
                    "y_max": max(p1[1], p2[1]), "tag": tag,
                })
        self._h_segs[route_idx] = h_segs
        self._v_segs[route_idx] = v_segs
        # 新 h_segs 對所有其他 route 的 v_segs
        for hs in h_segs:
            for other_ri, other_vs in self._v_segs.items():
                if other_ri == route_idx:
                    continue
                for vs in other_vs:
                    if (hs["x_min"] + _EPS_INTERIOR < vs["x"] < hs["x_max"] - _EPS_INTERIOR
                            and vs["y_min"] + _EPS_INTERIOR < hs["y"] < vs["y_max"] - _EPS_INTERIOR):
                        self._crossings.append({
                            "h_route": route_idx, "v_route": other_ri,
                            "h_tag": hs["tag"], "v_tag": vs["tag"],
                            "x": round(vs["x"], 3), "y": round(hs["y"], 3),
                        })
        # 新 v_segs 對所有其他 route 的 h_segs
        for vs in v_segs:
            for other_ri, other_hs in self._h_segs.items():
                if other_ri == route_idx:
                    continue
                for hs in other_hs:
                    if (hs["x_min"] + _EPS_INTERIOR < vs["x"] < hs["x_max"] - _EPS_INTERIOR
                            and vs["y_min"] + _EPS_INTERIOR < hs["y"] < vs["y_max"] - _EPS_INTERIOR):
                        self._crossings.append({
                            "h_route": other_ri, "v_route": route_idx,
                            "h_tag": hs["tag"], "v_tag": vs["tag"],
                            "x": round(vs["x"], 3), "y": round(hs["y"], 3),
                        })

    def remove(self, route_idx) -> None:
        """移除一條 route 的全部線段與交叉。"""
        self._h_segs.pop(route_idx, None)
        self._v_segs.pop(route_idx, None)
        self._crossings = [
            c for c in self._crossings
            if c["h_route"] != route_idx and c["v_route"] != route_idx
        ]

    def count(self) -> int:
        return len(self._crossings)

    def count_for(self, route_idx) -> int:
        return sum(
            1 for c in self._crossings
            if c["h_route"] == route_idx or c["v_route"] == route_idx
        )

    def all(self) -> list[dict]:
        return list(self._crossings)


def main(argv: list[str]) -> int:
    for path in argv[1:]:
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError as e:
            print(f"{path}\tERR\t{e}")
            continue
        print(f"{path}\t{count_interior_crossings(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
