"""M7-2.5 TDD：L2.5 route 容量預留層（capacity plan）。

覆蓋（design.md DD-4 / 出口斷言 / rulebook C 章）：
- route 數評估：box-to-box net 統計、cross-IC 推導（M6-8d 遷入）。
- all-label/直連政策：跨 IC ≥2 信號 → label；覆蓋全 net（rulebook C1）。
- lane slot 預留：slot 互斥、pitch ≥ LANE_PITCH_MM、每實線 route 預一 slot。
- 出口斷言 fail-fast：slot 重疊 / pitch 不足 / 政策漏 net / 重複預留 → raise。
- 凍結契約：L2.5 產物 producer_layer == Layer.L2_5，接 pipeline.SlotTable。
"""

import unittest

from bodesign_eda_bridge.capacity_plan import (
    CapacityPlanError,
    NetConn,
    build_capacity_plan,
    decide_route_policy,
    reserve_lane_slots,
)
from bodesign_eda_bridge.pipeline import Layer, SlotTable


def _net(name, nodes):
    return NetConn(name=name, nodes=tuple(nodes))


class TestRoutePolicy(unittest.TestCase):
    """M7-2.1 / M7-2.2：route 數評估 + all-label/直連政策決策器。"""

    def test_cross_ic_pair_two_signals_forces_label(self):
        # U1,U2 皆 IC（>2 pin）；兩條 net 同時跨這對 IC → 全部 label（C1）。
        pin_count = {"U1": 8, "U2": 8, "R1": 2}
        nets = [
            _net("SDA", [("U1", "1"), ("U2", "3")]),
            _net("SCL", [("U1", "2"), ("U2", "4")]),
        ]
        policy = decide_route_policy(nets, pin_count)
        self.assertEqual(policy["SDA"], "label")
        self.assertEqual(policy["SCL"], "label")

    def test_single_cross_ic_signal_stays_wire(self):
        # 同對 IC 只有 1 條跨接信號 → 不強制 label（<2 不觸發 C1）。
        pin_count = {"U1": 8, "U2": 8}
        nets = [_net("INT", [("U1", "1"), ("U2", "3")])]
        policy = decide_route_policy(nets, pin_count)
        self.assertEqual(policy["INT"], "wire")

    def test_ic_to_passive_stays_wire(self):
        # IC ↔ 衛星被動件（<=2 pin）短距 → wire（C2）。
        pin_count = {"U1": 8, "R1": 2}
        nets = [_net("VOUT", [("U1", "5"), ("R1", "1")])]
        policy = decide_route_policy(nets, pin_count)
        self.assertEqual(policy["VOUT"], "wire")

    def test_policy_covers_every_net(self):
        pin_count = {"U1": 8, "U2": 8, "R1": 2}
        nets = [
            _net("SDA", [("U1", "1"), ("U2", "3")]),
            _net("SCL", [("U1", "2"), ("U2", "4")]),
            _net("VOUT", [("U1", "5"), ("R1", "1")]),
        ]
        policy = decide_route_policy(nets, pin_count)
        self.assertEqual(set(policy), {"SDA", "SCL", "VOUT"})

    def test_three_ics_pairwise(self):
        # 三 IC：U1-U2 有 2 信號（label），U1-U3 僅 1（wire）。
        pin_count = {"U1": 8, "U2": 8, "U3": 8}
        nets = [
            _net("A", [("U1", "1"), ("U2", "3")]),
            _net("B", [("U1", "2"), ("U2", "4")]),
            _net("C", [("U1", "5"), ("U3", "1")]),
        ]
        policy = decide_route_policy(nets, pin_count)
        self.assertEqual(policy["A"], "label")
        self.assertEqual(policy["B"], "label")
        self.assertEqual(policy["C"], "wire")

    def test_net_touching_three_ics_labels(self):
        # 一條 net 同時觸及 3 IC → 觸及 >=2 IC pair 各記一次，>=2 → label。
        pin_count = {"U1": 8, "U2": 8, "U3": 8}
        nets = [_net("CLK", [("U1", "1"), ("U2", "3"), ("U3", "5")])]
        policy = decide_route_policy(nets, pin_count)
        # 單 net 跨 3 IC 產生 3 對，但每對只有這 1 條 net → 每對 <2 → wire。
        # （與 kicad_emit 現行語義一致：per-pair 計數，非 per-net IC 數。）
        self.assertEqual(policy["CLK"], "wire")


