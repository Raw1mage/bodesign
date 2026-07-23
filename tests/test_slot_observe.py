"""M7-3b-i TDD：SlotTable 接進 render 主流程 + 觀察模式斷言（DD-11）。

零 fidelity 風險工單：routing 幾何一行不改，只接線與量測。覆蓋：

1. **接線**：composer 把 clusters 經新參數傳入 emit；emit 內部用既有
   pin_maps/placements + 傳入 clusters 建 SlotTable（build_slot_observation）。
2. **觀察斷言**：每條被接受的 drawn wire，對比「該 net 若有 reserved slot，
   實際路徑主幹是否落在 lane coord 容差內」，結果寫 PhaseLog（不改幾何）。
3. **觀察模式降級**：gap_topology/capacity_plan fail-fast（跨 >2 box、對角
   非相鄰）在觀察期以 PhaseLog 記 skip 原因，不中斷 render（顯式量測，非
   silent fallback——每筆 skip 都可在報告中看到）。
4. **向後相容**：clusters=None（預設）→ 不建 SlotTable、行為 byte-identical。

紅→綠：本檔先於實作寫成，import 目標函式在實作前不存在（先紅）。
"""

import unittest

from bodesign_eda_bridge.kicad_emit import EmitComponent, EmitNet
from bodesign_eda_bridge.composer import Cluster
from bodesign_eda_bridge.slot_observe import (
    SlotObservation,
    build_slot_observation,
    observe_wire_on_lane,
)


def _comp(ref, x, y, lib_id="Device:R", pins=2):
    return EmitComponent(ref=ref, lib_id=lib_id, x=x, y=y)


class TestBuildSlotObservation(unittest.TestCase):
    """composer clusters + emit 素材 → SlotObservation（含 SlotTable 或 skip）。"""

    def test_two_ic_cross_net_builds_slot_table(self):
        # 兩顆 IC（pin>2）水平相鄰，一條跨 IC net 走 wire。
        clusters = [
            Cluster(cluster_id="boxA", source="declared", members=["U1"]),
            Cluster(cluster_id="boxB", source="declared", members=["U2"]),
        ]
        comps = [_comp("U1", 0.0, 0.0, lib_id="MCU:U", ), _comp("U2", 100.0, 0.0, lib_id="MCU:U")]
        nets = [EmitNet(name="SIG1", nodes=[("U1", "1"), ("U2", "1")])]
        pin_count = {"U1": 8, "U2": 8}
        bboxes = {"U1": (20.0, 20.0), "U2": (20.0, 20.0)}

        obs = build_slot_observation(clusters, comps, nets, pin_count, bboxes)
        self.assertIsInstance(obs, SlotObservation)
        # SIG1 是唯一跨 box net → 應有 SlotTable 且 reserved 覆蓋它（wire 政策）。
        self.assertIsNotNone(obs.slot_table)
        self.assertIn("SIG1", obs.slot_table.route_policy)
        self.assertEqual(obs.skips, [])

    def test_cross_more_than_two_boxes_is_observed_skip_not_raise(self):
        # 一條 net 跨三個 box → gap_topology fail-fast；觀察模式應捕捉為 skip
        # 而非拋出（顯式量測，PhaseLog 可見）。
        clusters = [
            Cluster(cluster_id="bA", source="declared", members=["U1"]),
            Cluster(cluster_id="bB", source="declared", members=["U2"]),
            Cluster(cluster_id="bC", source="declared", members=["U3"]),
        ]
        comps = [_comp("U1", 0, 0), _comp("U2", 100, 0), _comp("U3", 200, 0)]
        nets = [EmitNet(name="TRIP", nodes=[("U1", "1"), ("U2", "1"), ("U3", "1")])]
        pin_count = {"U1": 1, "U2": 1, "U3": 1}
        bboxes = {"U1": (20, 20), "U2": (20, 20), "U3": (20, 20)}

        obs = build_slot_observation(clusters, comps, nets, pin_count, bboxes)
        # 不拋出；skip 記錄可見，帶原因。
        self.assertTrue(obs.skips, "expected an observed skip, got none")
        self.assertTrue(any("TRIP" in s.get("reason", "") or "TRIP" in str(s) for s in obs.skips))

    def test_empty_clusters_returns_empty_observation(self):
        # clusters 空 / None 語義：無 SlotTable，不拋出（向後相容）。
        obs = build_slot_observation([], [], [], {}, {})
        self.assertIsNone(obs.slot_table)


class TestObserveWireOnLane(unittest.TestCase):
    """觀察斷言：wire 主幹是否落在 reserved lane coord 容差內。"""

    def test_wire_on_reserved_lane_reports_hit(self):
        # reserved SIG1 lane 在 x=50；一條垂直主幹 waypoint 落在 x=50 → hit。
        reserved = {"SIG1": ("gapAB#0", 50.0)}
        waypoints = [(10.0, 0.0), (50.0, 0.0), (50.0, 30.0), (90.0, 30.0)]
        rec = observe_wire_on_lane("SIG1", waypoints, reserved, gap_axis="x", tol=0.5)
        self.assertTrue(rec["has_slot"])
        self.assertTrue(rec["hit"])

    def test_wire_off_reserved_lane_reports_miss(self):
        reserved = {"SIG1": ("gapAB#0", 50.0)}
        # 主幹全部遠離 x=50。
        waypoints = [(10.0, 0.0), (20.0, 0.0), (20.0, 30.0)]
        rec = observe_wire_on_lane("SIG1", waypoints, reserved, gap_axis="x", tol=0.5)
        self.assertTrue(rec["has_slot"])
        self.assertFalse(rec["hit"])

    def test_net_without_slot_reports_no_slot(self):
        rec = observe_wire_on_lane("OTHER", [(0.0, 0.0), (1.0, 1.0)], {}, gap_axis="x", tol=0.5)
        self.assertFalse(rec["has_slot"])


if __name__ == "__main__":
    unittest.main()
