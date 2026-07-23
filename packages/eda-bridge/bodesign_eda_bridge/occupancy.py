"""OccupancyLedger — 2D 空間佔用帳本（budget-first / frame-first 架構核心）。

compose→emit 全流程共用的單一 SSOT：任何佔紙面面積的實體（符號 body、pin 外伸、
stub、label、電源/GND 符號、pwr_flag、圖框邊界）在落筆前必須先 reserve。

天條（repo §2.1 no-silent-fallback）：
- 非法輸入（x1<=x0 / y1<=y0 / 未知 kind）立即 ValueError，不修正不吞。
- reserve 衝突 fail-loud：拋 LedgerConflict 附全部衝突矩形，不靜默改位。

M1 階段：模組獨立，不接線既有引擎（DD-1）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# LedgerRect.kind 允許值（data-schema.json）
# M6-1 (DD-12): "wire" — drawn wire segment 以細長 rect 落帳，讓 router 沿線查
# ledger 全體佔用（body/pin_extent/label/wire）而非只避 body。使用者鐵律：
# routing 不得碰到任何其他元素。
VALID_KINDS = frozenset(
    {"body", "pin_extent", "stub", "label", "power", "flag", "frame_margin", "wire"}
)

# M7-1.3 (DD-6): 分段落帳 — 每層只寫自己職責的 kind。source_layer 標注寫入來源
# 層；kind 與 source_layer 不匹配 → fail-fast（越層落帳＝實作 bug）。
# 映射（design.md §分層架構 / data-schema LedgerEntry.source_layer）：
#   L1 → body（模組 body 外框）
#   L2 → stub（pin escape 外伸段；現況 kind 名為 "stub"）
#   L3 → wire（佈線段）
#   L6 → label / power（net label、電源/GND 符號文字盒）
# 其餘 kind（pin_extent 同符號內部文字、flag、frame_margin）非分層產物，不綁層，
# 任何 source_layer 皆放行（含 None）。source_layer=None（既有呼叫）一律放行 →
# byte-identical 相容，落帳分層是 opt-in。
VALID_SOURCE_LAYERS = frozenset({"L1", "L2", "L3", "L6"})

_LAYER_KIND_OWNERSHIP: dict[str, frozenset] = {
    "L1": frozenset({"body"}),
    "L2": frozenset({"stub"}),
    "L3": frozenset({"wire"}),
    "L6": frozenset({"label", "power"}),
}
# 受分層管轄的 kind（出現在任一層的職責集合內）。只有這些 kind 在帶了
# source_layer 時才做匹配檢查；其餘 kind 不綁層。
_LAYERED_KINDS: frozenset = frozenset(
    k for kinds in _LAYER_KIND_OWNERSHIP.values() for k in kinds
)


@dataclass(frozen=True)
class LedgerRect:
    """一個佔用矩形（頁座標，mm）。

    半開區間語義 [x0, x1) × [y0, y1)：邊緣相接（x1==other.x0）不算相交（TV-3）。
    frozen=True → 可 hash、可安全放進 snapshot/清單而不被意外改動。
    """

    x0: float
    y0: float
    x1: float
    y1: float
    owner: str
    kind: str
    source_layer: str | None = None  # M7-1.3 (DD-6)：寫入來源層；None=不分層（既有呼叫）

    def __post_init__(self) -> None:
        # fail-fast：退化/反向矩形非法（no-silent-fallback）
        if not (self.x1 > self.x0):
            raise ValueError(
                f"LedgerRect requires x1>x0, got x0={self.x0} x1={self.x1} (owner={self.owner!r})"
            )
        if not (self.y1 > self.y0):
            raise ValueError(
                f"LedgerRect requires y1>y0, got y0={self.y0} y1={self.y1} (owner={self.owner!r})"
            )
        if self.kind not in VALID_KINDS:
            raise ValueError(
                f"LedgerRect unknown kind {self.kind!r}; valid: {sorted(VALID_KINDS)}"
            )
        # M7-1.3 (DD-6) 分段落帳守衛：source_layer 給定時，其 kind 必須屬於該層職責。
        # None（既有呼叫）放行 → byte-identical。未受分層管轄的 kind 不檢查。
        if self.source_layer is not None:
            if self.source_layer not in VALID_SOURCE_LAYERS:
                raise ValueError(
                    f"LedgerRect unknown source_layer {self.source_layer!r}; "
                    f"valid: {sorted(VALID_SOURCE_LAYERS)}"
                )
            if self.kind in _LAYERED_KINDS:
                owned = _LAYER_KIND_OWNERSHIP[self.source_layer]
                if self.kind not in owned:
                    raise LayerKindMismatch(
                        kind=self.kind,
                        source_layer=self.source_layer,
                        owner=self.owner,
                    )

    def overlaps(self, other: "LedgerRect") -> bool:
        """半開區間相交測試：邊緣相接不算相交。"""
        return (
            self.x0 < other.x1
            and other.x0 < self.x1
            and self.y0 < other.y1
            and other.y0 < self.y1
        )

    def to_dict(self) -> dict:
        d = {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "owner": self.owner,
            "kind": self.kind,
        }
        if self.source_layer is not None:
            d["source_layer"] = self.source_layer
        return d


@dataclass
class ReserveResult:
    """try_reserve 的回傳（不拋例外版本）。"""

    ok: bool
    conflicts: list[LedgerRect] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "conflicts": [c.to_dict() for c in self.conflicts]}


class LayerKindMismatch(Exception):
    """M7-1.3 (DD-6)：落帳 kind 與宣告的 source_layer 不匹配（越層落帳）。

    payload：kind（被落帳的物件類型）、source_layer（宣告的來源層）、owner。

    語義：分段落帳制度下每層只寫自己職責的 kind（L1→body / L2→stub /
    L3→wire / L6→label,power）。下層寫了不屬於自己的 kind＝越權落帳，是實作
    bug，fail-loud 走 RCA，不靜默接受（errors.md no-silent-fallback 擴充條）。
    """

    def __init__(self, kind: str, source_layer: str, owner: str) -> None:
        self.kind = kind
        self.source_layer = source_layer
        self.owner = owner
        _owned = sorted(_LAYER_KIND_OWNERSHIP.get(source_layer, frozenset()))
        super().__init__(
            f"LAYER_KIND_MISMATCH: {source_layer} may not reserve kind {kind!r} "
            f"(owner={owner!r}); {source_layer} owns {_owned}. Each layer writes "
            f"only its own kind (DD-6 分段落帳)."
        )


class LedgerConflict(Exception):
    """reserve 的矩形與帳本既有矩形相交（DD-2 fail-loud 交易）。

    payload：requested（欲 reserve 的矩形）+ conflicts（全部衝突矩形清單）。
    呼叫端顯式位移策略耗盡後升級為 BUDGET_INFEASIBLE；禁止捕捉後靜默改位續跑。
    """

    def __init__(self, requested: LedgerRect, conflicts: list[LedgerRect]) -> None:
        self.requested = requested
        self.conflicts = conflicts
        owners = ", ".join(sorted({c.owner for c in conflicts}))
        super().__init__(
            f"reserve conflict for {requested.owner!r} ({requested.kind}) "
            f"vs {len(conflicts)} rect(s) [{owners}]"
        )


class BudgetInfeasible(Exception):
    """A2 掃畢所有 frame×pitch 候選無可行組合（DD-2 / DD-3 / errors.md BUDGET_INFEASIBLE）。

    payload：
    - overloaded_edges: 超出最大圖框的軸清單，每項 {axis, needed, avail, over}（mm）。
    - candidates_tried: 各被否決候選的原因軌跡，每項含 paper/needed/avail/reason。

    語義：fail-loud 終止 compose。人工裁決拆 unit（DD-7）、分頁或改內容；
    禁止升框迴圈、禁止降 scale 硬壓（errors.md Recovery）。
    """

    def __init__(self, overloaded_edges: list[dict], candidates_tried: list[dict]) -> None:
        self.overloaded_edges = overloaded_edges
        self.candidates_tried = candidates_tried
        _axes = ", ".join(
            f"{e['axis']}:+{e['over']}mm" for e in overloaded_edges
        ) or "none"
        super().__init__(
            f"BUDGET_INFEASIBLE: content exceeds largest standard frame "
            f"[{_axes}]; {len(candidates_tried)} candidate(s) rejected"
        )


class LedgerAssertionFailed(Exception):
    """A5 事後斷言不成立（DD-5 / DD-11）：帳本落定後偵測到本不該存在的
    結構性互疊（如 label↔label 真互疊）。

    payload：violations（違規矩形對清單，每對 owner/kind/座標）+ snapshot（全帳本傾印）。
    語義：帳本正確則斷言恆真；失敗＝ledger/placement 實作 bug，走 RCA 修引擎，
    不調參不重試（errors.md LEDGER_ASSERTION_FAILED）。
    """

    def __init__(self, violations: list[tuple[LedgerRect, LedgerRect]], snapshot: dict) -> None:
        self.violations = violations
        self.snapshot = snapshot
        super().__init__(
            f"LEDGER_ASSERTION_FAILED: {len(violations)} structural overlap(s) "
            f"in a {snapshot.get('count', 0)}-rect ledger"
        )


class IntraSymbolTextOverlap(Exception):
    """M4-1 / scale-coherence DD-6a：同一符號內部文字框（真縮放尺寸）互疊。

    payload：violations（同 owner 互疊的 pin_extent 矩形對清單）+ snapshot（帳本傾印）。
    語義：舊 A5 閘 owner-aware 對同 owner 一律豁免，因此測不到同一 U1 內部因 scale
    分裂而疊在一起的字——本例外專抓這類盲區。fail-loud：修幾何/scale 傳播，
    不降容忍、不自動避讓（errors.md LEDGER_ASSERTION_FAILED 擴充條）。
    """

    def __init__(self, violations: list[tuple[LedgerRect, LedgerRect]], snapshot: dict) -> None:
        self.violations = violations
        self.snapshot = snapshot
        _owners = ", ".join(sorted({a.owner for a, _ in violations})) or "none"
        super().__init__(
            f"TEXT_OVERLAP_INTRA_SYMBOL: {len(violations)} in-symbol text overlap(s) "
            f"[owners: {_owners}] in a {snapshot.get('count', 0)}-rect ledger"
        )


_KICAD_BASE_PITCH = 2.54  # KiCad 100-mil grid; page_scale = pitch / this
_BASE_PIN_LENGTH = 5.08   # legacy pin graphic length (unscaled)
_BASE_TEXT_HEIGHT = 1.27  # legacy pin-name/number/property text height (unscaled)
_BASE_CHAR_WIDTH = 1.05   # per-char width approximation (unscaled)


class ScaleContextMissing(Exception):
    """CCM path 幾何消費者在 strict 模式下收不到 scale（DD-1 no-silent-fallback）。

    語義：scale 是單一傳播源，CCM per-page variant 路徑缺 scale 時必須顯式報錯，
    禁止靜默採用 page_scale=1.0 續跑（那正是「字大骨架小」殘留 1.27 的來源）。
    非 CCM caller（style=netlist 等）不觸發本例外——其 scale 預設 1.0 恆等。
    """

    def __init__(self, consumer: str, detail: str = "") -> None:
        self.consumer = consumer
        super().__init__(
            f"SCALE_CONTEXT_MISSING: geometry consumer {consumer!r} received no "
            f"ScaleContext on the CCM path (strict mode); refusing silent 1.0 fallback"
            + (f" [{detail}]" if detail else "")
        )


@dataclass(frozen=True)
class ScaleContext:
    """單一 scale 傳播源（DD-1 / data-schema.json）。

    pitch-scan 定案時凍結一次；所有幾何消費者（symbol builder、emit、ledger box
    建模、閘）由此推導尺寸，不各自持有零散 scale 參數。frozen=True 防意外改動。
    """

    page_scale: float
    paper: str | None = None

    def __post_init__(self) -> None:
        if not (self.page_scale > 0):
            raise ValueError(
                f"ScaleContext requires page_scale>0, got {self.page_scale!r}"
            )

    @classmethod
    def from_pitch(cls, pitch_mm: float, paper: str | None = None) -> "ScaleContext":
        """由 pitch-scan 選定的 pitch 建構（page_scale = pitch / 2.54）。"""
        return cls(page_scale=round(pitch_mm / _KICAD_BASE_PITCH, 4), paper=paper)

    @property
    def pin_pitch_mm(self) -> float:
        return round(_KICAD_BASE_PITCH * self.page_scale, 4)

    @property
    def pin_length_mm(self) -> float:
        return round(_BASE_PIN_LENGTH * self.page_scale, 4)

    @property
    def text_height_mm(self) -> float:
        return round(_BASE_TEXT_HEIGHT * self.page_scale, 4)

    @property
    def char_width_mm(self) -> float:
        return round(_BASE_CHAR_WIDTH * self.page_scale, 4)

    def require(self, consumer: str) -> "ScaleContext":
        """strict 守衛：CCM 消費者用此確保 scale 已傳達（回傳自身以便鏈式）。"""
        return self


def require_scale_context(ctx: "ScaleContext | None", consumer: str) -> "ScaleContext":
    """CCM path strict 守衛：ctx 為 None 即 fail-loud（DD-1）。

    非 CCM caller 不呼叫本函式——它們的 scale 預設 1.0 恆等，維持 byte-identical。
    """
    if ctx is None:
        raise ScaleContextMissing(consumer)
    return ctx


class OccupancyLedger:
    """2D 佔用帳本。純 Python list 掃描（頁面實體數 <10³，秒級可負擔）。"""

    def __init__(self, paper: str | None = None) -> None:
        self._rects: list[LedgerRect] = []
        self.paper = paper

    # ---- 互斥語義 (M4-3a-2, DD-10a) -----------------------------------

    @staticmethod
    def _conflicts_with(a: LedgerRect, b: LedgerRect) -> bool:
        """owner-aware 互斥：兩矩形是否構成真衝突。

        規則（DD-10a）：
        - 同 owner → 不衝突（同符號內部的 body / pin_extent / prop 文字天然共存）。
        - 跨 owner → 幾何相交即真衝突（結構性佔用 body/label/power/pin_extent 對任何他者）。

        不得解讀為幾何分群啟發式（DD-10a 拒絕的方案 B）：owner 是 emit 落帳時
        標註的真實來源 ref，非後驗推斷。
        """
        if a.owner == b.owner:
            return False
        return a.overlaps(b)

    # ---- 查詢 ----------------------------------------------------------

    def query(self, rect: LedgerRect) -> list[LedgerRect]:
        """回傳帳本中與 rect 真衝突的既有矩形（owner-aware：同 owner 不算衝突）。

        M4-3a-2 前：純幾何相交（同符號內部文字框被誤判為衝突 → 71% 假衝突）。
        M4-3a-2 後：owner-aware，同符號 body/pin_extent/prop 共存，只留跨實體真衝突。
        """
        return [r for r in self._rects if self._conflicts_with(r, rect)]

    # ---- 落帳 ----------------------------------------------------------

    def try_reserve(self, rect: LedgerRect) -> ReserveResult:
        """不拋例外版本：衝突則回 ok=False + conflicts，成功則入帳回 ok=True。"""
        conflicts = self.query(rect)
        if conflicts:
            return ReserveResult(ok=False, conflicts=conflicts)
        self._rects.append(rect)
        return ReserveResult(ok=True, conflicts=[])

    def reserve(self, rect: LedgerRect) -> None:
        """fail-loud 交易（DD-2）：衝突拋 LedgerConflict 附全部衝突矩形；成功入帳。"""
        conflicts = self.query(rect)
        if conflicts:
            raise LedgerConflict(rect, conflicts)
        self._rects.append(rect)

    # ---- M6-1 (DD-12) router 沿線淨空查詢 ------------------------------

    @staticmethod
    def _seg_hits_rect(a: tuple[float, float], b: tuple[float, float],
                       r: "LedgerRect") -> bool:
        """軸對齊線段 a-b 是否穿過矩形 r 的內部（半開區間，邊緣相接不算）。

        router 只發水平/垂直線段（Manhattan）；對角線恆回 False（emit 從不畫）。
        內部穿越判定與 kicad_emit._seg_hits_box 同語義：線段落在矩形跨距內、
        且垂直軸落在矩形開區間內才算 hit。共享邊/角的合法貼靠不算 hit。
        """
        ax, ay = a
        bx, by = b
        if abs(ay - by) < 1e-6:  # 水平線段
            if not (r.y0 < ay < r.y1):
                return False
            lo, hi = sorted((ax, bx))
            return lo < r.x1 and hi > r.x0 and (min(hi, r.x1) - max(lo, r.x0)) > 1e-6
        if abs(ax - bx) < 1e-6:  # 垂直線段
            if not (r.x0 < ax < r.x1):
                return False
            lo, hi = sorted((ay, by))
            return lo < r.y1 and hi > r.y0 and (min(hi, r.y1) - max(lo, r.y0)) > 1e-6
        return False

    def path_clear(
        self,
        waypoints: list[tuple[float, float]],
        host_owners: "frozenset[str] | set[str]" = frozenset(),
        kinds: "frozenset[str] | set[str] | None" = None,
    ) -> tuple[bool, "LedgerRect | None"]:
        """router 沿線淨空查詢（M6-1 / DD-12，使用者鐵律：routing 不得碰到任何其他元素）。

        把整條 waypoints polyline 對帳本內**全體** rect（body/pin_extent/label/
        wire/power/...）做內部穿越測試，host_owners 名下的 rect 豁免（wire 自己的
        host pin body/pin-name，其接近腳段合法貼靠自身）。

        - 輸入 waypoints：>=2 個絕對座標點，相鄰兩點構成一軸對齊線段。
        - 輸入 host_owners：本 wire 電氣連接的 host ref 集合（豁免）。
        - 輸入 kinds：若給定，只對這些 kind 的 rect 做碰撞測試（例 frozenset({"label","wire"})）；
          None 表全 kind。body/pin_extent 的避讓由 router 自己的 body keep-out（已驗證
          golden baseline）負責，kinds 限縮避免與它重複擋而誤傷合法繞行。
        - 回傳 (clear, first_hit)：clear=True 表全程淨空、first_hit=None；
          clear=False 時 first_hit=第一個被穿越的 rect（供 RCA / 降級決策）。
        - NOT：不修改帳本、不落帳（純查詢）；wire 落帳由呼叫端在確認 clear 後自行 reserve。
        - 完成條件：對每段線段掃畢所有符合 kind 的 rect 後回傳。
        """
        skip = set(host_owners)
        want = set(kinds) if kinds is not None else None
        for a, b in zip(waypoints, waypoints[1:]):
            for r in self._rects:
                if r.owner in skip:
                    continue
                if want is not None and r.kind not in want:
                    continue
                if self._seg_hits_rect(a, b, r):
                    return (False, r)
        return (True, None)

    # ---- dry-run（DD-3 pitch-scan 預檢）--------------------------------

    def dry_run(self) -> "OccupancyLedger":
        """回傳當前帳本的獨立副本；對副本的寫入不影響本尊（TV-4）。

        LedgerRect frozen → 淺拷貝清單即安全隔離（元素不可變）。
        """
        clone = OccupancyLedger(paper=self.paper)
        clone._rects = list(self._rects)
        return clone

    # ---- A5 事後斷言 (M4-3b, DD-5 / DD-11) ------------------------------

    def overlaps_of_kinds(self, kinds: frozenset[str]) -> list[tuple[LedgerRect, LedgerRect]]:
        """回傳帳本中「雙方 kind 都落在 kinds 集合、且 owner-aware 真衝突」的矩形對。

        DD-11 定案：A5 閘的真實守備對象是 label↔label 互疊（emit label solver 應
        by-construction 零互疊）。power/body-label 鄰接是合法佈局，NOT 納入。

        taxonomy：
        - 輸入 kinds：欲檢測的 kind 白名單（例如 frozenset({"label"})）。
        - 輸出：違規矩形對清單 [(a, b), ...]，每對 a/b 皆滿足 a.kind∈kinds、
          b.kind∈kinds、且 _conflicts_with(a,b)（跨 owner 幾何相交）。
        - 不得解讀為：全體跨 owner 衝突清單（那含 power 鄰接，非撞字）。
        - 完成條件：回傳空清單＝該 kind 集合內零真互疊。
        """
        hits: list[tuple[LedgerRect, LedgerRect]] = []
        subset = [r for r in self._rects if r.kind in kinds]
        for i in range(len(subset)):
            for j in range(i + 1, len(subset)):
                if self._conflicts_with(subset[i], subset[j]):
                    hits.append((subset[i], subset[j]))
        return hits

    def assert_no_label_overlap(self) -> int:
        """A5 斷言：ledger 內 label↔label owner-aware 真互疊必須為 0（DD-11）。

        >0 拋 LedgerAssertionFailed（附違規實體對＋帳本快照）；
        通過回傳 0（供 [gate] PASS 日誌行）。power/body-label 鄰接不納入。
        """
        violations = self.overlaps_of_kinds(frozenset({"label"}))
        if violations:
            raise LedgerAssertionFailed(violations, self.snapshot())
        return 0

    # ---- M4-1 intra-symbol 文字互疊 (scale-coherence DD-6a) ------------

    def intra_symbol_text_overlaps(self) -> list[tuple[LedgerRect, LedgerRect]]:
        """回傳「同一 owner 內 pin_extent 文字框彼此幾何相交」的矩形對。

        scale-coherence DD-6a：舊 A5 閘（overlaps_of_kinds/_conflicts_with）對
        「同 owner」一律豁免——正是盲區。同一 U1 的 pin-name / refdes / value
        文字若因 scale 傳播分裂（字放大、格子沒放大）而互疊，舊閘結構性測不到
        （這解釋 `label_overlap=0 PASS` 卻滿頁疊字）。

        本閘刻意反轉語義：**只看同 owner、只看 pin_extent kind**，用真縮放後的
        文字 box（emit 已以 page_scale 建模 _pin_name_box_abs / _prop_text_box）
        做幾何相交測試。跨 owner 由 label 閘與 body 佔用管轄，不在此。

        - 半開區間相交（LedgerRect.overlaps）：邊緣相接不算疊。
        - 完成條件：回傳空清單＝該符號內文字零互疊。
        """
        text = [r for r in self._rects if r.kind == "pin_extent"]
        hits: list[tuple[LedgerRect, LedgerRect]] = []
        for i in range(len(text)):
            for j in range(i + 1, len(text)):
                a, b = text[i], text[j]
                if a.owner == b.owner and a.overlaps(b):
                    hits.append((a, b))
        return hits

    def assert_no_intra_symbol_text_overlap(self) -> int:
        """DD-6a 斷言：同符號內部文字框真互疊必須為 0。

        >0 拋 IntraSymbolTextOverlap（附違規對＋快照）；通過回傳 0（供 [gate]
        intra_overlap=0 PASS 日誌行）。assert-only fail-loud，不自動避讓、不降容忍。
        """
        violations = self.intra_symbol_text_overlaps()
        if violations:
            raise IntraSymbolTextOverlap(violations, self.snapshot())
        return 0

    # ---- 傾印 ----------------------------------------------------------

    def snapshot(self) -> dict:
        """全帳本傾印（LedgerSnapshot；斷言失敗 RCA 唯一入口）。"""
        return {
            "rects": [r.to_dict() for r in self._rects],
            "paper": self.paper,
            "count": len(self._rects),
        }

    # ---- 便利 ----------------------------------------------------------

    def extend(self, rects: Iterable[LedgerRect]) -> None:
        """批次 reserve（任一衝突即拋，已入帳的不回滾——呼叫端自負一致性）。"""
        for r in rects:
            self.reserve(r)

    def __len__(self) -> int:
        return len(self._rects)

    @property
    def rects(self) -> list[LedgerRect]:
        """唯讀視圖（回複本，防外部改動內部清單）。"""
        return list(self._rects)
