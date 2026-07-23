"""M1 單元測試：OccupancyLedger（test-vectors TV-1..TV-4 + 補充）。"""

import unittest

from bodesign_eda_bridge.occupancy import (
    BudgetInfeasible,
    LedgerAssertionFailed,
    LedgerConflict,
    LedgerRect,
    OccupancyLedger,
    ReserveResult,
)


class TestLedgerRect(unittest.TestCase):
    def test_valid_rect(self):
        r = LedgerRect(10, 10, 30, 20, "U1", "body")
        self.assertEqual(r.owner, "U1")
        self.assertEqual(r.kind, "body")

    def test_degenerate_x_raises(self):
        with self.assertRaises(ValueError):
            LedgerRect(30, 10, 30, 20, "U1", "body")  # x1==x0
        with self.assertRaises(ValueError):
            LedgerRect(30, 10, 10, 20, "U1", "body")  # x1<x0

    def test_degenerate_y_raises(self):
        with self.assertRaises(ValueError):
            LedgerRect(10, 20, 30, 20, "U1", "body")  # y1==y0
        with self.assertRaises(ValueError):
            LedgerRect(10, 20, 30, 10, "U1", "body")  # y1<y0

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            LedgerRect(10, 10, 30, 20, "U1", "bogus")

    def test_all_valid_kinds(self):
        for k in ("body", "pin_extent", "stub", "label", "power", "flag", "frame_margin"):
            LedgerRect(0, 0, 1, 1, "x", k)  # no raise

    def test_overlaps_half_open(self):
        a = LedgerRect(10, 10, 30, 20, "A", "body")
        b = LedgerRect(30, 10, 50, 20, "B", "body")  # 邊緣相接
        self.assertFalse(a.overlaps(b))
        self.assertFalse(b.overlaps(a))
        c = LedgerRect(29, 10, 50, 20, "C", "body")  # 重疊 1mm
        self.assertTrue(a.overlaps(c))


