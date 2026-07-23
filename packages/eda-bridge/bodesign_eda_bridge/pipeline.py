"""M7-1 layered pipeline skeleton — 顯式責任分層骨架與強凍結層間契約。

drawmiat IDEF0 renderer 的 L0–L6 責任分層移植到 eda-bridge 原理圖 pipeline
（design.md §分層架構）。本模組是 M7 重構的**地基層**：

- 定義 7 個 stage 槽位（L1→L2→L2.5→L3→L4→L5→L6）與各自的**凍結輸出契約**。
- per-render PhaseLog 追蹤每層決策（data-schema.json PhaseLog）。
- 強凍結守衛（DD-5）：下層試圖 mutate 上層產物 → raise FrozenContractViolation。

M7-1 範圍：骨架與資料流成形。各 stage 內部**尚未**接管 composer/emit 邏輯——
現行 render 仍走 compose_schematic 原路（行為 byte-identical）。後續里程碑
（M7-2 起）逐層把真實決策搬進對應 stage。因此本模組此刻不改變任何既有 render
輸出，只提供分層骨架供漸進遷移掛載。

天條（repo no-silent-fallback）：契約違規 fail-loud，不吞不修正。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# 分層枚舉（design.md §分層架構表 / idef0.json A1–A7）
# ---------------------------------------------------------------------------
class Layer(str, Enum):
    """七個責任層。值＝PhaseLog.phase 標籤（data-schema.json）。"""

    L1 = "L1"          # box placement
    L2 = "L2"          # pin read + escape
    L2_5 = "L2.5"      # route capacity plan
    L3 = "L3"          # routing
    L4 = "L4"          # violation detect + repair
    L5 = "L5"          # spacing balance
    L6 = "L6"          # labeling

    def __str__(self) -> str:  # PhaseLog 序列化用字面值（"L2.5" 非 "Layer.L2_5"）
        return self.value


# 分層線性順序（凍結守衛判斷「上層/下層」用）。索引越小越上層。
_LAYER_ORDER: tuple[Layer, ...] = (
    Layer.L1, Layer.L2, Layer.L2_5, Layer.L3, Layer.L4, Layer.L5, Layer.L6,
)


def _layer_rank(layer: Layer) -> int:
    return _LAYER_ORDER.index(layer)


# ---------------------------------------------------------------------------
# 凍結契約違規例外（DD-5）
# ---------------------------------------------------------------------------
class FrozenContractViolation(Exception):
    """下層試圖 mutate 上層已凍結的 stage 產物（DD-5 強凍結契約）。

    payload：
    - producer_layer: 產物的來源層（凍結它的層）。
    - offending_layer: 試圖改動它的下層（可為 None，若無法判定呼叫層）。
    - target: 被改動的物件描述（欄位名 / repr）。

    語義：層間凍結是分層架構的結構前提（「哪裏有問題就在哪裏改規則」）。
    違規＝下層越權改上層產物，是實作 bug，fail-loud 走 RCA，不靜默容忍。
    """

    def __init__(
        self,
        producer_layer: Layer,
        target: str,
        offending_layer: Layer | None = None,
    ) -> None:
        self.producer_layer = producer_layer
        self.offending_layer = offending_layer
        self.target = target
        _by = f" by {offending_layer}" if offending_layer is not None else ""
        super().__init__(
            f"FROZEN_CONTRACT_VIOLATION: attempt to mutate {producer_layer} "
            f"output {target!r}{_by}; upstream stage outputs are read-only once "
            f"frozen (DD-5)"
        )


# ---------------------------------------------------------------------------
# PhaseLog（data-schema.json PhaseLog：phase / decision / evidence 三欄）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PhaseLogEntry:
    """單一分層決策記錄。frozen → 記錄一旦寫入不可竄改。"""

    phase: Layer
    decision: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "phase": str(self.phase),
            "decision": self.decision,
            "evidence": dict(self.evidence),
        }


class PhaseLog:
    """per-render 分層 debug log。每層決策 append，render 後可整體傾印追溯。

    對齊 drawmiat per-render phase log（idef0_renderer.py:12「records every
    routing decision through L0–L6」）。
    """

    def __init__(self) -> None:
        self._entries: list[PhaseLogEntry] = []

    def record(
        self,
        phase: Layer,
        decision: str,
        evidence: dict[str, Any] | None = None,
    ) -> PhaseLogEntry:
        """記錄一層決策；回傳寫入的 entry。"""
        entry = PhaseLogEntry(phase=phase, decision=decision, evidence=evidence or {})
        self._entries.append(entry)
        return entry

    def entries(self) -> list[PhaseLogEntry]:
        """唯讀視圖（回複本，防外部改動內部清單）。"""
        return list(self._entries)

    def for_phase(self, phase: Layer) -> list[PhaseLogEntry]:
        return [e for e in self._entries if e.phase == phase]

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# 凍結 stage 產物基底（DD-5）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StageOutput:
    """所有分層 stage 輸出的凍結基底。

    frozen=True 已在 dataclass 層面阻止屬性再賦值（下層 `output.field = x`
    直接 raise dataclass FrozenInstanceError）。本基底額外標注 producer_layer，
    讓越權改動能被 guard_frozen() 轉譯為語義明確的 FrozenContractViolation，
    附上「哪一層凍結、被誰改」的 RCA 訊息。

    子類為各層具體產物（M7-2 起逐層填實欄位）。M7-1 提供骨架與契約守衛。
    """

    producer_layer: Layer

    def evolve(self, **changes: Any) -> "StageOutput":
        """在**同層內**產生修改後的新凍結複本（dataclasses.replace）。

        合法用途：同層 stage 迭代自己的中間結果（例 L4 repair 重寫自己的
        route 集合）。跨層改動禁止——下層要衍生新結構必須產生**自己層**的
        StageOutput 子類，而非 evolve() 上層產物（那會保留上層 producer_layer，
        被 assert_owned_by 抓出）。
        """
        return replace(self, **changes)


def guard_frozen(output: StageOutput, offending_layer: Layer) -> None:
    """凍結守衛（DD-5）：offending_layer 想改 output 時呼叫。

    若 offending_layer 排序在 output.producer_layer **之後**（即下層改上層），
    raise FrozenContractViolation。同層或上層對自己/下層產物的操作放行
    （上層本就先執行，不存在改下層既成品的時序）。

    這是**顯式**守衛：dataclass frozen 已擋直接賦值，本函式擋「下層拿到上層
    產物、想以 evolve/替換方式改它」的越權，並給出分層語義的錯誤。
    """
    if not isinstance(output, StageOutput):
        raise TypeError(
            f"guard_frozen expects a StageOutput, got {type(output).__name__}"
        )
    if _layer_rank(offending_layer) > _layer_rank(output.producer_layer):
        raise FrozenContractViolation(
            producer_layer=output.producer_layer,
            target=type(output).__name__,
            offending_layer=offending_layer,
        )


def assert_owned_by(output: StageOutput, expected_layer: Layer) -> StageOutput:
    """契約斷言：output 必須由 expected_layer 產出。

    stage 收到上游產物時用此確認來源層正確（防串接錯層 / evolve 洩漏上層
    producer_layer）。回傳 output 以便鏈式。
    """
    if output.producer_layer is not expected_layer:
        raise FrozenContractViolation(
            producer_layer=output.producer_layer,
            target=f"{type(output).__name__}(expected producer={expected_layer})",
        )
    return output


# ---------------------------------------------------------------------------
# 各層具體 stage 產物（M7-1：骨架欄位；M7-2 起逐層填實）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BoxGeometry(StageOutput):
    """L1 輸出：凍結的模組 box 幾何（data-schema FrozenBoxGeometry）。"""

    boxes: tuple = ()          # tuple[BoxPlacement] — M7-2 填實
    sheet: Any = None          # SheetChoice + ink density

    def __init__(self, boxes: tuple = (), sheet: Any = None) -> None:
        object.__setattr__(self, "producer_layer", Layer.L1)
        object.__setattr__(self, "boxes", tuple(boxes))
        object.__setattr__(self, "sheet", sheet)


@dataclass(frozen=True)
class EscapePlan(StageOutput):
    """L2 輸出：每 pin 的 escape corridor（data-schema EscapeCorridor 集合）。"""

    corridors: tuple = ()

    def __init__(self, corridors: tuple = ()) -> None:
        object.__setattr__(self, "producer_layer", Layer.L2)
        object.__setattr__(self, "corridors", tuple(corridors))


@dataclass(frozen=True)
class SlotTable(StageOutput):
    """L2.5 輸出：route 容量預留（data-schema SlotTable）。M7-2 核心。"""

    route_policy: Any = None   # map[net_id -> "wire"|"label"]
    slots: Any = None          # map[(gap_id, slot_idx) -> slot_coord]
    reserved: Any = None       # map[route_id -> slot_ref]

    def __init__(self, route_policy: Any = None, slots: Any = None, reserved: Any = None) -> None:
        object.__setattr__(self, "producer_layer", Layer.L2_5)
        object.__setattr__(self, "route_policy", route_policy)
        object.__setattr__(self, "slots", slots)
        object.__setattr__(self, "reserved", reserved)


@dataclass(frozen=True)
class RoutedPaths(StageOutput):
    """L3 輸出：佈線後 wire path 集合。"""

    wires: tuple = ()

    def __init__(self, wires: tuple = ()) -> None:
        object.__setattr__(self, "producer_layer", Layer.L3)
        object.__setattr__(self, "wires", tuple(wires))


@dataclass(frozen=True)
class ValidatedRoutes(StageOutput):
    """L4 輸出：檢核＋bounded repair 後的 route（含收斂狀態）。"""

    wires: tuple = ()
    violations: tuple = ()
    repair_passes: int = 0

    def __init__(self, wires: tuple = (), violations: tuple = (), repair_passes: int = 0) -> None:
        object.__setattr__(self, "producer_layer", Layer.L4)
        object.__setattr__(self, "wires", tuple(wires))
        object.__setattr__(self, "violations", tuple(violations))
        object.__setattr__(self, "repair_passes", int(repair_passes))


@dataclass(frozen=True)
class BalancedGeometry(StageOutput):
    """L5 輸出：等距平衡後幾何（topology 不變，只平移座標）。"""

    wires: tuple = ()

    def __init__(self, wires: tuple = ()) -> None:
        object.__setattr__(self, "producer_layer", Layer.L5)
        object.__setattr__(self, "wires", tuple(wires))


@dataclass(frozen=True)
class LabeledSchematic(StageOutput):
    """L6 輸出：最終圖（label 落帳完成，不回頭改線）。"""

    artifact: Any = None       # 最終 emit 結果 / 路徑

    def __init__(self, artifact: Any = None) -> None:
        object.__setattr__(self, "producer_layer", Layer.L6)
        object.__setattr__(self, "artifact", artifact)


# ---------------------------------------------------------------------------
# 分層 pipeline 骨架
# ---------------------------------------------------------------------------
class LayeredPipeline:
    """L1→L2→L2.5→L3→L4→L5→L6 顯式 stage 執行骨架（M7-1）。

    M7-1 契約：本骨架定義各層的槽位、輸入/輸出型別、與凍結守衛掛點，並在每層
    產出時寫 PhaseLog。各 stage 方法（stage_l1 ... stage_l6）在 M7-1 為**待接管
    的槽位**——真實決策仍由 compose_schematic 原路執行，逐層在 M7-2+ 遷入。

    因此 M7-1 不改變任何 render 輸出：LayeredPipeline 目前不接進 compose_schematic
    的主流程，僅提供骨架、契約與 log，供後續里程碑漸進掛載。
    """

    def __init__(self) -> None:
        self.log = PhaseLog()

    # 各 stage 槽位。回傳對應層的凍結 StageOutput，並記 PhaseLog。
    # M7-1：骨架委派點（尚未接管真實邏輯）。

    def stage_l1(self, box_geometry: BoxGeometry) -> BoxGeometry:
        out = assert_owned_by(box_geometry, Layer.L1)
        self.log.record(Layer.L1, "box placement frozen", {"n_boxes": len(out.boxes)})
        return out

    def stage_l2(self, prev: BoxGeometry, escape: EscapePlan) -> EscapePlan:
        # prev 是 L1 凍結產物，作為唯讀輸入串接（讀取不觸發 guard；guard_frozen
        # 專責攔「下層想 mutate 上層」，見 guard_frozen docstring）。
        assert_owned_by(prev, Layer.L1)
        out = assert_owned_by(escape, Layer.L2)
        self.log.record(Layer.L2, "pin escape corridors decided", {"n_corridors": len(out.corridors)})
        return out

    def stage_l2_5(self, prev: EscapePlan, table: SlotTable) -> SlotTable:
        assert_owned_by(prev, Layer.L2)
        out = assert_owned_by(table, Layer.L2_5)
        self.log.record(Layer.L2_5, "route capacity reserved", {})
        return out

    def stage_l3(self, prev: SlotTable, routed: RoutedPaths) -> RoutedPaths:
        assert_owned_by(prev, Layer.L2_5)
        out = assert_owned_by(routed, Layer.L3)
        self.log.record(Layer.L3, "routes drawn (consume reserved slots)", {"n_wires": len(out.wires)})
        return out

    def stage_l4(self, prev: RoutedPaths, validated: ValidatedRoutes) -> ValidatedRoutes:
        assert_owned_by(prev, Layer.L3)
        out = assert_owned_by(validated, Layer.L4)
        self.log.record(
            Layer.L4,
            "violation detect + bounded repair",
            {"violations": len(out.violations), "repair_passes": out.repair_passes},
        )
        return out

    def stage_l5(self, prev: ValidatedRoutes, balanced: BalancedGeometry) -> BalancedGeometry:
        assert_owned_by(prev, Layer.L4)
        out = assert_owned_by(balanced, Layer.L5)
        self.log.record(Layer.L5, "spacing balanced (topology preserved)", {"n_wires": len(out.wires)})
        return out

    def stage_l6(self, prev: BalancedGeometry, labeled: LabeledSchematic) -> LabeledSchematic:
        assert_owned_by(prev, Layer.L5)
        out = assert_owned_by(labeled, Layer.L6)
        self.log.record(Layer.L6, "labels placed (no wire mutation)", {})
        return out
