"""M7-5.3/5.4 TDD — L6 labeling 契約層。

先紅後綠：本檔在 l6_label 落地前應 fail。

L6 職責（design.md 分層表 L6 行 / 出口斷言）：
- 輸入 balanced geometry（現階段＝routed wires）+ label 擺位清單，輸出 LabeledSchematic。
- 契約化：把「label 擺位 bbox + 落帳 + 互斥斷言」抽成顯式 L6 階段（純推導，
  不碰 kicad_emit 的 S-expression 序列化 → byte 等價）。
- 出口斷言：label reach-bbox 互斥（無疊字）+ wire geometry 與輸入 byte 一致
  （L6 絕不改線）。

**契約層設計**：不搬動 kicad_emit 內與 emit 主流程深度纏繞的 label/power 生成
（那是序列化，動它破 byte）；只包裝已是純函式的 _label_bbox/_bbox_overlap，提供
可獨立驗證的 L6 出口斷言（與 L5 同構，零 byte 風險）。
"""
from __future__ import annotations

import unittest

from bodesign_eda_bridge.l6_label import (
    LabelPlacement,
    L6LabelStage,
    LabelOverlap,
    WireMutatedError,
)
from bodesign_eda_bridge.pipeline import LabeledSchematic, Layer


def _lbl(name, x, y, is_global=False, edge=(1.0, 0.0)):
    return LabelPlacement(name=name, x=x, y=y, is_global=is_global, edge=edge)


class TestL6Contract(unittest.TestCase):
    def test_produces_labeled_schematic_l6(self):
        stage = L6LabelStage()
        wires = (("A", "1", "B", "2"),)
        out = stage.run(labels=[_lbl("NET1", 0.0, 0.0)], wires_in=wires)
        self.assertIsInstance(out, LabeledSchematic)
        self.assertIs(out.producer_layer, Layer.L6)

    def test_wire_byte_identity_preserved(self):
        # L6 不改線：輸入 wires 原樣掛在輸出（byte 一致）。
        stage = L6LabelStage()
        wires = (("A", "1", "B", "2"), ("C", "3", "D", "4"))
        out = stage.run(labels=[_lbl("N", 5.0, 5.0)], wires_in=wires)
        self.assertEqual(out.artifact["wires"], wires)


class TestL6OverlapAssertion(unittest.TestCase):
    def test_non_overlapping_labels_pass(self):
        stage = L6LabelStage()
        labels = [_lbl("AAA", 0.0, 0.0), _lbl("BBB", 0.0, 50.0)]  # y 遠隔
        out = stage.run(labels=labels, wires_in=())
        self.assertEqual(len(out.artifact["labels"]), 2)

    def test_overlapping_labels_fail_fast(self):
        stage = L6LabelStage()
        # 兩個 label 同錨點同方向 → reach-bbox 必疊 → fail-fast
        labels = [_lbl("SAME", 0.0, 0.0), _lbl("SAME", 0.0, 0.0)]
        with self.assertRaises(LabelOverlap):
            stage.run(labels=labels, wires_in=())


class TestL6WireGuard(unittest.TestCase):
    def test_mutating_wires_raises(self):
        # 若呼叫端把 wires_in 與 wires_out 給不一致 → WireMutatedError。
        stage = L6LabelStage()
        with self.assertRaises(WireMutatedError):
            stage.run(labels=[], wires_in=(("A", "1"),), wires_out=(("A", "2"),))


if __name__ == "__main__":
    unittest.main()
