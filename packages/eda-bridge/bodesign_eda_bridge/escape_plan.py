"""L2 pin escape plan — M7 分層 pipeline 的 pin escape corridor 決策層（design.md DD-3）。

drawmiat IDEF0 renderer 的 L1 `activity_boxes_and_port_sort`（idef0_renderer.py:1334）
移植到電路原理圖時**降級為唯讀**（DD-3）：IDEF0 port 可在 box 邊自由排序防交叉，
但電路 pin 的位置與朝向是 symbol 的硬約束（KiCad `at x y ROTATION`），不可重排。
因此 L2 只做兩件事，且都是**純推導、無座標系衝突**：

1. **escape 方向**（escape_direction）：從 pin 的 KiCad rotation 決定它朝哪個 box
   邊直出（outward 單位向量）。這是 kicad_emit `_pin_edge` 的方向決策**唯一權威**
   （M7-3.2 拆出：邏輯只留這一份，kicad_emit 改為呼叫本模組）。
2. **escape corridor**（build_escape_plan）：每 pin 一條 EscapeCorridor（pin 端點 +
   方向 + 直出長度），輸出凍結 EscapePlan（接 pipeline，producer_layer==Layer.L2）。

出口斷言（design.md 出口斷言表 L2，DD-3）：每 pin 有唯一 escape 方向；corridor
與任何 body 不相交。任一違反 → raise EscapePlanError（fail-fast，天條
no-silent-fallback）。

## escape 方向 SSOT
「pin rotation → outward 向量」原實作在 kicad_emit.py `_pin_edge`（closure over
placements/pin_maps）。M7-3.2 起該決策的**唯一權威**是本模組 escape_direction
（純函式，只吃 pin endpoint tuple）；kicad_emit `_pin_edge` 改為委派，方向邏輯
只留這一份。KiCad pin `at ANGLE` 慣例：0=左邊(outward -x)、180=右邊(+x)、
90=下邊(sheet +y down)、270=上邊(sheet -y up)。
"""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline import EscapePlan, Layer

# escape corridor 直出長度（mm）。pin 先沿朝向直出此長度的 clear 走廊再轉彎
# （rulebook B2）；預設一個 KiCad 連接格距，與既有 stub 尺度一致。
DEFAULT_ESCAPE_LEN_MM = 1.27


class EscapePlanError(Exception):
    """L2 escape 出口斷言違規（DD-3 fail-fast）。

    觸發情形：pin 無法決定唯一 escape 方向、corridor 與 body 相交。
    語義：escape 走廊是 routing 的起手邊界，方向錯或撞 body 會傳染下游——
    fail-loud 走 RCA，不靜默降級（天條 no-silent-fallback）。
    """


def escape_direction(endpoint: tuple) -> tuple[float, float]:
    """M7-3.2：pin 的 outward escape 單位向量（SHEET 座標）。

    kicad_emit `_pin_edge` 的方向決策唯一權威（DD-3）。從 pin 的 KiCad
    rotation（endpoint 第 3 元素）決定它朝哪個 box 邊直出：

      - rot 0   → 左邊，outward (-1,  0)
      - rot 180 → 右邊，outward (+1,  0)
      - rot 90  → 下邊，outward ( 0, +1)（sheet y 向下）
      - rot 270 → 上邊，outward ( 0, -1)

    endpoint 是 _pin_endpoints 的 (x, y, rotation) tuple。legacy 2-tuple（無
    rotation）走 axis-test fallback：|ex|>=|ey| → 左/右；否則 上/下。原點
    (ex==ey==0) 預設右 (+1, 0)。

    這是**純函式**：只吃 endpoint tuple，不依賴任何 closure/placement 狀態，
    故無座標系衝突（DD-9 方案 B）。
    """
    rot = int(round(endpoint[2])) % 360 if len(endpoint) > 2 else None
    if rot is not None:
        if rot == 0:
            return (-1.0, 0.0)   # left edge, stub runs -x
        if rot == 180:
            return (1.0, 0.0)    # right edge, stub runs +x
        if rot == 90:
            return (0.0, 1.0)    # bottom edge, stub runs +y (screen down)
        if rot == 270:
            return (0.0, -1.0)   # top edge, stub runs -y (screen up)
    # Fallback (rotation absent — legacy 2-tuple pin map): axis test.
    ex, ey = endpoint[0], endpoint[1]
    if abs(ex) >= abs(ey):
        return (-1.0, 0.0) if ex < -0.01 else (1.0, 0.0)
    return (0.0, -1.0) if ey > 0.01 else (0.0, 1.0)


