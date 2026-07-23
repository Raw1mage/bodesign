"""M7-5.1/5.2/5.4 TDD — L5 等距平衡層（gap-local interval packing）。

先紅後綠：本檔在 l5_balance 落地前應 fail。

L5 職責（design.md 分層表 L5 行 / 出口斷言）：
- 輸入 validated routes（L4 產物視圖），輸出 balanced geometry（只平移 lane 座標）。
- gap-local interval packing：同 gap 內平行 wire 段的 lane 位置重分佈
  （pitch ≥ LANE_PITCH_MM、離 IC body ≥ ic_keepout_band）。
- validate-and-revert：重分佈後若新增 hard violation（碰撞/交叉）→ per-gap 回退。
- 出口斷言：topology hash 不變（wire 端點集合前後一致）+ pitch 達標。
- **預設不啟用**（旗標控制）：現行 render 路徑行為不變。
"""
from __future__ import annotations

import unittest

from bodesign_eda_bridge.l5_balance import (
    L5Balancer,
    LaneSegment,
    TopologyChanged,
    topology_hash,
)
from bodesign_eda_bridge.pipeline import BalancedGeometry, Layer


def _seg(seg_id, gap_id, axis, lane, lo, hi, endpoints):
    return LaneSegment(
        seg_id=seg_id, gap_id=gap_id, axis=axis, lane=lane, lo=lo, hi=hi,
        endpoints=tuple(endpoints),
    )


class TestTopologyHash(unittest.TestCase):
    def test_hash_stable_under_lane_shift(self):
        # 端點集合不變 → hash 不變（lane 平移只改中段座標，不改連接端點）。
        segs = [_seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("B", "2")])]
        h1 = topology_hash(segs)
        moved = [_seg("s1", "g1", "v", 5.0, 10.0, 20.0, [("A", "1"), ("B", "2")])]
        self.assertEqual(h1, topology_hash(moved))

    def test_hash_changes_when_endpoints_change(self):
        segs = [_seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("B", "2")])]
        diff = [_seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("C", "3")])]
        self.assertNotEqual(topology_hash(segs), topology_hash(diff))


class TestL5DefaultOff(unittest.TestCase):
    def test_disabled_by_default_is_identity(self):
        # 預設關：輸入原樣返回（現行 render 行為不變）。
        segs = [
            _seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("B", "2")]),
            _seg("s2", "g1", "v", 1.0, 10.0, 20.0, [("C", "1"), ("D", "2")]),
        ]
        bal = L5Balancer()  # balance_enabled 預設 False
        out = bal.balance(segs)
        self.assertIsInstance(out, BalancedGeometry)
        self.assertIs(out.producer_layer, Layer.L5)
        # 座標一字不動
        self.assertEqual([s.lane for s in out.wires], [0.0, 1.0])


class TestL5PackingEnabled(unittest.TestCase):
    def test_packing_enforces_min_pitch(self):
        # 兩條同 gap 平行 v 段擠在 1mm（< LANE_PITCH_MM 2.54）→ 啟用後撐開到 ≥ pitch。
        segs = [
            _seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("B", "2")]),
            _seg("s2", "g1", "v", 1.0, 10.0, 20.0, [("C", "1"), ("D", "2")]),
        ]
        bal = L5Balancer(balance_enabled=True)
        out = bal.balance(segs)
        lanes = sorted(s.lane for s in out.wires)
        self.assertGreaterEqual(lanes[1] - lanes[0], 2.54 - 1e-6)

    def test_topology_hash_preserved_after_packing(self):
        segs = [
            _seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("B", "2")]),
            _seg("s2", "g1", "v", 1.0, 10.0, 20.0, [("C", "1"), ("D", "2")]),
        ]
        before = topology_hash(segs)
        bal = L5Balancer(balance_enabled=True)
        out = bal.balance(segs)
        self.assertEqual(before, topology_hash(out.wires))

    def test_single_lane_gap_unchanged(self):
        # 單 lane gap 無平行鄰居 → packing 不動它。
        segs = [_seg("s1", "g1", "v", 3.3, 10.0, 20.0, [("A", "1"), ("B", "2")])]
        bal = L5Balancer(balance_enabled=True)
        out = bal.balance(segs)
        self.assertAlmostEqual(out.wires[0].lane, 3.3)


class TestL5ValidateRevert(unittest.TestCase):
    def test_revert_on_keepout_violation(self):
        # 若 packing 後某 lane 落進 IC keepout band → per-gap 回退該 gap 原座標。
        segs = [
            _seg("s1", "g1", "v", 0.0, 10.0, 20.0, [("A", "1"), ("B", "2")]),
            _seg("s2", "g1", "v", 1.0, 10.0, 20.0, [("C", "1"), ("D", "2")]),
        ]
        # keepout 覆蓋整個可分佈範圍 → 撐開必侵入 → 回退
        keepout = {"g1": [(-100.0, 0.0, 100.0, 100.0)]}
        bal = L5Balancer(balance_enabled=True, gap_keepout=keepout)
        out = bal.balance(segs)
        # 回退：原座標保留
        self.assertEqual(sorted(s.lane for s in out.wires), [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
