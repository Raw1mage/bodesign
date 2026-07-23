"""M7-1.4 TDD：分層 pipeline 骨架 + 凍結契約 + occupancy 分段落帳。

覆蓋（design.md DD-5 / DD-6）：
- 凍結契約：下層試圖改上層產物 → FrozenContractViolation。
- 分段落帳：錯層落帳（kind 不屬該 source_layer）→ LayerKindMismatch；
  source_layer=None（既有呼叫）一律放行（byte-identical）。
- PhaseLog：每層決策落 log，可傾印追溯。
"""

import unittest

from bodesign_eda_bridge.occupancy import (
    LayerKindMismatch,
    LedgerRect,
    OccupancyLedger,
)
from bodesign_eda_bridge.pipeline import (
    BalancedGeometry,
    BoxGeometry,
    EscapePlan,
    FrozenContractViolation,
    Layer,
    LabeledSchematic,
    LayeredPipeline,
    PhaseLog,
    RoutedPaths,
    SlotTable,
    ValidatedRoutes,
    assert_owned_by,
    guard_frozen,
)


class TestFrozenContract(unittest.TestCase):
    """DD-5 強凍結契約：下層不得 mutate 上層產物。"""

    def test_stage_output_is_frozen_dataclass(self):
        # frozen dataclass：直接屬性賦值即 raise（dataclass 層防線）。
        box = BoxGeometry(boxes=(("U1", 0, 0, 10, 10),))
        with self.assertRaises(Exception):
            box.boxes = ()  # frozen → FrozenInstanceError

    def test_guard_frozen_blocks_downstream_mutation(self):
        # L1 產物被 L3（下層）試圖改 → FrozenContractViolation。
        box = BoxGeometry()
        with self.assertRaises(FrozenContractViolation) as ctx:
            guard_frozen(box, Layer.L3)
        self.assertEqual(ctx.exception.producer_layer, Layer.L1)
        self.assertEqual(ctx.exception.offending_layer, Layer.L3)

    def test_guard_frozen_allows_same_layer(self):
        # 同層對自己產物操作放行（L4 repair 迭代自己的 route）。
        vr = ValidatedRoutes()
        guard_frozen(vr, Layer.L4)  # 不 raise

    def test_guard_frozen_allows_upstream(self):
        # 上層在下層產物之前執行，不存在改下層既成品——上層對下層放行。
        routed = RoutedPaths()
        guard_frozen(routed, Layer.L2)  # L2 rank < L3 → 放行

    def test_assert_owned_by_wrong_producer_raises(self):
        box = BoxGeometry()
        with self.assertRaises(FrozenContractViolation):
            assert_owned_by(box, Layer.L2)  # 宣稱 L2 但實為 L1

    def test_assert_owned_by_correct_producer_passes(self):
        table = SlotTable()
        self.assertIs(assert_owned_by(table, Layer.L2_5), table)

    def test_each_layer_output_carries_correct_producer(self):
        self.assertEqual(BoxGeometry().producer_layer, Layer.L1)
        self.assertEqual(EscapePlan().producer_layer, Layer.L2)
        self.assertEqual(SlotTable().producer_layer, Layer.L2_5)
        self.assertEqual(RoutedPaths().producer_layer, Layer.L3)
        self.assertEqual(ValidatedRoutes().producer_layer, Layer.L4)
        self.assertEqual(BalancedGeometry().producer_layer, Layer.L5)
        self.assertEqual(LabeledSchematic().producer_layer, Layer.L6)


class TestPhaseLog(unittest.TestCase):
    """per-render 分層 debug log。"""

    def test_record_and_dump(self):
        log = PhaseLog()
        log.record(Layer.L1, "box placement frozen", {"n_boxes": 3})
        log.record(Layer.L2_5, "route capacity reserved", {"slots": 5})
        self.assertEqual(len(log), 2)
        dumped = log.to_list()
        self.assertEqual(dumped[0]["phase"], "L1")
        self.assertEqual(dumped[1]["phase"], "L2.5")  # enum 值序列化為 "L2.5"
        self.assertEqual(dumped[0]["evidence"]["n_boxes"], 3)

    def test_for_phase_filter(self):
        log = PhaseLog()
        log.record(Layer.L3, "route A", {})
        log.record(Layer.L3, "route B", {})
        log.record(Layer.L4, "check", {})
        self.assertEqual(len(log.for_phase(Layer.L3)), 2)
        self.assertEqual(len(log.for_phase(Layer.L4)), 1)

    def test_entries_are_readonly_copy(self):
        log = PhaseLog()
        log.record(Layer.L1, "x", {})
        entries = log.entries()
        entries.clear()  # 改複本不影響內部
        self.assertEqual(len(log), 1)