class TestReserve(unittest.TestCase):
    def test_tv1_reserve_success(self):
        """TV-1：空帳本 reserve 成功，帳本含該 rect。"""
        led = OccupancyLedger()
        rect = LedgerRect(10, 10, 30, 20, "U1", "body")
        res = led.try_reserve(rect)
        self.assertTrue(res.ok)
        self.assertEqual(res.conflicts, [])
        self.assertEqual(len(led), 1)
        self.assertIn(rect, led.rects)

    def test_tv1_reserve_raising_variant(self):
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        self.assertEqual(len(led), 1)

    def test_tv2_conflict_fail_loud_try(self):
        """TV-2（try 版）：相交回 ok=False 並列衝突 owner。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        res = led.try_reserve(LedgerRect(25, 15, 45, 25, "LBL_SDIO0", "label"))
        self.assertFalse(res.ok)
        self.assertEqual([c.owner for c in res.conflicts], ["U1"])
        self.assertEqual(len(led), 1)  # 未入帳

    def test_tv2_conflict_fail_loud_raise(self):
        """TV-2（raise 版）：相交拋 LedgerConflict 附衝突矩形。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        req = LedgerRect(25, 15, 45, 25, "LBL_SDIO0", "label")
        with self.assertRaises(LedgerConflict) as ctx:
            led.reserve(req)
        exc = ctx.exception
        self.assertEqual(exc.requested, req)
        self.assertEqual([c.owner for c in exc.conflicts], ["U1"])
        self.assertEqual(len(led), 1)  # 未入帳

    def test_tv2_multi_conflict(self):
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        led.reserve(LedgerRect(40, 10, 60, 20, "U2", "body"))
        req = LedgerRect(20, 12, 50, 18, "wide", "label")
        res = led.try_reserve(req)
        self.assertFalse(res.ok)
        self.assertEqual({c.owner for c in res.conflicts}, {"U1", "U2"})

    def test_tv3_edge_touch_coexist(self):
        """TV-3：邊緣相接（x1==x0）不算衝突，可共存。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        res = led.try_reserve(LedgerRect(30, 10, 50, 20, "U2", "body"))
        self.assertTrue(res.ok)
        self.assertEqual(res.conflicts, [])
        self.assertEqual(len(led), 2)


class TestQuery(unittest.TestCase):
    def test_query_hit(self):
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        hits = led.query(LedgerRect(25, 15, 45, 25, "probe", "label"))
        self.assertEqual([h.owner for h in hits], ["U1"])

    def test_query_miss(self):
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        hits = led.query(LedgerRect(30, 10, 50, 20, "probe", "body"))  # 邊緣相接
        self.assertEqual(hits, [])


class TestDryRun(unittest.TestCase):
    def test_tv4_dry_run_no_commit(self):
        """TV-4：dry-run 副本寫入不影響本尊。"""
        led = OccupancyLedger()
        clone = led.dry_run()
        clone.reserve(LedgerRect(0, 0, 100, 100, "probe", "body"))
        self.assertEqual(len(clone), 1)
        self.assertEqual(len(led), 0)  # 本尊不受影響

    def test_dry_run_inherits_existing(self):
        led = OccupancyLedger(paper="A1")
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        clone = led.dry_run()
        self.assertEqual(len(clone), 1)
        self.assertEqual(clone.paper, "A1")
        # clone 再 reserve 相交者應衝突（繼承既有）
        res = clone.try_reserve(LedgerRect(20, 12, 40, 18, "x", "label"))
        self.assertFalse(res.ok)
        # 本尊仍只有 1 筆
        self.assertEqual(len(led), 1)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_structure(self):
        led = OccupancyLedger(paper="A0")
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        led.reserve(LedgerRect(30, 10, 50, 20, "U2", "label"))
        snap = led.snapshot()
        self.assertEqual(snap["paper"], "A0")
        self.assertEqual(snap["count"], 2)
        self.assertEqual(len(snap["rects"]), 2)
        self.assertEqual(snap["rects"][0]["owner"], "U1")
        self.assertEqual(snap["rects"][1]["kind"], "label")
        self.assertIn("x0", snap["rects"][0])

    def test_reserve_result_to_dict(self):
        res = ReserveResult(ok=False, conflicts=[LedgerRect(0, 0, 1, 1, "a", "body")])
        d = res.to_dict()
        self.assertFalse(d["ok"])
        self.assertEqual(d["conflicts"][0]["owner"], "a")


class TestExtend(unittest.TestCase):
    def test_extend_batch(self):
        led = OccupancyLedger()
        led.extend([
            LedgerRect(0, 0, 10, 10, "a", "body"),
            LedgerRect(10, 0, 20, 10, "b", "body"),
        ])
        self.assertEqual(len(led), 2)

    def test_extend_conflict_raises(self):
        led = OccupancyLedger()
        with self.assertRaises(LedgerConflict):
            led.extend([
                LedgerRect(0, 0, 10, 10, "a", "body"),
                LedgerRect(5, 5, 15, 15, "b", "body"),  # 與 a 相交
            ])


class TestConflictsOwnerAware(unittest.TestCase):
    """M4-3a-2 (DD-10a) owner-aware 互斥：同 owner 不衝突、跨 owner 幾何相交即衝突。"""

    def test_same_owner_no_conflict(self):
        """同 owner 的 body/pin_extent 內部文字天然共存（假衝突抑制）。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        # 同 owner U1 的 pin_extent 落在 body 內 → 不算衝突
        res = led.try_reserve(LedgerRect(12, 12, 18, 18, "U1", "pin_extent"))
        self.assertTrue(res.ok)
        self.assertEqual(res.conflicts, [])
        self.assertEqual(len(led), 2)

    def test_cross_owner_conflict(self):
        """跨 owner 幾何相交＝真衝突。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        res = led.try_reserve(LedgerRect(25, 15, 45, 25, "U2", "body"))
        self.assertFalse(res.ok)
        self.assertEqual([c.owner for c in res.conflicts], ["U1"])


class TestBudgetInfeasible(unittest.TestCase):
    """TV-5：BUDGET_INFEASIBLE payload 契約（overloaded_edges + candidates_tried）。"""

    def test_tv5_payload_shape(self):
        edges = [{"axis": "w", "needed": 1400.0, "avail": 1189.0, "over": 211.0}]
        tried = [
            {"paper": "A4", "needed_w": 1400.0, "avail_w": 297.0, "needed_h": 100.0, "avail_h": 210.0, "reason": "width"},
            {"paper": "A0", "needed_w": 1400.0, "avail_w": 1189.0, "needed_h": 100.0, "avail_h": 841.0, "reason": "width"},
        ]
        exc = BudgetInfeasible(edges, tried)
        self.assertEqual(exc.overloaded_edges, edges)
        self.assertEqual(exc.candidates_tried, tried)
        self.assertIn("BUDGET_INFEASIBLE", str(exc))
        self.assertIn("w:+211.0mm", str(exc))


class TestAssertNoLabelOverlap(unittest.TestCase):
    """TV-6：A5 斷言偵測帳本內 label↔label 真互疊（DD-11）。"""

    def test_tv6_clean_ledger_passes(self):
        """無 label 互疊時斷言回 0（PASS）。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        led.reserve(LedgerRect(40, 10, 60, 20, "LBL_A", "label"))
        led.reserve(LedgerRect(70, 10, 90, 20, "LBL_B", "label"))
        self.assertEqual(led.assert_no_label_overlap(), 0)

    def test_tv6_injected_overlap_raises(self):
        """人工注入跨 owner 重疊 label → 拋 LedgerAssertionFailed 附違規實體+快照。"""
        led = OccupancyLedger(paper="A1")
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        led.reserve(LedgerRect(40, 10, 60, 20, "LBL_A", "label"))
        # 直接 append 繞過 reserve 衝突檢查（模擬 emit 落帳 bug 產生的重疊）
        led._rects.append(LedgerRect(50, 12, 70, 18, "LBL_B", "label"))  # 與 LBL_A 相交
        with self.assertRaises(LedgerAssertionFailed) as ctx:
            led.assert_no_label_overlap()
        exc = ctx.exception
        self.assertEqual(len(exc.violations), 1)
        self.assertIn("violations", {**exc.snapshot, "violations": True})
        self.assertEqual(exc.snapshot["count"], 3)
        # 違規對雙方皆 label kind
        a, b = exc.violations[0]
        self.assertEqual({a.kind, b.kind}, {"label"})

    def test_tv6_power_adjacency_not_flagged(self):
        """power/body-label 鄰接 NOT 納入斷言（DD-11：非撞字）。"""
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 10, 30, 20, "U1", "body"))
        # label 落在 body 上（跨 owner 相交），但非 label↔label → 斷言不觸發
        led._rects.append(LedgerRect(15, 12, 35, 18, "LBL_RAIL", "label"))
        led._rects.append(LedgerRect(20, 14, 40, 16, "VCC#pwr", "power"))
        self.assertEqual(led.assert_no_label_overlap(), 0)


