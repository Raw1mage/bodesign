"""M7-4.2/4.3 — L4 檢核層：rulebook B 章機檢集中 + bounded repair loop。

design.md 分層表 A5/L4：violation detect + rulebook 機檢 + bounded local repair。
drawmiat 對應：L4 `violation_detector`/`run_repair_loop` + CrossingRegistry
（idef0_renderer.py:520-594）。

職責（單一）：
- 輸入 routed wires（L3 產物），輸出 ViolationReport（rule_id 含 L# 歸屬）。
- 機檢斷言集中：rulebook B 章 wire 幾何規則（B1 wire-vs-wire 不交叉、
  B3 同 IC pin 走線不自交）。以 CrossingRegistry 做增量交叉偵測。
- bounded repair loop（DD-7）：violation → 小範圍修復 → 重掃受影響 rules；
  pass 上限達到仍有 violation → fail-fast（RepairBudgetExceeded），拒絕交付。

天條（DD-7 / no-silent-fallback）：repair 無法收斂時 fail-loud 輸出診斷報告，
不靜默降級。**預設不啟用 repair**（repair_enabled=False）——現行 render 路徑
只做偵測、行為不變；repair loop 待 9 頁驗證後才啟用。

單一事實來源：wire-vs-wire 交叉定義委派 crossing_stats.CrossingRegistry，
不在本模組複製幾何判定（design.md DD-1 規則收件人制度）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from bodesign_eda_bridge.crossing_stats import CrossingRegistry

# rulebook B 章條款歸屬層（design.md DD-1：B→L2/L3；wire 幾何規則歸 L3 routing）。
_B_RULE_LAYER = "L3"

# 預設 repair pass 上限（DD-7；小如 3，對齊 drawmiat run_repair_loop bounded 精神）。
DEFAULT_MAX_PASSES = 3


@dataclass(frozen=True)
class WireRoute:
    """一條已佈線的 wire（L3 產物視圖）。

    - route_id: 唯一識別（CrossingRegistry 索引鍵）。
    - path: 正交折線頂點序列 [(x,y), ...]。
    - owner_ic: 若此 wire 是某 IC 的 pin 走線，記其 refdes（B3 同 IC 自交判定用）；
      None = 非單一 IC 歸屬（跨 IC / 一般 net）。
    """

    route_id: str
    path: list
    owner_ic: str | None = None


class RepairBudgetExceeded(Exception):
    """repair loop 達 pass 上限仍有 violation（DD-7 fail-fast）。

    payload：repair_passes（已消耗 pass 數）+ violations（殘留違規清單）。
    語義：沒有 fixture 覆蓋的 repair 不得靜默放行；達上限拒絕交付、輸出診斷。
    """

    def __init__(self, repair_passes: int, violations: list[dict]) -> None:
        self.repair_passes = repair_passes
        self.violations = violations
        super().__init__(
            f"REPAIR_BUDGET_EXCEEDED: {len(violations)} violation(s) remain after "
            f"{repair_passes} repair pass(es); refusing delivery (DD-7 fail-fast)"
        )


@dataclass
class ViolationReport:
    """L4 檢核結果。

    violations: [{'rule_id','layer','objects','detail'}]（rule_id 含 L# 歸屬）。
    repair_passes: 消耗的 repair pass 數（未啟用 repair 時為 0）。
    """

    violations: list[dict] = field(default_factory=list)
    repair_passes: int = 0

    def count(self) -> int:
        return len(self.violations)

    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {
            "violations": list(self.violations),
            "repair_passes": self.repair_passes,
            "ok": self.ok(),
        }


class L4Checker:
    """L4 檢核器：rulebook B 章機檢集中 + bounded repair loop。

    repair_enabled=False（預設）：只偵測不修，現行 render 路徑行為不變。
    repair_enabled=True：violation → repair_fn 逐條修 → 重掃，pass 上限 fail-fast。
    """

    def __init__(
        self,
        repair_enabled: bool = False,
        max_passes: int = DEFAULT_MAX_PASSES,
        repair_fn: Callable[[WireRoute, ViolationReport], WireRoute] | None = None,
    ) -> None:
        self.repair_enabled = repair_enabled
        self.max_passes = max_passes
        self.repair_fn = repair_fn

    # --- 機檢斷言（rulebook B 章） -----------------------------------------
    def _detect(self, wires: list[WireRoute]) -> list[dict]:
        """偵測 B 章 wire 幾何違規。回傳 violation 清單（不修）。

        - B1：任兩條 wire 內部交叉（wire 不得碰其他 wire）。
        - B3：同一 owner_ic 的兩條 wire 交叉（同 IC pin 走線不得自交）。
        兩者同源於 CrossingRegistry 的交叉偵測（單一事實來源），僅 owner_ic
        相同時額外標 B3。
        """
        reg = CrossingRegistry()
        by_id: dict[str, WireRoute] = {}
        for w in wires:
            reg.update(w.route_id, w.path, tag=w.owner_ic or "?")
            by_id[w.route_id] = w

        violations: list[dict] = []
        for c in reg.all():
            hr, vr = c["h_route"], c["v_route"]
            w_h, w_v = by_id.get(hr), by_id.get(vr)
            same_ic = (
                w_h is not None and w_v is not None
                and w_h.owner_ic is not None
                and w_h.owner_ic == w_v.owner_ic
            )
            rule_id = "B3" if same_ic else "B1"
            violations.append({
                "rule_id": rule_id,
                "layer": _B_RULE_LAYER,
                "objects": [hr, vr],
                "detail": (
                    f"wire {hr} × {vr} interior crossing at "
                    f"({c['x']},{c['y']})"
                    + (f" (same IC {w_h.owner_ic})" if same_ic else "")
                ),
            })
        return violations

    # --- 對外檢核入口 -------------------------------------------------------
    def check(self, wires: list[WireRoute]) -> ViolationReport:
        """檢核 routed wires。

        repair 關（預設）：回傳含 violation 的報告（repair_passes=0）。
        repair 開：bounded loop 修到 0 或達上限 fail-fast（RepairBudgetExceeded）。
        """
        current = list(wires)
        violations = self._detect(current)

        if not self.repair_enabled or not violations:
            return ViolationReport(violations=violations, repair_passes=0)

        if self.repair_fn is None:
            raise ValueError(
                "repair_enabled=True requires a repair_fn (no-silent-fallback: "
                "cannot repair without an explicit fixer)"
            )

        passes = 0
        report = ViolationReport(violations=violations, repair_passes=0)
        while violations and passes < self.max_passes:
            passes += 1
            # 逐條 violation 修復涉及的 wire，重建 route 集合後重掃（bounded：
            # 只有被修的 route 幾何變，CrossingRegistry 重掃時只重算受影響交叉）。
            offending_ids = {rid for v in violations for rid in v["objects"]}
            by_id = {w.route_id: w for w in current}
            for rid in offending_ids:
                w = by_id.get(rid)
                if w is not None:
                    by_id[rid] = self.repair_fn(w, report)
            current = list(by_id.values())
            violations = self._detect(current)
            report = ViolationReport(violations=violations, repair_passes=passes)

        if violations:
            raise RepairBudgetExceeded(repair_passes=passes, violations=violations)

        return ViolationReport(violations=[], repair_passes=passes)
