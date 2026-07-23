"""L5 spacing balance — M7 分層 pipeline 的等距平衡層（design.md DD-5）。

drawmiat IDEF0 renderer 的 L5 compaction（specs/architecture.md:84-132：
grouping→remapping→compaction→refitting、spacing 公式 N lane→(N+1)×2U、
per-gap validate-and-revert）移植到電路原理圖。

職責（單一）：
- 輸入 validated routes（L4 產物視圖，本層以 LaneSegment 表達可平移的 lane 段）。
- gap-local interval packing：同 gap 內平行 wire 段的 lane 座標重分佈，使相鄰
  lane pitch ≥ LANE_PITCH_MM（2.54mm，一整行字高），離 IC body ≥ keepout band。
- validate-and-revert：重分佈後若新增 hard violation（落進 keepout band）→
  per-gap 回退該 gap 不動（不擴散、不全圖回退）。
- 輸出 BalancedGeometry（producer_layer=L5）：**只平移 lane 座標，不改 topology**。

出口斷言（design.md 出口斷言表 L5，DD-5）：
- topology hash 不變（wire 端點集合前後一致）。
- pitch 達標（未被 revert 的 gap 內相鄰 lane ≥ LANE_PITCH_MM）。

**預設不啟用**（balance_enabled=False）：現行 render 路徑行為不變（byte-identical）；
啟用時機留待 M7-7 重產時統一驗證（對齊 M7-4 repair loop 旗標化紀律）。

天條（no-silent-fallback）：topology 若被改動（端點集合變）→ raise TopologyChanged，
不靜默容忍（L5 只准平移，改連接關係＝實作 bug）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from .pipeline import BalancedGeometry, Layer

# L5 移植 kicad_emit 的 lane discipline 常數（design.md 分層表 L5 現有程式歸位）。
# 單一權威仍是 kicad_emit.LANE_PITCH_MM；此處 import 以免重複定義漂移。
from .kicad_emit import LANE_PITCH_MM, ic_keepout_band


class TopologyChanged(Exception):
    """L5 出口斷言違規：平移後 wire 端點集合改變（DD-5 fail-fast）。

    語義：L5 只准平移 lane 中段座標，端點（電氣連接點）必須逐字不變。
    端點集合 hash 前後不一致＝L5 越權改了 topology，是實作 bug，fail-loud
    走 RCA，不靜默容忍（天條 no-silent-fallback）。
    """


@dataclass(frozen=True)
class LaneSegment:
    """一條可平移的 lane 段（L5 的工作單位）。

    - seg_id     : 唯一識別。
    - gap_id     : 所屬 box-to-box gap（packing 以 gap 為單位分組）。
    - axis       : "v"（垂直段，lane 沿 x 平移）或 "h"（水平段，lane 沿 y 平移）。
    - lane       : 可平移的橫向座標（v 段＝x，h 段＝y）。packing 只改這個值。
    - lo, hi     : 段沿主軸的跨距（v 段＝y 跨距，h 段＝x 跨距）。判平行重疊用。
    - endpoints  : ((ref, pin), ...) 電氣端點識別；topology hash 的唯一輸入，
                   平移不得改動它。
    """

    seg_id: str
    gap_id: str
    axis: str
    lane: float
    lo: float
    hi: float
    endpoints: tuple = ()


def topology_hash(segments: list[LaneSegment]) -> str:
    """wire 端點集合的穩定 hash（L5 出口斷言用）。

    只吃 (seg_id, endpoints)——**不吃 lane 座標**，故 lane 平移不改 hash；
    端點（電氣連接）改變才改 hash。順序無關（sorted），避免重排造成假差異。
    """
    items = sorted(
        (s.seg_id, tuple(s.endpoints)) for s in segments
    )
    payload = repr(items).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _segments_parallel_overlap(a: LaneSegment, b: LaneSegment) -> bool:
    """兩段是否同軸且主軸跨距有真重疊（→ 需分開 lane，pitch 相關）。"""
    if a.axis != b.axis:
        return False
    return a.lo < b.hi and b.lo < a.hi


def _seg_lane_box(seg: LaneSegment, pitch: float) -> tuple[float, float, float, float]:
    """lane 段以 pitch 寬度的細矩形表達（keepout 侵入判定用）。

    v 段：x∈[lane-半pitch, lane+半pitch]、y∈[lo,hi]。
    h 段：y∈[lane-半pitch, lane+半pitch]、x∈[lo,hi]。
    """
    half = pitch / 2.0
    if seg.axis == "v":
        return (seg.lane - half, seg.lo, seg.lane + half, seg.hi)
    return (seg.lo, seg.lane - half, seg.hi, seg.lane + half)


def _box_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """半開區間 AABB 相交（邊緣相接不算）。"""
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


class L5Balancer:
    """L5 等距平衡器：gap-local interval packing + validate-and-revert。

    balance_enabled=False（預設）：balance() 原樣返回輸入（現行 render 行為不變）。
    balance_enabled=True：對每個 gap 做 interval packing 撐開至 pitch，撐開後若
    侵入該 gap 的 keepout band → per-gap 回退。
    """

    def __init__(
        self,
        balance_enabled: bool = False,
        pitch: float = LANE_PITCH_MM,
        gap_keepout: dict[str, list[tuple[float, float, float, float]]] | None = None,
    ) -> None:
        self.balance_enabled = balance_enabled
        self.pitch = pitch
        self.gap_keepout = gap_keepout or {}

    def balance(self, segments: list[LaneSegment]) -> BalancedGeometry:
        """對 lane 段做等距平衡；回傳凍結 BalancedGeometry（接 pipeline）。

        預設關：原樣返回（byte-identical）。開：per-gap packing + validate-revert，
        並斷言 topology hash 不變。
        """
        before_hash = topology_hash(segments)

        if not self.balance_enabled:
            result = list(segments)
        else:
            result = self._pack_all_gaps(segments)

        after_hash = topology_hash(result)
        if before_hash != after_hash:
            raise TopologyChanged(
                "L5 balance changed wire endpoint set (topology hash mismatch); "
                "L5 may only translate lane coordinates, not alter connectivity "
                "(DD-5 fail-fast)"
            )

        return BalancedGeometry(wires=tuple(result))

    def _pack_all_gaps(self, segments: list[LaneSegment]) -> list[LaneSegment]:
        """對每個 gap 獨立 packing；per-gap validate-and-revert。"""
        by_gap: dict[str, list[LaneSegment]] = {}
        for s in segments:
            by_gap.setdefault(s.gap_id, []).append(s)

        out: list[LaneSegment] = []
        for gap_id, segs in by_gap.items():
            packed = self._pack_gap(segs)
            if self._packed_ok(gap_id, packed):
                out.extend(packed)
            else:
                out.extend(segs)  # per-gap revert：該 gap 原座標不動
        return out

    def _pack_gap(self, segs: list[LaneSegment]) -> list[LaneSegment]:
        """單 gap 內 interval packing：把兩兩平行重疊的段撐開到 ≥ pitch。

        演算法（drawmiat compaction 精神的最小落地）：對同軸、主軸跨距重疊的
        段群，依原 lane 座標排序後以固定 pitch 遞增重排。無平行鄰居的段不動。
        """
        # 分成「有平行重疊鄰居」與「孤立」兩類；只重排前者。
        movable_idx: list[int] = []
        for i, a in enumerate(segs):
            if any(
                i != j and _segments_parallel_overlap(a, b)
                for j, b in enumerate(segs)
            ):
                movable_idx.append(i)

        if len(movable_idx) < 2:
            return list(segs)  # 無平行群，不動

        # 依原 lane 排序，錨定最小 lane，等距 pitch 遞增。
        ordered = sorted(movable_idx, key=lambda i: segs[i].lane)
        anchor = segs[ordered[0]].lane
        new_lane: dict[int, float] = {}
        for k, i in enumerate(ordered):
            new_lane[i] = round(anchor + k * self.pitch, 4)

        result: list[LaneSegment] = []
        for i, s in enumerate(segs):
            if i in new_lane:
                result.append(replace(s, lane=new_lane[i]))
            else:
                result.append(s)
        return result

    def _packed_ok(self, gap_id: str, packed: list[LaneSegment]) -> bool:
        """validate：packed 後無 lane 段侵入該 gap 的 keepout band。"""
        bands = self.gap_keepout.get(gap_id)
        if not bands:
            return True
        for s in packed:
            box = _seg_lane_box(s, self.pitch)
            for band in bands:
                if _box_overlap(box, band):
                    return False
        return True
