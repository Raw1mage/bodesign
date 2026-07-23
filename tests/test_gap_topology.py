"""M7-2.6 TDD：gap 拓撲抽取（gap_topology）。

覆蓋（design.md DD-9 方案 A / capacity_plan 輸入契約）：
- 從 L1 box geometry + net 端點歸屬抽 box-to-box gap 拓撲。
- 輸出 route_gap {net→gap_id} 與 gap_span {gap_id→(lo,hi)}，直餵 build_capacity_plan。
- 出口斷言 fail-fast：跨 box net 無歸屬 gap → raise 列 net 名；gap span lo<hi。
- 分軸：水平相鄰（左右）→ 走水平線、span 是 Y；垂直相鄰（上下）→ span 是 X。
- 與 build_capacity_plan 串接：gap_topology 輸出直建 SlotTable 成功。
"""

import unittest

from bodesign_eda_bridge.gap_topology import (
    BoxRect,
    GapTopologyError,
    extract_gap_topology,
)


def _box(box_id, x, y, w, h):
    """左上角 (x,y) + 寬高 → BoxRect。"""
    return BoxRect(box_id=box_id, x=x, y=y, w=w, h=h)


class TestTwoBoxHorizontal(unittest.TestCase):
    """兩 box 水平相鄰（左右）基本案：net 走中間水平 gap。"""

    def test_two_horizontally_adjacent_boxes_yield_one_gap(self):
        boxes = [_box("A", 0.0, 0.0, 10.0, 10.0), _box("B", 30.0, 0.0, 10.0, 10.0)]
        # net 從 A 連到 B（各自成員 ref 已歸屬 box）。
        net_boxes = {"N1": frozenset({"A", "B"})}
        route_gap, gap_span = extract_gap_topology(boxes, net_boxes)
        self.assertIn("N1", route_gap)
        gid = route_gap["N1"]
        self.assertIn(gid, gap_span)
        lo, hi = gap_span[gid]
        self.assertLess(lo, hi)  # span 非退化

    def test_gap_span_is_vertical_extent_for_horizontal_gap(self):
        # 水平 gap（A|B 左右）的 span 應是 Y 範圍（垂直於水平走線方向）。
        boxes = [_box("A", 0.0, 0.0, 10.0, 10.0), _box("B", 30.0, 2.0, 10.0, 6.0)]
        net_boxes = {"N1": frozenset({"A", "B"})}
        _route_gap, gap_span = extract_gap_topology(boxes, net_boxes)
        (gid,) = list(gap_span)
        lo, hi = gap_span[gid]
        # Y 重疊區間 = [max(top)=2, min(bottom)=8]。
        self.assertAlmostEqual(lo, 2.0)
        self.assertAlmostEqual(hi, 8.0)


class TestThreeBoxRow(unittest.TestCase):
    """三 box 一字排：A|B|C → 兩個 gap（A-B, B-C）。"""

    def test_three_in_a_row_two_gaps(self):
        boxes = [
            _box("A", 0.0, 0.0, 10.0, 10.0),
            _box("B", 20.0, 0.0, 10.0, 10.0),
            _box("C", 40.0, 0.0, 10.0, 10.0),
        ]
        net_boxes = {
            "AB": frozenset({"A", "B"}),
            "BC": frozenset({"B", "C"}),
        }
        route_gap, gap_span = extract_gap_topology(boxes, net_boxes)
        self.assertEqual(len(gap_span), 2)
        self.assertNotEqual(route_gap["AB"], route_gap["BC"])


class TestDiagonalNotAdjacent(unittest.TestCase):
    """對角 box 無投影重疊 → 不算相鄰 gap，跨對角 net fail-fast。"""

    def test_diagonal_net_without_gap_raises(self):
        boxes = [_box("A", 0.0, 0.0, 10.0, 10.0), _box("D", 40.0, 40.0, 10.0, 10.0)]
        net_boxes = {"AD": frozenset({"A", "D"})}
        with self.assertRaises(GapTopologyError):
            extract_gap_topology(boxes, net_boxes)


class TestNetNoGapFailFast(unittest.TestCase):
    """跨 box net 找不到歸屬 gap → fail-fast 列出 net 名。"""

    def test_unassigned_net_raises_with_name(self):
        boxes = [_box("A", 0.0, 0.0, 10.0, 10.0), _box("D", 40.0, 40.0, 10.0, 10.0)]
        net_boxes = {"ORPHAN": frozenset({"A", "D"})}
        with self.assertRaises(GapTopologyError) as ctx:
            extract_gap_topology(boxes, net_boxes)
        self.assertIn("ORPHAN", str(ctx.exception))


class TestIntraBoxNetIgnored(unittest.TestCase):
    """net 只在單一 box 內（衛星件）→ 不需 gap，不列入 route_gap。"""

    def test_single_box_net_not_in_route_gap(self):
        boxes = [_box("A", 0.0, 0.0, 10.0, 10.0), _box("B", 30.0, 0.0, 10.0, 10.0)]
        net_boxes = {
            "CROSS": frozenset({"A", "B"}),
            "LOCAL": frozenset({"A"}),
        }
        route_gap, _gap_span = extract_gap_topology(boxes, net_boxes)
        self.assertIn("CROSS", route_gap)
        self.assertNotIn("LOCAL", route_gap)


class TestVerticalAdjacency(unittest.TestCase):
    """垂直相鄰（上下）→ span 是 X 範圍（垂直於垂直走線方向）。"""

    def test_vertically_adjacent_gap_span_is_x(self):
        boxes = [_box("A", 0.0, 0.0, 10.0, 10.0), _box("B", 3.0, 30.0, 4.0, 10.0)]
        net_boxes = {"N": frozenset({"A", "B"})}
        _route_gap, gap_span = extract_gap_topology(boxes, net_boxes)
        (gid,) = list(gap_span)
        lo, hi = gap_span[gid]
        # X 重疊 = [max(left)=3, min(right)=7]。
        self.assertAlmostEqual(lo, 3.0)
        self.assertAlmostEqual(hi, 7.0)


class TestBuildCapacityPlanIntegration(unittest.TestCase):
    """串接：gap_topology 輸出直餵 build_capacity_plan 成功建 SlotTable。"""

    def test_topology_output_feeds_capacity_plan(self):
        from bodesign_eda_bridge.capacity_plan import NetConn, build_capacity_plan
        from bodesign_eda_bridge.pipeline import Layer, SlotTable

        boxes = [
            _box("U1", 0.0, 0.0, 10.0, 20.0),
            _box("U2", 40.0, 0.0, 10.0, 20.0),
        ]
        # 兩條 wire net 跨 U1-U2；pin_count 讓它們維持 wire（同對只 <2 → 這裡給 1 條 IC-IC）。
        net_boxes = {"VOUT": frozenset({"U1", "U2"})}
        route_gap, gap_span = extract_gap_topology(boxes, net_boxes)

        nets = [NetConn(name="VOUT", nodes=(("U1", "5"), ("U2", "1")))]
        pin_count = {"U1": 8, "U2": 8}  # 同對 IC 僅 1 net → wire
        table = build_capacity_plan(nets, pin_count, route_gap, gap_span)
        self.assertIsInstance(table, SlotTable)
        self.assertEqual(table.producer_layer, Layer.L2_5)
        self.assertEqual(table.route_policy["VOUT"], "wire")
        self.assertIn("VOUT", table.reserved)


if __name__ == "__main__":
    unittest.main()
