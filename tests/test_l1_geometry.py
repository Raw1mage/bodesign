"""M7-2.7 TDD：L1 幾何橋接層（l1_geometry）。

覆蓋（design.md DD-10 方案 / gap_topology 輸入契約）：
- composer ComposeResult（clusters + emit components）→ BoxRect 清單 + net_boxes。
- y 軸語義鎖定：composer resolved 座標與 gap_topology BoxRect 皆 y 向下（同向）；
  adapter 為恆等映射，但集中單一函式，以具體數字驗證上下關係在兩系一致。
- net_boxes：net 端點元件 → 所屬 box id 集合（跨 box net 觸兩 box）。
- 端到端乾跑（DD-9 方案 B 精神）：composer 真實輸出 → l1_geometry →
  gap_topology → build_capacity_plan → SlotTable 合理，不接 router。
- 出口斷言 fail-fast：component 無所屬 cluster → raise 列 ref。
"""

import unittest

from bodesign_eda_bridge.kicad_emit import EmitComponent, EmitNet
from bodesign_eda_bridge.composer import Cluster
from bodesign_eda_bridge.gap_topology import BoxRect
from bodesign_eda_bridge.l1_geometry import (
    L1GeometryError,
    build_box_rects,
    build_net_boxes,
    sheet_y_to_box_y,
)


def _comp(ref, x, y, lib_id="Device:R"):
    return EmitComponent(ref=ref, lib_id=lib_id, x=x, y=y)


class TestYAxisSemanticLock(unittest.TestCase):
    """y 軸語義鎖定：composer sheet 座標與 BoxRect 皆 y 向下（同向恆等）。

    讀碼實證（M7-2.7）：composer `_macro_compact` shelf-packing top-left
    `y += shelf_h` 向下增長 → resolved component.y = KiCad sheet y 向下；
    gap_topology.BoxRect 假設也是 y 向下（gap_topology.py:23）。兩者同向，
    adapter 恆等。DD-10 斷層1「y 相反」是誤判（_pin_abs 翻的是 symbol-local
    端點，非 component.y 本身）。本測試把「同向」鎖進契約，防未來漂移。
    """

    def test_sheet_y_to_box_y_is_identity(self):
        # 恆等映射：同一 sheet y 值直接是 box y 值。
        self.assertEqual(sheet_y_to_box_y(0.0), 0.0)
        self.assertEqual(sheet_y_to_box_y(42.5), 42.5)

    def test_larger_sheet_y_is_lower_on_page_in_both_systems(self):
        # 上下關係一致：sheet y 越大＝頁面越下，box y 越大＝越下（同向）。
        top_box = sheet_y_to_box_y(10.0)
        bottom_box = sheet_y_to_box_y(90.0)
        self.assertLess(top_box, bottom_box)  # 上方 box 的 y 較小（同 gap_topology top<bottom）


class TestBuildBoxRects(unittest.TestCase):
    """cluster 成員 component AABB → box bbox（含 pin 延伸）。"""

    def test_single_cluster_aabb(self):
        # 兩 component 在一 cluster，bbox = 成員 AABB + pin 延伸。
        comps = [_comp("R1", 10.0, 10.0), _comp("R2", 30.0, 10.0)]
        clusters = [Cluster(cluster_id="c0", source="declared", members=["R1", "R2"])]
        bboxes = {"R1": (4.0, 6.0), "R2": (4.0, 6.0)}  # (w, h)
        rects = build_box_rects(clusters, comps, bboxes)
        self.assertEqual(len(rects), 1)
        r = rects[0]
        self.assertEqual(r.box_id, "c0")
        # AABB: x from R1.x-2=8 to R2.x+2=32; y from 10-3=7 to 10+3=13.
        self.assertAlmostEqual(r.left, 8.0)
        self.assertAlmostEqual(r.right, 32.0)
        self.assertAlmostEqual(r.top, 7.0)
        self.assertAlmostEqual(r.bottom, 13.0)

    def test_two_clusters_two_boxes(self):
        comps = [_comp("U1", 0.0, 0.0), _comp("U2", 50.0, 0.0)]
        clusters = [
            Cluster(cluster_id="A", source="declared", members=["U1"]),
            Cluster(cluster_id="B", source="declared", members=["U2"]),
        ]
        bboxes = {"U1": (10.0, 20.0), "U2": (10.0, 20.0)}
        rects = build_box_rects(clusters, comps, bboxes)
        self.assertEqual({r.box_id for r in rects}, {"A", "B"})

    def test_component_without_cluster_fail_fast(self):
        # U3 不在任何 cluster → fail-fast 列 ref（no-silent-fallback）。
        comps = [_comp("U1", 0.0, 0.0), _comp("U3", 50.0, 0.0)]
        clusters = [Cluster(cluster_id="A", source="declared", members=["U1"])]
        bboxes = {"U1": (10.0, 20.0), "U3": (10.0, 20.0)}
        with self.assertRaises(L1GeometryError) as ctx:
            build_box_rects(clusters, comps, bboxes)
        self.assertIn("U3", str(ctx.exception))

    def test_returns_boxrect_instances(self):
        comps = [_comp("R1", 10.0, 10.0)]
        clusters = [Cluster(cluster_id="c0", source="declared", members=["R1"])]
        bboxes = {"R1": (4.0, 6.0)}
        rects = build_box_rects(clusters, comps, bboxes)
        self.assertIsInstance(rects[0], BoxRect)


