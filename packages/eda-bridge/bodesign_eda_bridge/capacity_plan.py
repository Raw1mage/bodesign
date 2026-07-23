"""L2.5 route capacity plan — M7 分層 pipeline 的容量預留層（design.md DD-4）。

drawmiat IDEF0 renderer 的 L2-PLAN slot_planner（idef0_renderer.py:1482-1489,
`_reserved_ports`/`_slot_table`）移植到電路原理圖。本層在 routing（L3）**之前**
決策兩件事，routing 從此只消費預算、不再邊畫邊搶空間：

1. **route 政策**（decide_route_policy）：每 net 走實線 wire 還是切 net label。
   跨 IC 多信號一律 all-label（rulebook C1）——此政策邏輯自 kicad_emit.py 的
   M6-8d cross-IC 推導**遷入**（單一事實來源，見下方 SSOT 註）。
2. **lane slot 預留**（reserve_lane_slots）：每條實線 route 在其 box-to-box gap
   內預定一條互斥 lane（pitch ≥ LANE_PITCH_MM），L3 只能消費 reserved slot。

出口斷言（design.md 出口斷言表 L2.5，DD-4）：slot 兩兩互斥、相鄰 pitch 達標、
route_policy 覆蓋全 net。任一違反 → raise CapacityPlanError（fail-fast，天條
no-silent-fallback）。

## cross-IC 政策 SSOT
「跨 IC 同對 ≥2 信號 → all-label」原實作在 kicad_emit.py:661-679。M7-2 起該決策
的**唯一權威**是本模組 decide_route_policy；kicad_emit 的呼叫點改為過渡期委派
（見 M7-3），決策邏輯只留這一份。IC 定義＝pin 數 > 2 的元件（被動件 ≤2 pin）；
一條 net「跨」一對 IC ＝其節點同時觸及該對 IC 的兩個成員。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .kicad_emit import LANE_PITCH_MM
from .pipeline import Layer, SlotTable

# IC 判定門檻：pin 數 > 此值 ＝ IC；<= 此值 ＝ 被動件/衛星件（kicad_emit 語義）。
_IC_PIN_THRESHOLD = 2


class CapacityPlanError(Exception):
    """L2.5 容量預留出口斷言違規（DD-4 fail-fast）。

    觸發情形：slot 重疊、相鄰 pitch < LANE_PITCH_MM、gap 容量不足、
    route_policy 未覆蓋全 net、同一 route 重複預留。
    語義：容量規劃是 routing 的預算來源，預算算錯會傳染下游——fail-loud 走
    RCA，不靜默降級（天條 no-silent-fallback）。
    """


@dataclass(frozen=True)
class NetConn:
    """L2.5 輸入的 net 連線視圖（對齊 kicad_emit EmitNet：name + nodes）。

    - name : net 名（route_policy 的 key）。
    - nodes: ((ref, pin), ...) 節點集合；ref 是元件參考、pin 是腳號。
    """

    name: str
    nodes: tuple


def decide_route_policy(
    nets: list[NetConn],
    pin_count: dict[str, int],
) -> dict[str, str]:
    """M7-2.1/2.2：route 數評估 + all-label/直連政策決策器（rulebook C1）。

    自 kicad_emit.py:661-679 遷入的 cross-IC 推導（唯一權威）：
    - IC ＝ pin_count[ref] > 2 的元件。
    - 對每 net，取其節點觸及的 IC 集合，列舉所有 IC 兩兩配對，每對記一次此 net。
    - 某對 IC 累積 ≥2 條 net → 該對之間**每條** net 一律 label（C1）；否則 wire。

    回傳 route_policy: {net_name: "wire" | "label"}，覆蓋輸入全 net。
    """
    # 每對 IC → 跨接它的 net 名清單（per-pair 計數，與 kicad_emit 同源語義）。
    pair_signals: dict[frozenset, list[str]] = {}
    for net in nets:
        ics = sorted({r for (r, _p) in net.nodes if pin_count.get(r, 0) > _IC_PIN_THRESHOLD})
        if len(ics) < 2:
            continue
        for i in range(len(ics)):
            for j in range(i + 1, len(ics)):
                pair_signals.setdefault(frozenset((ics[i], ics[j])), []).append(net.name)

    label_nets = {
        name
        for names in pair_signals.values()
        if len(names) >= 2
        for name in names
    }

    return {net.name: ("label" if net.name in label_nets else "wire") for net in nets}


def reserve_lane_slots(
    route_policy: dict[str, str],
    route_gap: dict[str, str],
    gap_span: dict[str, tuple[float, float]],
    *,
    reserved: dict[str, tuple[str, float]] | None = None,
    slots: dict[str, float] | None = None,
) -> tuple[dict[str, float], dict[str, tuple[str, float]]]:
    """M7-2.3/2.4：lane slot 預留 + 出口斷言。

    只有 policy=="wire" 的 route 佔 lane slot（label 不佔）。每條 wire route 依
    其所屬 box-to-box gap（route_gap[route] → gap_id）在該 gap 的可用區間
    （gap_span[gap_id] = (lo, hi)）內分到一條互斥 lane，相鄰 lane 中心距
    ≥ LANE_PITCH_MM（rulebook 引擎常數，M6-8e）。

    - reserved / slots：既有預留（過渡期或增量呼叫）；同一 route 若已在 reserved
      內再次預留 → CapacityPlanError（重複預留，M7-2.5）。
    - 出口斷言：
        * 同 gap 內 slot 兩兩互斥且相鄰 pitch ≥ LANE_PITCH_MM。
        * gap 容量不足（lane 數 × pitch 超出 span）→ CapacityPlanError。

    回傳 (slots, reserved)：
    - slots   : {slot_key -> slot_coord}；slot_key ＝ f"{gap_id}#{idx}"。
    - reserved: {route_name -> (slot_key, slot_coord)}；L3 據此消費。
    """
    slots = dict(slots) if slots is not None else {}
    reserved = dict(reserved) if reserved is not None else {}

    # 只取 wire route，按 gap 分組（label route 不佔 lane）。
    wire_by_gap: dict[str, list[str]] = {}
    for route, style in route_policy.items():
        if style != "wire":
            continue
        gap = route_gap.get(route)
        if gap is None:
            # 沒有 gap 指派的 wire route：無從預留 lane —— fail-fast（不靜默略過）。
            raise CapacityPlanError(
                f"wire route {route!r} has no box-to-box gap assignment; "
                f"cannot reserve a lane (route_gap missing entry)"
            )
        if route in reserved:
            raise CapacityPlanError(
                f"route {route!r} already has a reserved slot "
                f"{reserved[route]!r}; duplicate reservation is a fail-fast (DD-4)"
            )
        wire_by_gap.setdefault(gap, []).append(route)

    for gap, routes in wire_by_gap.items():
        if gap not in gap_span:
            raise CapacityPlanError(f"gap {gap!r} has no span in gap_span")
        lo, hi = gap_span[gap]
        span = hi - lo
        if span < 0:
            raise CapacityPlanError(f"gap {gap!r} has degenerate span {gap_span[gap]!r}")

        n = len(routes)
        # 容量：n 條 lane 需 (n-1)*pitch 的跨距（首條落在 lo）。
        needed = (n - 1) * LANE_PITCH_MM
        if needed > span + 1e-9:
            capacity = int(math.floor(span / LANE_PITCH_MM)) + 1 if span >= 0 else 0
            raise CapacityPlanError(
                f"gap {gap!r} span {span:.3f} mm holds {capacity} lane(s) at "
                f"pitch {LANE_PITCH_MM} mm but {n} wire route(s) need reserving; "
                f"capacity exceeded (DD-4 fail-fast)"
            )

        # 等距鋪 lane（deterministic：route 名排序）。
        for idx, route in enumerate(sorted(routes)):
            coord = round(lo + idx * LANE_PITCH_MM, 4)
            slot_key = f"{gap}#{idx}"
            slots[slot_key] = coord
            reserved[route] = (slot_key, coord)

    _assert_slots_exclusive(slots, gap_span)
    return slots, reserved


def _assert_slots_exclusive(
    slots: dict[str, float],
    gap_span: dict[str, tuple[float, float]],
) -> None:
    """出口斷言：同 gap 內 slot 兩兩互斥且相鄰 pitch ≥ LANE_PITCH_MM。"""
    per_gap: dict[str, list[float]] = {}
    for slot_key, coord in slots.items():
        gap = slot_key.rsplit("#", 1)[0]
        per_gap.setdefault(gap, []).append(coord)

    for gap, coords in per_gap.items():
        ordered = sorted(coords)
        for a, b in zip(ordered, ordered[1:]):
            if round(b - a, 6) < LANE_PITCH_MM:
                raise CapacityPlanError(
                    f"gap {gap!r} lanes at {a:.3f}/{b:.3f} mm violate pitch "
                    f">= {LANE_PITCH_MM} mm (slot overlap, DD-4)"
                )


def build_capacity_plan(
    nets: list[NetConn],
    pin_count: dict[str, int],
    route_gap: dict[str, str],
    gap_span: dict[str, tuple[float, float]],
) -> SlotTable:
    """L2.5 整合入口：政策決策 + lane 預留 → 凍結 SlotTable（接 pipeline）。

    出口斷言（DD-4）：route_policy 覆蓋全 net；route_gap 不得指涉未知 route。
    回傳的 SlotTable.producer_layer == Layer.L2_5（強凍結，下層唯讀）。
    """
    policy = decide_route_policy(nets, pin_count)

    # 覆蓋斷言：每 net 都有政策。
    net_names = {net.name for net in nets}
    missing = net_names - set(policy)
    if missing:
        raise CapacityPlanError(
            f"route_policy does not cover nets {sorted(missing)!r} (DD-4)"
        )
    # route_gap 不得指涉不存在的 route（避免預留幽靈 lane）。
    ghost = set(route_gap) - net_names
    if ghost:
        raise CapacityPlanError(
            f"route_gap references unknown route(s) {sorted(ghost)!r} "
            f"not present in nets (DD-4 fail-fast)"
        )

    slots, reserved = reserve_lane_slots(policy, route_gap, gap_span)

    assert policy, "route_policy empty despite non-empty nets"  # 不變式
    table = SlotTable(route_policy=policy, slots=slots, reserved=reserved)
    assert table.producer_layer is Layer.L2_5
    return table
