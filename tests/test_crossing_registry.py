"""M7-4.1/4.4 TDD — 增量 CrossingRegistry 正確性 + L4 檢核器 + bounded repair loop。

先紅後綠：本檔在 crossing_stats.CrossingRegistry / l4_check 落地前應 fail。
"""
from __future__ import annotations

import random
import unittest

from bodesign_eda_bridge.crossing_stats import (
    CrossingRegistry,
    count_interior_crossings,
)


def _brute_orthogonal_crossings(routes: dict[int, list[tuple[float, float]]]) -> int:
    """全重算對照組：把所有 route 的正交線段兩兩比對 proper interior crossing。

    只算 h-seg × v-seg 的內部穿越（與 CrossingRegistry 同定義），
    共享端點與同向重疊不計。
    """
    h_segs = []  # (y, x_min, x_max, route)
    v_segs = []  # (x, y_min, y_max, route)
    for ri, path in routes.items():
        for i in range(len(path) - 1):
            p1, p2 = path[i], path[i + 1]
            if abs(p1[1] - p2[1]) < 0.01:
                h_segs.append((p1[1], min(p1[0], p2[0]), max(p1[0], p2[0]), ri))
            elif abs(p1[0] - p2[0]) < 0.01:
                v_segs.append((p1[0], min(p1[1], p2[1]), max(p1[1], p2[1]), ri))
    n = 0
    for (y, xmn, xmx, hr) in h_segs:
        for (x, ymn, ymx, vr) in v_segs:
            if hr == vr:
                continue
            if xmn + 0.1 < x < xmx - 0.1 and ymn + 0.1 < y < ymx - 0.1:
                n += 1
    return n


class TestCrossingRegistryIncremental(unittest.TestCase):
    def test_single_crossing(self):
        reg = CrossingRegistry()
        # 水平 route 0：y=5, x 0→10；垂直 route 1：x=5, y 0→10 → 正中相交
        reg.update(0, [(0, 5), (10, 5)])
        reg.update(1, [(5, 0), (5, 10)])
        self.assertEqual(reg.count(), 1)
        self.assertEqual(reg.count_for(0), 1)
        self.assertEqual(reg.count_for(1), 1)

    def test_shared_endpoint_is_not_crossing(self):
        reg = CrossingRegistry()
        # T 接：共享端點 (5,5) 不算 crossing
        reg.update(0, [(0, 5), (5, 5)])
        reg.update(1, [(5, 5), (5, 10)])
        self.assertEqual(reg.count(), 0)

    def test_remove_updates_count(self):
        reg = CrossingRegistry()
        reg.update(0, [(0, 5), (10, 5)])
        reg.update(1, [(5, 0), (5, 10)])
        self.assertEqual(reg.count(), 1)
        reg.remove(1)
        self.assertEqual(reg.count(), 0)
        self.assertEqual(reg.count_for(0), 0)

    def test_update_replaces_route_segments(self):
        reg = CrossingRegistry()
        reg.update(0, [(0, 5), (10, 5)])
        reg.update(1, [(5, 0), (5, 10)])
        self.assertEqual(reg.count(), 1)
        # 把 route 1 移開，不再相交
        reg.update(1, [(50, 0), (50, 10)])
        self.assertEqual(reg.count(), 0)

    def test_incremental_matches_bruteforce_random(self):
        """核心：增量結果必須逐步等於全重算對照組。"""
        rng = random.Random(1234)
        for _ in range(20):
            routes: dict[int, list[tuple[float, float]]] = {}
            reg = CrossingRegistry()
            n_routes = rng.randint(2, 8)
            for ri in range(n_routes):
                if rng.random() < 0.5:
                    y = rng.randint(0, 20)
                    x1, x2 = sorted(rng.sample(range(0, 30), 2))
                    path = [(x1, y), (x2, y)]
                else:
                    x = rng.randint(0, 20)
                    y1, y2 = sorted(rng.sample(range(0, 30), 2))
                    path = [(x, y1), (x, y2)]
                routes[ri] = path
                reg.update(ri, path)
            self.assertEqual(
                reg.count(),
                _brute_orthogonal_crossings(routes),
                f"incremental != bruteforce for routes={routes}",
            )

    def test_all_returns_crossing_records(self):
        reg = CrossingRegistry()
        reg.update(0, [(0, 5), (10, 5)])
        reg.update(1, [(5, 0), (5, 10)])
        allc = reg.all()
        self.assertEqual(len(allc), 1)
        rec = allc[0]
        self.assertIn("x", rec)
        self.assertIn("y", rec)


class TestCrossingStatsBackCompat(unittest.TestCase):
    """升級後 count_interior_crossings（batch API）行為不變。"""

    def test_batch_counter_still_works(self):
        sch = (
            "(wire (pts (xy 0 5) (xy 10 5)))\n"
            "(wire (pts (xy 5 0) (xy 5 10)))\n"
        )
        self.assertEqual(count_interior_crossings(sch), 1)

    def test_batch_shared_endpoint_zero(self):
        sch = (
            "(wire (pts (xy 0 5) (xy 5 5)))\n"
            "(wire (pts (xy 5 5) (xy 5 10)))\n"
        )
        self.assertEqual(count_interior_crossings(sch), 0)


if __name__ == "__main__":
    unittest.main()