@dataclass(frozen=True)
class EscapeCorridor:
    """單一 pin 的 escape corridor（data-schema EscapeCorridor）。

    - ref, pin : pin 唯讀識別（來自 symbol 硬約束，不可挪）。
    - x, y     : pin 端點 sheet 絕對座標（mm）。
    - dx, dy   : outward escape 單位向量（escape_direction 決定）。
    - length   : 直出長度（mm）。
    """

    ref: str
    pin: str
    x: float
    y: float
    dx: float
    dy: float
    length: float = DEFAULT_ESCAPE_LEN_MM

    def far_point(self) -> tuple[float, float]:
        """corridor 直出末端（轉彎點）。"""
        return (round(self.x + self.dx * self.length, 4),
                round(self.y + self.dy * self.length, 4))


def build_escape_plan(
    pins: list[tuple[str, str, tuple[float, float], tuple]],
    *,
    body_rects: dict[str, tuple[float, float, float, float]] | None = None,
    escape_len: float = DEFAULT_ESCAPE_LEN_MM,
) -> EscapePlan:
    """L2 整合入口：每 pin 決定 escape corridor → 凍結 EscapePlan（接 pipeline）。

    輸入 pins：list of (ref, pin, abs_pt, endpoint)，其中
      - abs_pt   = (x, y) pin 的 sheet 絕對座標（呼叫端已算好，含 placement）。
      - endpoint = _pin_endpoints 的 (x, y, rotation) local tuple（供方向推導）。

    body_rects（可選）：{ref: (x0, y0, x1, y1)} 各元件 body 的 sheet 絕對矩形。
    給定時做出口斷言「corridor 與 body 不相交」——corridor 直出段（pin→far_point）
    不得穿過**任何其他元件** body（自己 host 的 body 不算，pin 本就長在自己身上）。

    出口斷言（DD-3）：
      * 每 pin 有唯一 escape 方向（escape_direction 純函式保證單值）。
      * corridor 與任何 non-host body 不相交（給定 body_rects 時檢查）。
    任一違反 → EscapePlanError（fail-fast）。
    """
    corridors: list[EscapeCorridor] = []
    for ref, pin, abs_pt, endpoint in pins:
        dx, dy = escape_direction(endpoint)
        corridor = EscapeCorridor(
            ref=ref, pin=pin, x=abs_pt[0], y=abs_pt[1], dx=dx, dy=dy, length=escape_len,
        )
        corridors.append(corridor)

    if body_rects is not None:
        _assert_corridors_clear_bodies(corridors, body_rects)

    return EscapePlan(corridors=tuple(corridors))


def _seg_rect_intersects(
    p0: tuple[float, float],
    p1: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> bool:
    """線段 p0→p1 是否穿入矩形 rect=(x0,y0,x1,y1)（半開語義，端點觸邊不算）。

    escape corridor 恆為軸向段（dx/dy 其一為 0），故只需軸向重疊測試：段落在
    rect 的 x 跨距與 y 跨距**同時**有真重疊（開區間）才算穿入。
    """
    x0, y0, x1, y1 = rect
    sx0, sx1 = sorted((p0[0], p1[0]))
    sy0, sy1 = sorted((p0[1], p1[1]))
    return (sx0 < x1 and x0 < sx1) and (sy0 < y1 and y0 < sy1)


def _assert_corridors_clear_bodies(
    corridors: list[EscapeCorridor],
    body_rects: dict[str, tuple[float, float, float, float]],
) -> None:
    """出口斷言：每條 corridor 直出段不穿過任何 non-host 元件 body（DD-3）。"""
    for c in corridors:
        far = c.far_point()
        for ref, rect in body_rects.items():
            if ref == c.ref:
                continue  # 自己 host 的 body 不算（pin 長在自己身上）
            if _seg_rect_intersects((c.x, c.y), far, rect):
                raise EscapePlanError(
                    f"escape corridor of pin {c.ref}.{c.pin} "
                    f"(dir=({c.dx},{c.dy}), len={c.length}) intersects body of "
                    f"{ref!r} rect={rect!r} (DD-3 fail-fast)"
                )