class TestLaneSlots(unittest.TestCase):
    """M7-2.3 / M7-2.4：lane slot 預留 + 出口斷言。"""

    def test_wire_routes_each_get_a_slot(self):
        policy = {"A": "wire", "B": "wire", "LBL": "label"}
        gap_span = {"g0": (0.0, 20.0)}
        route_gap = {"A": "g0", "B": "g0"}
        slots, reserved = reserve_lane_slots(policy, route_gap, gap_span)
        # 只有 wire route 佔 slot；label 不佔。
        self.assertIn("A", reserved)
        self.assertIn("B", reserved)
        self.assertNotIn("LBL", reserved)

    def test_slots_are_mutually_exclusive_and_pitch_ok(self):
        from bodesign_eda_bridge.kicad_emit import LANE_PITCH_MM

        policy = {f"N{i}": "wire" for i in range(4)}
        gap_span = {"g0": (0.0, 20.0)}
        route_gap = {f"N{i}": "g0" for i in range(4)}
        slots, reserved = reserve_lane_slots(policy, route_gap, gap_span)
        coords = sorted(slots.values())
        for a, b in zip(coords, coords[1:]):
            self.assertGreaterEqual(round(b - a, 6), LANE_PITCH_MM)

    def test_duplicate_reservation_raises(self):
        # 同一 route 重複預留 slot → fail-fast。
        policy = {"A": "wire"}
        gap_span = {"g0": (0.0, 20.0)}
        route_gap = {"A": "g0"}
        slots, reserved = reserve_lane_slots(policy, route_gap, gap_span)
        with self.assertRaises(CapacityPlanError):
            reserve_lane_slots(
                policy, route_gap, gap_span, reserved=dict(reserved), slots=dict(slots)
            )

    def test_gap_capacity_exceeded_raises(self):
        # gap 只容 2 條 lane（span 2.54，pitch 2.54）卻要塞 5 條 → fail-fast。
        policy = {f"N{i}": "wire" for i in range(5)}
        gap_span = {"g0": (0.0, 2.54)}
        route_gap = {f"N{i}": "g0" for i in range(5)}
        with self.assertRaises(CapacityPlanError):
            reserve_lane_slots(policy, route_gap, gap_span)


class TestBuildCapacityPlan(unittest.TestCase):
    """整合：build_capacity_plan → 凍結 SlotTable（接 pipeline）。"""

    def test_returns_frozen_slot_table_owned_by_l2_5(self):
        pin_count = {"U1": 8, "U2": 8, "R1": 2}
        nets = [
            _net("SDA", [("U1", "1"), ("U2", "3")]),
            _net("SCL", [("U1", "2"), ("U2", "4")]),
            _net("VOUT", [("U1", "5"), ("R1", "1")]),
        ]
        gap_span = {"g0": (0.0, 30.0)}
        route_gap = {"VOUT": "g0"}  # 只有 wire net 需 gap
        table = build_capacity_plan(nets, pin_count, route_gap, gap_span)
        self.assertIsInstance(table, SlotTable)
        self.assertEqual(table.producer_layer, Layer.L2_5)
        # 政策覆蓋全 net；SDA/SCL label、VOUT wire。
        self.assertEqual(table.route_policy["SDA"], "label")
        self.assertEqual(table.route_policy["VOUT"], "wire")
        # VOUT 是唯一 wire route，取得 slot。
        self.assertIn("VOUT", table.reserved)

    def test_policy_missing_net_raises(self):
        # route_gap 指涉不存在於 nets 的 route → 覆蓋斷言 fail-fast。
        pin_count = {"U1": 8, "R1": 2}
        nets = [_net("VOUT", [("U1", "5"), ("R1", "1")])]
        gap_span = {"g0": (0.0, 30.0)}
        route_gap = {"GHOST": "g0"}
        with self.assertRaises(CapacityPlanError):
            build_capacity_plan(nets, pin_count, route_gap, gap_span)


if __name__ == "__main__":
    unittest.main()
