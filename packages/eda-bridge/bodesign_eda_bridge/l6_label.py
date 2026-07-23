"""L6 labeling — M7 分層 pipeline 的 labeling 契約層（design.md DD-5）。

drawmiat IDEF0 renderer 的 L6 `label_resolution`（idef0_renderer.py:1876,2255,
2396）移植到電路原理圖。

職責（單一）：
- 輸入 balanced geometry（現階段＝routed wires 端點視圖）+ label 擺位清單。
- 契約化：把「label reach-bbox 落帳 + 互斥斷言」抽成顯式 L6 階段。
- 輸出 LabeledSchematic（producer_layer=L6）。

出口斷言（design.md 出口斷言表 L6，DD-5）：
- label reach-bbox 互斥（無疊字）→ 違反 raise LabelOverlap。
- wire geometry 與輸入 byte 一致（L6 絕不改線）→ 違反 raise WireMutatedError。

**契約層邊界（byte 安全）**：本模組**不搬動** kicad_emit 內與 emit 主流程深度
纏繞的 label/power S-expression 生成（`_power_symbol_instance` 等，動它必破
byte-identical）。只包裝已是純函式的 `_label_bbox`/`_bbox_overlap`，提供可獨立
驗證的 L6 出口斷言。emit 現有 label 路徑行為不變（fixture byte 等價）。

天條（no-silent-fallback）：label 互疊 / wire 被改 → fail-loud 走 RCA，不靜默
避讓、不吞。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .pipeline import LabeledSchematic
# reach-bbox 幾何：單一權威是 kicad_emit._label_bbox / _bbox_overlap（QA 與 emitter
# 共用同一 box 定義）。L6 契約層 import 之，不重複定義（DD-1 規則收件人制度）。
from .kicad_emit import _label_bbox, _bbox_overlap


class LabelOverlap(Exception):
    """L6 出口斷言違規：兩 label 的 reach-bbox 真互疊（疊字，DD-5 fail-fast）。

    payload：pair（互疊的兩 label 名 + bbox）。
    語義：label solver 應 by-construction 零互疊；出現互疊＝擺位 bug，fail-loud
    走 RCA，不靜默避讓（對齊 occupancy.assert_no_label_overlap 精神）。
    """

    def __init__(self, a_name: str, b_name: str, a_box, b_box) -> None:
        self.a_name = a_name
        self.b_name = b_name
        self.a_box = a_box
        self.b_box = b_box
        super().__init__(
            f"L6_LABEL_OVERLAP: label {a_name!r} bbox {a_box} overlaps "
            f"{b_name!r} bbox {b_box} (DD-5 fail-fast; label solver must be "
            f"overlap-free by construction)"
        )


class WireMutatedError(Exception):
    """L6 出口斷言違規：wire geometry 在 L6 被改動（DD-5 fail-fast）。

    語義：L6 只擺 label，wire 必須逐字不變。輸入與輸出 wires 不一致＝L6 越權
    改線，是實作 bug，fail-loud。
    """

    def __init__(self) -> None:
        super().__init__(
            "L6_WIRE_MUTATED: L6 labeling changed wire geometry; L6 places labels "
            "only and must never modify wires (DD-5 fail-fast)"
        )


@dataclass(frozen=True)
class LabelPlacement:
    """單一 label 的擺位（L6 工作單位）。

    - name      : net 名（決定 reach-bbox 寬度）。
    - x, y      : 錨點 sheet 絕對座標（mm）。
    - is_global : global label（多一個 glyph 寬度）。
    - edge      : outward 邊向量（文字沿此方向延伸；_label_bbox 用）。
    - text_scale: CCM sheet-coherence 縮放（1.0＝legacy byte-identical box）。
    """

    name: str
    x: float
    y: float
    is_global: bool = False
    edge: tuple = (1.0, 0.0)
    text_scale: float = 1.0

    def reach_bbox(self) -> tuple[float, float, float, float]:
        """label 的 rendered reach-bbox（委派 kicad_emit._label_bbox，單一權威）。"""
        return _label_bbox(
            self.name, self.x, self.y, self.is_global,
            edge=self.edge, text_scale=self.text_scale,
        )


class L6LabelStage:
    """L6 labeling 契約階段：reach-bbox 互斥斷言 + wire byte 一致斷言。"""

    def run(
        self,
        labels: list[LabelPlacement],
        wires_in: tuple = (),
        wires_out: tuple | None = None,
    ) -> LabeledSchematic:
        """執行 L6：斷言 label 互斥 + wire 未變 → 凍結 LabeledSchematic。

        - labels    : 待擺位的 label 清單。
        - wires_in  : L5 交來的 wire 端點視圖（唯讀輸入）。
        - wires_out : L6 產出的 wire 視圖；None 表 L6 原樣沿用 wires_in（正常路徑）。
                      給定且與 wires_in 不一致 → WireMutatedError（守衛越權改線）。

        出口斷言全過 → LabeledSchematic.artifact = {labels, wires}（wires 逐字沿用）。
        """
        # 出口斷言 1：wire byte 一致（L6 不改線）。
        effective_wires = wires_in if wires_out is None else wires_out
        if tuple(effective_wires) != tuple(wires_in):
            raise WireMutatedError()

        # 出口斷言 2：label reach-bbox 兩兩不互疊。
        self._assert_no_overlap(labels)

        artifact = {
            "labels": [
                {"name": l.name, "bbox": l.reach_bbox()} for l in labels
            ],
            "wires": tuple(wires_in),
        }
        return LabeledSchematic(artifact=artifact)

    @staticmethod
    def _assert_no_overlap(labels: list[LabelPlacement]) -> None:
        """reach-bbox 兩兩互斥（無疊字）。首個互疊即 fail-fast。"""
        boxes = [(l, l.reach_bbox()) for l in labels]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                (la, ba), (lb, bb) = boxes[i], boxes[j]
                if _bbox_overlap(ba, bb):
                    raise LabelOverlap(la.name, lb.name, ba, bb)