class TestBuildNetBoxes(unittest.TestCase):
    """net 端點元件 → 所屬 box id 集合。"""

    def test_cross_box_net_touches_two_boxes(self):
        clusters = [
            Cluster(cluster_id="A", source="declared", members=["U1"]),
            Cluster(cluster_id="B", source="declared", members=["U2"]),
        ]
        nets = [EmitNet(name="VOUT", nodes=[("U1", "1"), ("U2", "3")])]
        net_boxes = build_net_boxes(nets, clusters)
        self.assertEqual(net_boxes["VOUT"], frozenset({"A", "B"}))

    def test_intra_box_net_single_box(self):
        clusters = [Cluster(cluster_id="A", source="declared", members=["U1", "R1"])]
        nets = [EmitNet(name="LOCAL", nodes=[("U1", "1"), ("R1", "2")])]
        net_boxes = build_net_boxes(nets, clusters)
        self.assertEqual(net_boxes["LOCAL"], frozenset({"A"}))

    def test_node_ref_without_cluster_fail_fast(self):
        clusters = [Cluster(cluster_id="A", source="declared", members=["U1"])]
        nets = [EmitNet(name="N", nodes=[("U1", "1"), ("GHOST", "2")])]
        with self.assertRaises(L1GeometryError) as ctx:
            build_net_boxes(nets, clusters)
        self.assertIn("GHOST", str(ctx.exception))


class TestEndToEndDryRun(unittest.TestCase):
    """端到端乾跑（DD-9 方案 B 精神）：l1_geometry → gap_topology →
    build_capacity_plan → SlotTable，證明前置鏈座標正確，不接 router。"""

    def test_chain_produces_valid_slot_table(self):
        from bodesign_eda_bridge.gap_topology import extract_gap_topology
        from bodesign_eda_bridge.capacity_plan import NetConn, build_capacity_plan
        from bodesign_eda_bridge.pipeline import Layer, SlotTable

        # 兩 box 水平相鄰（U1 左、U2 右），一條跨 box wire net。
        comps = [_comp("U1", 0.0, 0.0, "MCU:U"), _comp("U2", 60.0, 0.0, "MCU:U")]
        clusters = [
            Cluster(cluster_id="A", source="declared", members=["U1"]),
            Cluster(cluster_id="B", source="declared", members=["U2"]),
        ]
        bboxes = {"U1": (10.0, 20.0), "U2": (10.0, 20.0)}
        nets = [EmitNet(name="VOUT", nodes=[("U1", "5"), ("U2", "1")])]

        rects = build_box_rects(clusters, comps, bboxes)
        net_boxes = build_net_boxes(nets, clusters)
        route_gap, gap_span = extract_gap_topology(rects, net_boxes)

        conn = [NetConn(name="VOUT", nodes=(("U1", "5"), ("U2", "1")))]
        pin_count = {"U1": 8, "U2": 8}
        table = build_capacity_plan(conn, pin_count, route_gap, gap_span)

        self.assertIsInstance(table, SlotTable)
        self.assertEqual(table.producer_layer, Layer.L2_5)
        self.assertEqual(table.route_policy["VOUT"], "wire")
        self.assertIn("VOUT", table.reserved)


if __name__ == "__main__":
    unittest.main()
