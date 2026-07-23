"""M7-3.4 TDD：L2 escape plan（escape_plan.py）+ cross-IC 政策雙份消除委派等價。

覆蓋（design.md DD-3 / DD-9 方案 B / 出口斷言表 L2）：
- escape 方向：pin rotation → outward 單位向量（唯一權威，取代 kicad_emit._pin_edge）。
- escape corridor：每 pin 一條 EscapeCorridor，凍結 EscapePlan（producer_layer==L2）。
- 出口斷言 fail-fast：corridor 穿 non-host body → EscapePlanError。
- cross-IC 雙份消除：kicad_emit 委派 capacity_plan.decide_route_policy（行為等價）。
"""

import unittest

from bodesign_eda_bridge.escape_plan import (
    DEFAULT_ESCAPE_LEN_MM,
    EscapeCorridor,
    EscapePlanError,
    build_escape_plan,
    escape_direction,
)
from bodesign_eda_bridge.pipeline import EscapePlan, Layer


class TestEscapeDirection(unittest.TestCase):
    """M7-3.2：pin rotation → outward escape 單位向量（唯一權威）。"""

    def test_rotation_maps_to_four_edges(self):
        self.assertEqual(escape_direction((0.0, 0.0, 0)), (-1.0, 0.0))    # 左
        self.assertEqual(escape_direction((0.0, 0.0, 180)), (1.0, 0.0))   # 右
        self.assertEqual(escape_direction((0.0, 0.0, 90)), (0.0, 1.0))    # 下
        self.assertEqual(escape_direction((0.0, 0.0, 270)), (0.0, -1.0))  # 上

    def test_rotation_normalised_modulo_360(self):
        self.assertEqual(escape_direction((0.0, 0.0, 360)), (-1.0, 0.0))
        self.assertEqual(escape_direction((0.0, 0.0, 540)), (1.0, 0.0))

    def test_unique_direction_per_pin(self):
        # 每 pin 恰一個方向（純函式單值）——非零向量、且只沿一軸。
        for rot in (0, 90, 180, 270):
            dx, dy = escape_direction((1.5, -2.0, rot))
            self.assertEqual((dx == 0.0) ^ (dy == 0.0), True)  # 恰一軸非零
            self.assertEqual(abs(dx) + abs(dy), 1.0)           # 單位向量

    def test_legacy_2tuple_axis_fallback(self):
        # 無 rotation 的 legacy 2-tuple → axis test。
        self.assertEqual(escape_direction((-3.0, 0.5)), (-1.0, 0.0))  # |ex|>=|ey|, ex<0
        self.assertEqual(escape_direction((3.0, 0.5)), (1.0, 0.0))    # |ex|>=|ey|, ex>0
        self.assertEqual(escape_direction((0.5, 3.0)), (0.0, -1.0))   # |ey|>|ex|, ey>0
        self.assertEqual(escape_direction((0.5, -3.0)), (0.0, 1.0))   # |ey|>|ex|, ey<0

    def test_origin_defaults_right(self):
        self.assertEqual(escape_direction((0.0, 0.0)), (1.0, 0.0))


class TestBuildEscapePlan(unittest.TestCase):
    """M7-3.2：build_escape_plan → 凍結 EscapePlan（接 pipeline）。"""

    def test_returns_frozen_plan_owned_by_l2(self):
        pins = [
            ("U1", "1", (10.0, 10.0), (0.0, 0.0, 180)),
            ("U1", "2", (10.0, 12.0), (0.0, 0.0, 180)),
        ]
        plan = build_escape_plan(pins)
        self.assertIsInstance(plan, EscapePlan)
        self.assertEqual(plan.producer_layer, Layer.L2)
        self.assertEqual(len(plan.corridors), 2)

    def test_corridor_far_point_follows_direction(self):
        # rot 180 → +x；far point = pin + (len, 0)。
        pins = [("U1", "1", (10.0, 10.0), (0.0, 0.0, 180))]
        plan = build_escape_plan(pins)
        c = plan.corridors[0]
        self.assertEqual(c.far_point(), (10.0 + DEFAULT_ESCAPE_LEN_MM, 10.0))

    def test_corridor_clear_of_body_passes(self):
        # pin 在 U1 右邊向 +x 直出；U2 body 在遠處左方 → 不相交。
        pins = [("U1", "1", (10.0, 10.0), (0.0, 0.0, 180))]
        body_rects = {"U2": (0.0, 0.0, 5.0, 20.0)}
        plan = build_escape_plan(pins, body_rects=body_rects)
        self.assertEqual(len(plan.corridors), 1)

    def test_corridor_into_body_raises(self):
        # pin 向 +x 直出，U2 body 正好擋在 +x 路徑上 → 穿 body，fail-fast。
        pins = [("U1", "1", (10.0, 10.0), (0.0, 0.0, 180))]
        body_rects = {"U2": (10.5, 5.0, 15.0, 15.0)}
        with self.assertRaises(EscapePlanError):
            build_escape_plan(pins, body_rects=body_rects, escape_len=2.0)

    def test_host_body_not_counted(self):
        # pin 自己 host（U1）的 body 涵蓋 pin 端點是正常的——不算相交。
        pins = [("U1", "1", (10.0, 10.0), (0.0, 0.0, 180))]
        body_rects = {"U1": (8.0, 8.0, 12.0, 12.0)}
        plan = build_escape_plan(pins, body_rects=body_rects)
        self.assertEqual(len(plan.corridors), 1)


class TestCrossIcDelegationEquivalence(unittest.TestCase):
    """M7-3.3：kicad_emit cross-IC 推導委派 capacity_plan 後行為等價。

    委派前 kicad_emit.py:668-679 手刻 per-pair 推導；委派後唯一權威是
    capacity_plan.decide_route_policy。此處驗證委派結果與原語義等價。
    """

    def test_delegation_matches_legacy_semantics(self):
        from bodesign_eda_bridge.capacity_plan import NetConn, decide_route_policy

        # 重現 kicad_emit 原推導的參考實作（未委派前的手刻邏輯）。
        def _legacy_crossic_label(nets, pin_ct):
            pair_sig = {}
            for net in nets:
                ics = sorted({r for (r, _p) in net.nodes if pin_ct.get(r, 0) > 2})
                if len(ics) < 2:
                    continue
                for i in range(len(ics)):
                    for j in range(i + 1, len(ics)):
                        pair_sig.setdefault(frozenset((ics[i], ics[j])), []).append(net.name)
            return {n for names in pair_sig.values() if len(names) >= 2 for n in names}

        pin_ct = {"U1": 8, "U2": 8, "U3": 8, "R1": 2}
        nets = [
            NetConn("SDA", (("U1", "1"), ("U2", "3"))),
            NetConn("SCL", (("U1", "2"), ("U2", "4"))),
            NetConn("INT", (("U1", "5"), ("U3", "1"))),
            NetConn("VOUT", (("U1", "6"), ("R1", "1"))),
        ]
        legacy = _legacy_crossic_label(nets, pin_ct)
        policy = decide_route_policy(nets, pin_ct)
        delegated = {name for name, style in policy.items() if style == "label"}
        self.assertEqual(delegated, legacy)
        # 具體：U1-U2 對有 2 信號 → SDA/SCL label；INT/VOUT wire。
        self.assertEqual(delegated, {"SDA", "SCL"})


if __name__ == "__main__":
    unittest.main()
