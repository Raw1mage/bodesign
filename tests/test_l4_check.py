"""M7-4.2/4.3/4.4 TDD — L4 檢核器（rulebook B 章集中）+ bounded repair loop。

先紅後綠：本檔在 l4_check 落地前應 fail。

L4 職責（design.md 分層表 L4 行 / 出口斷言）：
- 輸入 routed wires（+ 選配 same-IC 分組），輸出 ViolationReport。
- 機檢斷言集中：B1 wire-vs-wire 不交叉、B3 同 IC pin 走線不自交。
- bounded repair loop：violation → 小範圍修復 → 重掃；pass 上限 fail-fast（DD-7）。
- **預設不啟用 repair**（旗標控制）：現行 render 路徑行為不變。
"""
from __future__ import annotations

import unittest

from bodesign_eda_bridge.l4_check import (
    L4Checker,
    RepairBudgetExceeded,
    ViolationReport,
    WireRoute,
)


def _h(route_id, y, x0, x1, ic=None):
    return WireRoute(route_id=route_id, path=[(x0, y), (x1, y)], owner_ic=ic)


def _v(route_id, x, y0, y1, ic=None):
    return WireRoute(route_id=route_id, path=[(x, y0), (x, y1)], owner_ic=ic)


class TestL4CheckViolations(unittest.TestCase):
    def test_clean_routes_no_violation(self):
        wires = [_h("w0", 5, 0, 10), _h("w1", 20, 0, 10)]
        report = L4Checker().check(wires)
        self.assertEqual(report.count(), 0)
        self.assertTrue(report.ok())

    def test_wire_cross_violation_b1(self):
        # 十字交叉 → B1 違規
        wires = [_h("w0", 5, 0, 10), _v("w1", 5, 0, 10)]
        report = L4Checker().check(wires)
        self.assertGreaterEqual(report.count(), 1)
        self.assertFalse(report.ok())
        rule_ids = {v["rule_id"] for v in report.violations}
        self.assertIn("B1", rule_ids)

    def test_same_ic_self_cross_violation_b3(self):
        # 同一 IC 的兩條 pin 走線交叉 → B3 違規
        wires = [_h("w0", 5, 0, 10, ic="U1"), _v("w1", 5, 0, 10, ic="U1")]
        report = L4Checker().check(wires)
        rule_ids = {v["rule_id"] for v in report.violations}
        self.assertIn("B3", rule_ids)

    def test_rule_id_carries_layer(self):
        wires = [_h("w0", 5, 0, 10), _v("w1", 5, 0, 10)]
        report = L4Checker().check(wires)
        for v in report.violations:
            # rule_id 含 L# 歸屬（design.md DD-1 規則收件人制度）
            self.assertIn("layer", v)
            self.assertEqual(v["layer"], "L3")  # B 章歸 routing/L3


class TestL4RepairLoop(unittest.TestCase):
    def test_repair_disabled_by_default(self):
        # 預設不啟用 repair：check 只偵測不修（現行 render 路徑行為不變）
        wires = [_h("w0", 5, 0, 10), _v("w1", 5, 0, 10)]
        checker = L4Checker()
        report = checker.check(wires)
        self.assertGreaterEqual(report.count(), 1)
        self.assertEqual(report.repair_passes, 0)

    def test_repair_loop_converges(self):
        # 啟用 repair：可修復的 violation 收斂到 0
        wires = [_h("w0", 5, 0, 10), _v("w1", 5, 0, 10)]

        def _mock_repair(wire, report):
            # 把垂直線移開消除交叉
            if wire.route_id == "w1":
                return WireRoute(route_id="w1", path=[(50, 0), (50, 10)], owner_ic=wire.owner_ic)
            return wire

        checker = L4Checker(repair_enabled=True, max_passes=3, repair_fn=_mock_repair)
        report = checker.check(wires)
        self.assertEqual(report.count(), 0)
        self.assertGreaterEqual(report.repair_passes, 1)

    def test_repair_pass_limit_fail_fast(self):
        # repair 無效（no-op）→ 達 pass 上限 fail-fast（DD-7）
        wires = [_h("w0", 5, 0, 10), _v("w1", 5, 0, 10)]

        def _noop_repair(wire, report):
            return wire  # 永遠修不好

        checker = L4Checker(repair_enabled=True, max_passes=3, repair_fn=_noop_repair)
        with self.assertRaises(RepairBudgetExceeded) as ctx:
            checker.check(wires)
        # 診斷報告帶 pass 數與殘留 violation
        self.assertEqual(ctx.exception.repair_passes, 3)
        self.assertGreaterEqual(len(ctx.exception.violations), 1)


if __name__ == "__main__":
    unittest.main()