class TestWireKind(unittest.TestCase):
    """M6-1（DD-12）：wire 落帳 — drawn wire segment 以細長 rect 進帳本。"""

    def test_wire_is_valid_kind(self):
        # wire 必須是合法 kind（router 落帳 drawn wire）
        LedgerRect(10, 10, 30, 11, "NET_A", "wire")  # no raise

    def test_wire_reserve_and_conflict(self):
        led = OccupancyLedger()
        led.reserve(LedgerRect(10, 20, 30, 20.3, "NET_A", "wire"))
        # 另一 net 的 wire 交叉同區 → 跨 owner 真衝突
        c = led.query(LedgerRect(18, 12, 18.3, 28, "NET_B", "wire"))
        self.assertTrue(c)
        self.assertEqual(c[0].owner, "NET_A")


class TestPathClear(unittest.TestCase):
    """M6-1（DD-12）：path_clear — router 沿線淨空查詢，查 ledger 全體 rects。

    使用者鐵律：routing 不得碰到任何其他元素。path_clear 把整條 waypoints
    polyline 對帳本內 body/pin_extent/label/wire 做相交測試（除 host owners），
    回傳是否全程淨空 + 首個碰撞矩形（供 RCA / 降級決策）。
    """

    def _ledger_with_body(self):
        led = OccupancyLedger()
        led.reserve(LedgerRect(20, 20, 40, 40, "U2", "body"))
        led.reserve(LedgerRect(45, 22, 55, 24, "IO5", "label"))  # 跨 owner label
        return led

    def test_clear_path_returns_true(self):
        led = self._ledger_with_body()
        # 一條沿 y=10 的水平線，完全在 body/label 之外
        clear, hit = led.path_clear([(0, 10), (60, 10)], host_owners=frozenset())
        self.assertTrue(clear)
        self.assertIsNone(hit)

    def test_path_through_body_blocked(self):
        led = self._ledger_with_body()
        # 一條穿過 U2 body 內部的水平線
        clear, hit = led.path_clear([(0, 30), (60, 30)], host_owners=frozenset())
        self.assertFalse(clear)
        self.assertEqual(hit.owner, "U2")

    def test_path_through_label_blocked(self):
        led = self._ledger_with_body()
        # 穿過 IO5 label 的水平線（body 只避 body 的舊 router 會放行這條）
        clear, hit = led.path_clear([(44, 23), (60, 23)], host_owners=frozenset())
        self.assertFalse(clear)
        self.assertEqual(hit.owner, "IO5")

    def test_host_owner_excluded(self):
        led = self._ledger_with_body()
        # host_owners 含 U2 → 穿 U2 body 視為合法（自身 pin 接近腳）
        clear, hit = led.path_clear([(0, 30), (60, 30)], host_owners=frozenset({"U2"}))
        self.assertTrue(clear)
        self.assertIsNone(hit)


if __name__ == "__main__":
    unittest.main()
