"""M7-2.7 L1 幾何橋接層 — DD-10 方案：slot 消費的缺失生產者。

DD-10 斷層 2 實證：composer ComposeResult 給 clusters（cluster_id/members）與
emit components（含 sheet 座標），但無 BoxRect + net_boxes 生產者——gap_topology
/ capacity_plan 因此是孤島。本模組把 L1 placement 結果橋接成 gap_topology 能吃的
兩件事：

1. **build_box_rects**：每個 cluster 一個 box，bbox = 成員 component 的 AABB
   （component.x/y ± bbox/2 聚合）。
2. **build_net_boxes**：每 net → 端點元件所屬 box id 集合（跨 box net 觸兩 box）。

## y 軸語義（DD-10 斷層 1 更正）
讀碼實證（M7-2.7）：composer `_macro_compact` shelf-packing 產 top-left 座標、
`y += shelf_h`（composer.py:786 向下增長）→ resolved component.y 是 KiCad sheet
座標、**y 向下**。gap_topology.BoxRect 假設也是 y 向下（gap_topology.py:23）。
**兩者同向**——DD-10 斷層 1 假設「y 相反」是誤判：kicad_emit._pin_abs 的
`component.y - endpoint[1]`（kicad_emit.py:693）翻的是 symbol-**local** 端點
（local y-up → sheet y-down），與 component.y 本身方向無關。

因此 sheet→box 的 y adapter 是**恆等映射**。仍集中在單一函式 sheet_y_to_box_y
並以測試鎖定（test_l1_geometry TestYAxisSemanticLock），若未來 composer 座標
語義變動，adapter 是唯一改動點、測試會先紅。

出口斷言（DD-10 fail-fast，天條 no-silent-fallback）：
- component 不屬任何 cluster → L1GeometryError 列 ref（box bbox 會漏算）。
- net 端點 ref 不屬任何 cluster → L1GeometryError 列 ref（net_boxes 會漏 box）。
"""

from __future__ import annotations

from .composer import BBOX_MARGIN_MM, Cluster
from .gap_topology import BoxRect
from .kicad_emit import EmitComponent, EmitNet
from .pipeline import BoxGeometry, Layer


class L1GeometryError(Exception):
    """L1 幾何橋接出口斷言違規（DD-10 fail-fast）。

    觸發：component / net 端點 ref 找不到所屬 cluster（box 歸屬缺漏）。
    語義：box geometry 是 gap 拓撲與 slot 預留的根輸入，歸屬漏算會讓下游
    silently 少一個 box——fail-loud 走 RCA，不靜默略過（天條 no-silent-fallback）。
    """


def sheet_y_to_box_y(sheet_y: float) -> float:
    """composer sheet 座標 y → gap_topology BoxRect y（DD-10 斷層 1 更正）。

    讀碼實證兩系皆 y 向下（見模組 docstring），故為**恆等映射**。單獨成函式
    是為了：(a) 讓 y 軸語義有唯一權威落點；(b) 測試鎖定「同向」契約，未來
    composer 若改座標語義，此處是唯一改動點、TestYAxisSemanticLock 先紅。
    """
    return sheet_y


def _cluster_of(ref: str, member_to_box: dict[str, str], what: str) -> str:
    box = member_to_box.get(ref)
    if box is None:
        raise L1GeometryError(
            f"{what} {ref!r} belongs to no cluster; cannot assign a box "
            f"(L1 geometry gap, DD-10 fail-fast, no-silent-fallback)"
        )
    return box


def _member_to_box(clusters: list[Cluster]) -> dict[str, str]:
    """{component ref -> cluster_id}；一個 ref 落多 cluster 視為輸入 bug fail-fast。"""
    mapping: dict[str, str] = {}
    for cl in clusters:
        for ref in cl.members:
            if ref in mapping and mapping[ref] != cl.cluster_id:
                raise L1GeometryError(
                    f"component {ref!r} appears in multiple clusters "
                    f"({mapping[ref]!r}, {cl.cluster_id!r}); box assignment ambiguous"
                )
            mapping[ref] = cl.cluster_id
    return mapping


