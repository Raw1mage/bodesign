"""M7-3b-i slot 觀察層 — SlotTable 接進 render 主流程 + 觀察模式斷言（DD-11）。

零 fidelity 風險：本模組**只讀不改**。routing 幾何一行不動，只做兩件事：

1. **build_slot_observation**：把 composer clusters + emit 素材（components /
   nets / pin_count / bboxes）串成 SlotTable（l1_geometry → gap_topology →
   build_capacity_plan）。真實 9 頁資料上 gap_topology / capacity_plan 的
   fail-fast（跨 >2 box、對角非相鄰、容量不足）在**觀察期**被捕捉成
   `SlotObservation.skips` 記錄，**不中斷 render**。這不是 silent fallback：
   每一筆 skip 都帶 reason、可在報告中看到——是顯式量測。

2. **observe_wire_on_lane**：每條被接受的 drawn wire，對比「該 net 若有
   reserved slot，實際路徑主幹是否落在 lane coord 容差內」，回傳觀察記錄
   （寫 PhaseLog）。**不改任何 waypoints**。

DD-11 裁決依據：SlotTable 的建構依賴 clusters（只存在於 composer），故 clusters
經新參數流入 emit；SlotTable 在 emit 內部素材最齊處建（pin_maps→pin_count 已
就緒）。M7-3b-ii 依本層產出的作用面數據，才灰度啟用真正的 slot 幾何消費。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capacity_plan import CapacityPlanError, NetConn, build_capacity_plan
from .gap_topology import GapTopologyError, extract_gap_topology
from .l1_geometry import L1GeometryError, build_box_rects, build_net_boxes


@dataclass
class SlotObservation:
    """slot 接線的觀察結果（M7-3b-i，非驅動 gate）。

    - slot_table   : 成功建構的 SlotTable（觀察對比的預算來源）；建構前置
                     fail-fast 時為 None。
    - skips        : 觀察期捕捉的 skip 記錄（每筆 {stage, reason}）；顯式量測，
                     非 silent fallback。
    - route_gap    : net → gap_id（供作用面報告）。
    - gap_axis     : 各 gap 的走線垂直軸（"x"/"y"），wire-on-lane 對比用。
    """

    slot_table: Any = None
    skips: list[dict] = field(default_factory=list)
    route_gap: dict = field(default_factory=dict)
    gap_axis: dict = field(default_factory=dict)


def _gap_axis_of(box_lo, box_hi) -> str:
    """gap 的 lane 座標軸：水平相鄰 gap 的 lane 沿 x（span 是 y 重疊）→ "x"；
    垂直相鄰 → lane 沿 y。與 gap_topology._gap_between 的分軸一致。"""
    x_sep = box_lo.right <= box_hi.left + 1e-9 or box_hi.right <= box_lo.left + 1e-9
    return "x" if x_sep else "y"


def build_slot_observation(
    clusters: list,
    components: list,
    nets: list,
    pin_count: dict[str, int],
    bboxes: dict[str, tuple[float, float] | None],
) -> SlotObservation:
    """串 l1_geometry → gap_topology → build_capacity_plan → SlotTable（觀察模式）。

    觀察期契約（DD-11）：任一前置層 fail-fast（L1GeometryError /
    GapTopologyError / CapacityPlanError）被捕捉為 skip 記錄，回傳
    slot_table=None + 帶 reason 的 skips，**不向上拋**——讓 render 照舊完成、
    同時把「哪些 net / gap 無法規劃」量測出來。每筆 skip 顯式可見。

    clusters 空 → 回傳空觀察（向後相容，netlist 路徑不建 SlotTable）。
    """
    obs = SlotObservation()
    if not clusters or not components or not nets:
        return obs

    # L1 幾何橋接（可能 L1GeometryError：component 無所屬 cluster）。
    try:
        box_rects = build_box_rects(clusters, components, bboxes)
        net_boxes = build_net_boxes(nets, clusters)
    except L1GeometryError as e:
        obs.skips.append({"stage": "l1_geometry", "reason": str(e)})
        return obs

    by_id = {bx.box_id: bx for bx in box_rects}

    # gap 拓撲（可能 GapTopologyError：跨 >2 box / 對角非相鄰）。
    try:
        route_gap, gap_span = extract_gap_topology(box_rects, net_boxes)
    except GapTopologyError as e:
        obs.skips.append({"stage": "gap_topology", "reason": str(e)})
        return obs

    obs.route_gap = dict(route_gap)
    for gid in gap_span:
        lo_id, hi_id = gid.split("|", 1)
        if lo_id in by_id and hi_id in by_id:
            obs.gap_axis[gid] = _gap_axis_of(by_id[lo_id], by_id[hi_id])

    # L2.5 容量規劃（可能 CapacityPlanError：容量不足 / slot 重疊）。
    net_conns = [NetConn(name=n.name, nodes=tuple(n.nodes)) for n in nets]
    try:
        obs.slot_table = build_capacity_plan(net_conns, pin_count, route_gap, gap_span)
    except CapacityPlanError as e:
        obs.skips.append({"stage": "capacity_plan", "reason": str(e)})
        obs.slot_table = None

    return obs


def observe_wire_on_lane(
    net_name: str,
    waypoints: list[tuple[float, float]],
    reserved: dict[str, tuple[str, float]] | None,
    *,
    gap_axis: str = "x",
    tol: float = 0.5,
) -> dict:
    """觀察一條 drawn wire 是否落在其 reserved lane coord 容差內（不改幾何）。

    - reserved[net_name] = (slot_key, lane_coord)。無此 net → has_slot=False。
    - gap_axis="x"：lane 是垂直線 x==lane_coord，檢查有無 waypoint 的 x 落在
      [lane_coord ± tol]（wire 主幹的某一直段跑在該 lane 上）。"y" 對稱。

    回傳觀察記錄（供 PhaseLog）：
      {net, has_slot, hit, lane_coord, gap, axis, nearest_delta}
    """
    rec: dict = {"net": net_name, "has_slot": False, "hit": False}
    if not reserved or net_name not in reserved:
        return rec

    slot_key, lane_coord = reserved[net_name]
    rec.update(has_slot=True, lane_coord=lane_coord, gap=slot_key, axis=gap_axis)

    idx = 0 if gap_axis == "x" else 1
    coords = [pt[idx] for pt in waypoints]
    if not coords:
        rec["nearest_delta"] = None
        return rec

    nearest_delta = min(abs(c - lane_coord) for c in coords)
    rec["nearest_delta"] = round(nearest_delta, 4)
    rec["hit"] = nearest_delta <= tol
    return rec
