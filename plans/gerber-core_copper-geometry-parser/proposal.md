# Proposal: gerber-core_copper-geometry-parser

## Why

- `quality_verify-checker-skillification`（verified）的盡職查核（event 2026-07-04
  `t-b-12-stub-ir-native-land-backlog`）證實：3-4 個 verified `control.*` 的判斷力清楚，
  唯一 blocker 是 **拿不到 copper 幾何**——`gerber-core` 目前僅到 summary 級，
  `BoardObject.geometry` 是 opaque dict，無 copper polygon / track / plane 的可計算幾何。
- 這些 control 的門檻都是 edge-to-edge **銅距** 或 plane 幾何（如 IPC 電壓-clearance、
  creepage 表面距離、RF 天線下 no-ground 區），沒有 copper 幾何 parser 就「知道要檢什麼、
  卻讀不到要檢的量」。
- 這是 DD-7 揭示的第二筆上游工，且工程量最大（等同蓋一個 gerber/copper 幾何解析器），
  應獨立成 plan。

## Original Requirement Wording (Baseline)

- 使用者 2026-07-04：「把未來的兩個 plan 先寫起來」——其二為 verify-checker T-B backlog 盡職查核
  指出的 copper-geometry parser 上游工（解鎖 3-4 個 clearance/creepage/銅距類 T-B control）。

## Requirement Revision History

- 2026-07-04: initial draft created via plan-init.ts
- 2026-07-04: proposal 填實（backlog 佔位，需求/範圍定案；designed 待未來啟動）

## Effective Requirement Description

1. 建一個 **純 python、零 pcbnew** 的 copper-geometry parser（比照 `checkers/board_outline.py`
   從已解析 artifact 消費幾何的路徑），把 gerber copper layer 的 polygon / track / pad / plane
   解析成可計算的幾何 primitive（座標、多邊形、net 歸屬）。
2. 提供確定性的 **edge-to-edge 銅距** 與 **point-to-copper / plane 覆蓋** 幾何查詢，供 verify-checker
   的 clearance/creepage 類 checker 讀取門檻量。
3. 解析失敗 / 缺 copper layer → fail-fast + 缺項清單（no-silent-fallback），絕不以近似或空結果靜默續跑。

## Scope

### IN
- gerber copper layer → 幾何 primitive（polygon / track / pad / plane，帶 net 歸屬）的確定性 parser。
- edge-to-edge 銅距、point-to-copper 距離、plane 覆蓋查詢（純幾何，byte-identical determinism）。
- 落點：`packages/gerber-core`（core，純 python）；重解析若需隔離則評估 worker 邊界（比照 AGENTS.md §4）。
- 解鎖並 land 這批 T-B control：
  `ipc-clearance-voltage`、`safety.creepage-clearance`、`safety.functional-spacing-formula`、
  `rf.antenna-keepout`（天線下 no-ground 區）。
- 對應 checker 在 `verify-checker-skillification` spec 以 `extend`/`amend` 掛入 registry。

### OUT
- **不做曲線 primitive 的粗略弦化近似**（比照 board_outline.py：arc/circle/curve 誠實跳過，
  不臆造 clearance 數值）——除非有明確 tessellation 契約。
- 不做 net role 判定（那是 `design-ir_net-role-extension` plan 的範圍）。
- 不引入 pcbnew / KiCad-mutating 依賴（保持 core 純 python）。
- 不在本 plan 補齊全部 12 個 T-B（net-role 類與需設計意圖類另計）。

## Non-Goals

- 不重寫既有 `gerber-core` 的 summary 級能力（只擴充幾何深解析，向後相容）。
- 不讓 LLM 參與幾何計算（純確定性）。

## Constraints

- **No silent fallback / No fabrication**（bodesign 天條）：缺 copper layer / 無法計算 →
  fail-fast + 缺項清單，不以近似或空結果靜默 pass。
- 曲線 primitive 未線性化前不得產出 clearance 數值（避免從近似邊臆造門檻）。
- 純 python，byte-identical determinism；core 不硬依賴 worker-only 套件。
- clearance 數值必帶幾何 provenance，對齊 datasheet-grounded / source_anchor 契約。

## What Changes

- `gerber-core`：新增 copper-geometry 深解析 + 幾何查詢 API。
- `verify-checker-skillification` registry：對應 T-B binding 由 stub → landed（跨 spec，extend）。
- `specs/architecture.md`：gerber-core 能力演進 + Verification Baseline 解鎖數更新。

## Capabilities

### New Capabilities
- copper-geometry parser：gerber copper layer → 可計算幾何 primitive（帶 net 歸屬）。
- edge-to-edge 銅距 / plane 覆蓋幾何查詢：clearance/creepage 類 checker 的門檻量來源。

### Modified Capabilities
- verify-checker registry：3-4 個 clearance/creepage/銅距 T-B binding 從 stub → landed。

## Impact

- `packages/gerber-core`（copper 幾何深解析 + 查詢 API）。
- `packages/workflow-core/.../checkers/`（clearance/creepage checker 改讀 copper 幾何）+ registry。
- `specs/architecture.md`、`quality_verify-checker-skillification` spec（extend）。
- Traceability：本 plan 是 `quality_verify-checker-skillification` DD-7 揭示的兩筆上游工之二
  （工程量較大者）。
