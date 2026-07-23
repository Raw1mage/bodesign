"""M7-2.6 gap 拓撲抽取 — DD-9 方案 A：SlotTable 的缺失生產者。

capacity_plan.build_capacity_plan 吃 route_gap {net→gap_id} 與
gap_span {gap_id→(lo,hi)}，但 render 流程無模組產生這兩者——SlotTable 是孤島。
drawmiat 的 lane col 來自 grid row-gap（天生有 gap 拓撲）；bodesign box 是自由
擺放，需從幾何反推。本模組從 L1 box geometry + net 端點歸屬抽 box-to-box gap
拓撲，直接餵 build_capacity_plan。

## 相鄰判定
兩 box 之間存在「可路由 gap」的條件（分軸）：
- **水平相鄰**：X 方向不重疊（一個完全在另一個左側），且 Y 投影有重疊。
  gap 走水平線，span＝Y 重疊區間 [max(top), min(bottom)]（垂直於走線方向）。
- **垂直相鄰**：Y 方向不重疊，且 X 投影有重疊。
  gap 走垂直線，span＝X 重疊區間 [max(left), min(right)]。
對角（兩軸都不重疊）→ 無 gap。

## net → gap 歸屬
一條 net 若其端點落在恰兩個 box 上（跨 box net），指派給這兩 box 之間的 gap。
單 box net（衛星件內部）不需 gap，不列入 route_gap。跨 box 但兩 box 非相鄰
（對角、或中間隔著第三 box 無直接 gap）→ fail-fast（no-silent-fallback）。

## 座標系
座標用左上角原點、y 向下（對齊 KiCad sheet mm / composer resolved 座標語義）：
box 的 top=y、bottom=y+h、left=x、right=x+w。span 語義與 capacity_plan
reserve_lane_slots 的 gap_span 對齊（lane 座標＝span 軸上的等距分佈）。

出口斷言（DD-9 fail-fast）：每條跨 box net 都有歸屬 gap（無 → raise 列 net 名）；
每 gap span 非退化（lo < hi）。
"""

from __future__ import annotations

from dataclasses import dataclass


class GapTopologyError(Exception):
    """gap 拓撲抽取出口斷言違規（DD-9 fail-fast）。

    觸發：跨 box net 找不到相鄰 gap（對角/非相鄰）、gap span 退化。
    語義：gap 拓撲是 slot 預留的輸入，反推錯會傳染 capacity plan——fail-loud
    走 RCA，不靜默略過（天條 no-silent-fallback）。
    """


@dataclass(frozen=True)
class BoxRect:
    """L1 box geometry 的輸入視圖（box id + bbox mm，左上角原點 y 向下）。

    - box_id: 模組 box 識別。
    - x, y  : 左上角座標（mm）。
    - w, h  : 寬、高（mm）。
    """

    box_id: str
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h


def _overlap(lo_a: float, hi_a: float, lo_b: float, hi_b: float) -> tuple[float, float] | None:
    """兩個 1D 區間的重疊，無重疊（含僅端點相切）回 None。"""
    lo = max(lo_a, lo_b)
    hi = min(hi_a, hi_b)
    if hi - lo > 1e-9:
        return (lo, hi)
    return None


def _gap_between(a: BoxRect, b: BoxRect) -> tuple[float, float] | None:
    """回傳 a,b 之間的 gap span (lo, hi)（垂直於走線方向），無相鄰 gap 回 None。

    水平相鄰：X 不重疊 ∧ Y 投影重疊 → span 為 Y 重疊。
    垂直相鄰：Y 不重疊 ∧ X 投影重疊 → span 為 X 重疊。
    兩者皆成立（不可能，因 X/Y 各需一軸不重疊）取水平優先；皆不成立回 None。
    """
    x_sep = a.right <= b.left + 1e-9 or b.right <= a.left + 1e-9
    y_sep = a.bottom <= b.top + 1e-9 or b.bottom <= a.top + 1e-9

    if x_sep and not y_sep:
        # 水平相鄰：span 是 Y 重疊。
        return _overlap(a.top, a.bottom, b.top, b.bottom)
    if y_sep and not x_sep:
        # 垂直相鄰：span 是 X 重疊。
        return _overlap(a.left, a.right, b.left, b.right)
    return None


def extract_gap_topology(
    boxes: list[BoxRect],
    net_boxes: dict[str, frozenset],
) -> tuple[dict[str, str], dict[str, tuple[float, float]]]:
    """從 L1 box geometry + net→box 歸屬抽 gap 拓撲。

    參數：
    - boxes    : L1 凍結 box geometry 的視圖清單。
    - net_boxes: {net_name -> frozenset(box_id)}；net 端點觸及的 box 集合。

    回傳 (route_gap, gap_span)，可直接餵 build_capacity_plan：
    - route_gap: {net_name -> gap_id}，僅含跨恰兩 box 的 net（單 box net 略過）。
    - gap_span : {gap_id -> (lo, hi)}，僅含被至少一條 net 使用的 gap。

    gap_id 語義：f"{box_lo}|{box_hi}"（box_id 排序後以 '|' 連接，deterministic）。

    出口斷言（fail-fast）：
    - 跨 box net（|boxes|>=2）找不到相鄰 gap → GapTopologyError 列 net 名。
    - net 觸及 >2 box（無單一 gap 可承載）→ GapTopologyError 列 net 名。
    - gap span 退化（lo>=hi）→ GapTopologyError（_gap_between 已排除相切，此為防呆）。
    """
    by_id = {bx.box_id: bx for bx in boxes}

    # 預算每對相鄰 box 的 gap span（lazy：只在有 net 用到時落 gap_span）。
    def _pair_gap(id_a: str, id_b: str) -> tuple[str, tuple[float, float]]:
        lo_id, hi_id = sorted((id_a, id_b))
        gid = f"{lo_id}|{hi_id}"
        span = _gap_between(by_id[lo_id], by_id[hi_id])
        return gid, span

    route_gap: dict[str, str] = {}
    gap_span: dict[str, tuple[float, float]] = {}
    unassigned: list[str] = []

    for net_name, box_ids in net_boxes.items():
        ids = [i for i in box_ids if i in by_id]
        if len(ids) < 2:
            # 單 box net（衛星件內部）：不需 gap。
            continue
        if len(ids) > 2:
            # 跨 >2 box：單一 box-to-box gap 無法承載（本層不處理多 gap 拆分）。
            unassigned.append(net_name)
            continue

        gid, span = _pair_gap(ids[0], ids[1])
        if span is None:
            # 兩 box 非相鄰（對角）→ 無 gap。
            unassigned.append(net_name)
            continue

        lo, hi = span
        if hi - lo <= 1e-9:
            unassigned.append(net_name)
            continue

        route_gap[net_name] = gid
        gap_span[gid] = span

    if unassigned:
        raise GapTopologyError(
            f"cross-box net(s) {sorted(unassigned)!r} have no adjacent box-to-box "
            f"gap (non-adjacent/diagonal, or spanning >2 boxes); cannot assign a "
            f"routing gap (DD-9 fail-fast, no-silent-fallback)"
        )

    # 防呆：所有落帳 gap span 必須非退化。
    for gid, (lo, hi) in gap_span.items():
        if hi - lo <= 1e-9:
            raise GapTopologyError(
                f"gap {gid!r} has degenerate span ({lo}, {hi}); lo must be < hi"
            )

    return route_gap, gap_span