class TestPipelineSkeleton(unittest.TestCase):
    """L1→...→L6 stage 骨架：串接與 log。"""

    def test_happy_path_stages_chain_and_log(self):
        pipe = LayeredPipeline()
        box = pipe.stage_l1(BoxGeometry(boxes=(("U1", 0, 0, 10, 10),)))
        esc = pipe.stage_l2(box, EscapePlan(corridors=(("U1", "1", "E", 5.0),)))
        tbl = pipe.stage_l2_5(esc, SlotTable(route_policy={}))
        rtd = pipe.stage_l3(tbl, RoutedPaths(wires=((0, 0, 5, 0),)))
        val = pipe.stage_l4(rtd, ValidatedRoutes(wires=((0, 0, 5, 0),)))
        bal = pipe.stage_l5(val, BalancedGeometry(wires=((0, 0, 5, 0),)))
        lbl = pipe.stage_l6(bal, LabeledSchematic(artifact="ok"))
        self.assertEqual(lbl.artifact, "ok")
        # 每層各記一筆 log。
        phases = [e.phase for e in pipe.log.entries()]
        self.assertEqual(
            phases,
            [Layer.L1, Layer.L2, Layer.L2_5, Layer.L3, Layer.L4, Layer.L5, Layer.L6],
        )

    def test_stage_rejects_wrong_upstream_layer(self):
        pipe = LayeredPipeline()
        # L2 stage 收到非 L1 產物 → raise。
        with self.assertRaises(FrozenContractViolation):
            pipe.stage_l2(SlotTable(), EscapePlan())


class TestSegmentedLedger(unittest.TestCase):
    """DD-6 分段落帳：kind 必須屬於 source_layer 的職責。"""

    def test_correct_layer_kind_ok(self):
        LedgerRect(0, 0, 10, 10, "U1", "body", source_layer="L1")
        LedgerRect(0, 0, 10, 10, "N1", "wire", source_layer="L3")
        LedgerRect(0, 0, 10, 10, "N1", "label", source_layer="L6")
        LedgerRect(0, 0, 10, 10, "N1", "power", source_layer="L6")
        LedgerRect(0, 0, 10, 10, "U1", "stub", source_layer="L2")

    def test_wrong_layer_kind_raises(self):
        # L1 只能寫 body；寫 wire → 越層落帳。
        with self.assertRaises(LayerKindMismatch):
            LedgerRect(0, 0, 10, 10, "N1", "wire", source_layer="L1")
        # L3 只能寫 wire；寫 body → 越層。
        with self.assertRaises(LayerKindMismatch):
            LedgerRect(0, 0, 10, 10, "U1", "body", source_layer="L3")
        # L6 只能寫 label/power；寫 wire → 越層。
        with self.assertRaises(LayerKindMismatch):
            LedgerRect(0, 0, 10, 10, "N1", "wire", source_layer="L6")

    def test_unknown_source_layer_raises(self):
        with self.assertRaises(ValueError):
            LedgerRect(0, 0, 10, 10, "U1", "body", source_layer="L9")

    def test_none_source_layer_always_ok(self):
        # source_layer=None（既有呼叫）一律放行——byte-identical 相容。
        LedgerRect(0, 0, 10, 10, "U1", "body")
        LedgerRect(0, 0, 10, 10, "N1", "wire")
        LedgerRect(0, 0, 10, 10, "U1", "pin_extent")  # 非分層 kind

    def test_non_layered_kind_not_checked(self):
        # pin_extent 未受分層管轄：即便帶 source_layer 也放行（不屬任何層職責集）。
        LedgerRect(0, 0, 10, 10, "U1", "pin_extent", source_layer="L1")
        LedgerRect(0, 0, 10, 10, "U1", "frame_margin", source_layer="L1")

    def test_to_dict_roundtrip_includes_source_layer(self):
        r = LedgerRect(0, 0, 10, 10, "N1", "wire", source_layer="L3")
        self.assertEqual(r.to_dict()["source_layer"], "L3")
        # None 時不含該鍵（byte-stable snapshot）。
        r2 = LedgerRect(0, 0, 10, 10, "N1", "wire")
        self.assertNotIn("source_layer", r2.to_dict())

    def test_reserve_with_source_layer_works(self):
        ledger = OccupancyLedger()
        ledger.reserve(LedgerRect(0, 0, 10, 10, "U1", "body", source_layer="L1"))
        self.assertEqual(len(ledger), 1)


if __name__ == "__main__":
    unittest.main()