def build_box_rects(
    clusters: list[Cluster],
    components: list[EmitComponent],
    bboxes: dict[str, tuple[float, float] | None],
) -> list[BoxRect]:
    """每 cluster 一個 BoxRect，bbox = 成員 component 的 AABB（sheet→box y 恆等）。

    參數：
    - clusters  : composer ComposeResult.clusters（cluster_id + members）。
    - components: emit 後的 EmitComponent 清單（含 resolved sheet 座標 x/y）。
    - bboxes    : {ref -> (w, h)}；component symbol bbox（composer `_cbb` 同源，
                  缺項用 2*BBOX_MARGIN_MM 保守值，與 composer.py:1203 一致）。

    每 component 以 (x ± w/2, y ± h/2) 貢獻一個 AABB；cluster 的 box 是成員
    AABB 的聯集。回傳的 BoxRect 用左上角原點 y 向下（x=left, y=top, w, h）。

    出口斷言：每 component 必屬某 cluster（否則 box bbox 漏算）→ fail-fast。
    """
    member_to_box = _member_to_box(clusters)

    def _bb(ref: str) -> tuple[float, float]:
        wh = bboxes.get(ref)
        if wh is None:
            return (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)
        return wh

    # 每 box 聚合成員 AABB：left/top 取 min，right/bottom 取 max。
    acc: dict[str, tuple[float, float, float, float]] = {}  # box_id -> (l, t, r, b)
    for c in components:
        box = _cluster_of(c.ref, member_to_box, "component")
        w, h = _bb(c.ref)
        by = sheet_y_to_box_y(c.y)
        l, t, r, b = c.x - w / 2, by - h / 2, c.x + w / 2, by + h / 2
        if box in acc:
            pl, pt, pr, pb = acc[box]
            acc[box] = (min(pl, l), min(pt, t), max(pr, r), max(pb, b))
        else:
            acc[box] = (l, t, r, b)

    rects: list[BoxRect] = []
    for box_id in sorted(acc):  # deterministic
        l, t, r, b = acc[box_id]
        rects.append(
            BoxRect(box_id=box_id, x=round(l, 4), y=round(t, 4),
                    w=round(r - l, 4), h=round(b - t, 4))
        )
    return rects


def build_net_boxes(
    nets: list[EmitNet],
    clusters: list[Cluster],
) -> dict[str, frozenset]:
    """每 net → 端點元件所屬 box id 集合（gap_topology.net_boxes 契約）。

    跨 box net 觸兩 box（→ gap 路由）；單 box net（衛星件內部）觸一 box。
    出口斷言：每 net 端點 ref 必屬某 cluster → fail-fast 列 ref。
    """
    member_to_box = _member_to_box(clusters)
    out: dict[str, frozenset] = {}
    for net in nets:
        boxes = {
            _cluster_of(ref, member_to_box, "net endpoint")
            for (ref, _pin) in net.nodes
        }
        out[net.name] = frozenset(boxes)
    return out


def build_box_geometry(
    clusters: list[Cluster],
    components: list[EmitComponent],
    bboxes: dict[str, tuple[float, float] | None],
    sheet: object = None,
) -> BoxGeometry:
    """M7-2.7.2：組裝凍結 L1 BoxGeometry（pipeline.py 契約填實）。

    把 build_box_rects 產出的 BoxRect 裝入凍結 BoxGeometry.boxes（原為空 tuple
    骨架），producer_layer==L1。這是 L1 stage 的正式輸出物，下游 L2/L2.5
    透過 gap_topology 消費其 boxes（唯讀，DD-5 強凍結）。

    sheet：SheetChoice + ink density（composer SheetFit）；本橋接層不改 sizer
    決策，原樣帶入供 L1 契約完整。
    """
    rects = build_box_rects(clusters, components, bboxes)
    geom = BoxGeometry(boxes=tuple(rects), sheet=sheet)
    assert geom.producer_layer is Layer.L1  # 不變式
    return geom
