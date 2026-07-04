# Design: gerber-core_copper-geometry-parser

## Context

`quality_verify-checker-skillification`（verified）的盡職查核（event 2026-07-04
`t-b-12-stub-ir-native-land-backlog`）證實：29 個 T-B `control.*` 的判斷力清楚，但卡在
**讀不到 copper 幾何**。`gerber-core` 目前僅到 summary 級（`contracts.py` 只有
`GerberGeometrySummary` / `GerberDrawSegment` / `GerberFlash` 這類 opaque 統計與 sample 幾何，
`parse_gerber_file` 只產 bounds/counts/samples，沒有可計算的 copper polygon / track / pad / plane，
也沒有 net 歸屬），因此 clearance/creepage/銅距類 control「知道要檢什麼、卻讀不到要檢的量」。

DD-7（`quality_verify-checker-skillification` design.md）明白揭示：implementing 階段的槓桿是
「補一個 parser 解鎖多個 control」而非逐一硬寫 checker。本 plan 是其揭示的兩筆上游工中
**工程量最大者**（等同蓋一個 copper 幾何解析器），故獨立成 plan。

既有的黃金範本是 `packages/workflow-core/bodesign_workflow_core/checkers/board_outline.py`：
純 python、零 pcbnew、從**已解析 artifact**（`ir["board_outline"]["edges"]`）消費幾何，
`edges_to_segments`（line 29）把 primitive 展成可算的線段、`point_to_segment_distance`（line 67）
是確定性 clearance 度量、`min_clearance_to_edge`（line 92）在無線段時回 `math.inf`
**要求 caller fail-fast**、且 arc/circle/curve **誠實跳過不弦化近似**。本 parser 完全比照這條路徑。

## Goals / Non-Goals

**Goals**

- 建一個**純 python、零 pcbnew** 的 copper-geometry parser：gerber copper layer →
  可計算幾何 primitive（polygon / track / pad / plane，帶座標與 net 歸屬）。
- 提供三種確定性幾何查詢：**edge-to-edge 銅距**、**point-to-copper 距離**、**plane 覆蓋**，
  同輸入 byte-identical 輸出，供 verify-checker 的 clearance/creepage 類 checker 讀門檻量。
- 解析失敗 / 缺 copper layer → **fail-fast + 缺項清單**（no-silent-fallback），
  絕不以近似或空結果靜默續跑。
- 每個查詢結果帶**幾何 provenance**（source layer + primitive 參與者 + 演算法），
  對齊 DD-2 `ValidationEvidence` 的 `source_anchor`/`threshold_provenance` 契約。

**Non-Goals**

- **不重寫**既有 `gerber-core` summary 級能力（`parse_gerber_file` 等只擴充、向後相容）。
- **不做曲線 primitive 粗略弦化近似**（arc/circle/curve 誠實跳過，除非有明確 tessellation 契約）。
- **不做 net role 判定**（那是 `design-ir_net-role-extension` plan 範圍）。
- **不引入 pcbnew / KiCad-mutating 依賴**（保持 core 純 python）。
- **不讓 LLM 參與幾何計算**（純確定性）。
- 不在本 plan 補齊全部 12 個 T-B（net-role 類與需設計意圖類另計）。

## Decisions

> IDEF0-first：本設計以 `idef0.json` 的 A1（解析 copper layer）→ A2（建 net-attributed
> primitive）→ A3（回答幾何查詢）功能分解為主軸，`grafcet.json` 描述其執行期狀態機
> （present→parse→branch: parseable→build→serve / else→fail-fast+missing-items）。以下 DD 對應該分解。

### DD-1: 消費「已解析 artifact」而非自解 gerber s-expr（比照 board_outline.py）

parser 的深解析層消費**已解析的 copper 幾何 artifact**（沿用既有 `parse_gerber_file`
產出的 draw/flash/region 事件序列 + aperture 表，materialise 成 primitive），
而非在深解析層重寫一套 gerber X3 語法解析。這與 `board_outline.py` 消費
`ir["board_outline"]["edges"]` 同構：解析職責留在既有 `contracts.py` 的 `parse_gerber_file`
（或上游 materialiser），本層只做「primitive 化 + 幾何查詢」。

**拒絕的替代方案**：在深解析層重寫 gerber 語法解析器——與既有 `parse_gerber_file`
重複、雙路徑漂移風險，違反「擴充不重寫」Non-Goal。

### DD-2: 純 python、零 pcbnew，落點 `packages/gerber-core`（core）

沿用 `board_outline.py` 的純 float 數學路徑：`edge-to-edge` 銅距 = 兩組 primitive 邊界線段間的
最短 point-to-segment / segment-to-segment 距離；`point-to-copper` = 點對所有 copper 線段最短距離；
`plane 覆蓋` = 點/區域是否落在 plane 多邊形內（ray-casting，確定性）。全部純 python、byte-identical。

**拒絕的替代方案**：引入 pcbnew/shapely 幾何庫——core 不得硬依賴 worker-only / native 套件
（AGENTS.md §4 邊界），且 pcbnew 為 KiCad-mutating。

### DD-3: 曲線 primitive 誠實跳過，未線性化不得產出 clearance（no-fabrication）

arc / circle / curve primitive 在 primitive 化階段標記為 `curve`（保留原始參數），
但**不參與** edge-to-edge / point 距離計算——比照 `edges_to_segments` 對 arc/circle/curve 的處理
（不弦化）。查詢結果的 provenance 必列出**被跳過的曲線 primitive 清單**，讓 caller 知道
「這個 clearance 數值未涵蓋曲線邊」，避免從近似邊臆造門檻。除非日後有明確 tessellation 契約
（board_outline.py 已立此先例），否則不做弦化。

**拒絕的替代方案**：對曲線做 N 段弦化近似再算 clearance——會從近似邊臆造出偏樂觀的 clearance
數值，違反 no-fabrication 天條。

### DD-4: 缺 copper layer / 無法計算 → fail-fast + 缺項清單（no-silent-fallback）

比照 `min_clearance_to_edge` 回 `math.inf` 要求 caller fail-fast：本 parser 在
①找不到 copper layer 檔、②layer 存在但零 D01/D03 幾何、③查詢所需 primitive 集合為空 時，
**不回空/不回 0/不回樂觀值**，而是回一個帶 `missing_items[]` 的顯式錯誤結果，
caller（verify-checker）必須據此判 `unverifiable`，不得當 pass。

**拒絕的替代方案**：缺 layer 時回空 primitive 集合並讓查詢回 `inf`/`0`——會讓下游誤判
「銅距無限大＝安全」或「覆蓋為零＝合規」，是最危險的靜默假 pass。

### DD-5: 每筆查詢結果帶幾何 provenance（對齊 DD-2 ValidationEvidence 封套）

查詢結果不只回 `distance`（float, mm），必附 `provenance`：
`source_layers[]`（哪些 copper layer）、`primitive_refs[]`（參與計算的 primitive id）、
`skipped_curves[]`（DD-3 跳過的曲線）、`algorithm`（如 `segment_min_distance`）。
這對映 `quality_verify-checker-skillification` DD-2 `ValidationEvidence` 的
`source_anchor`/`threshold_provenance`：clearance 數值有幾何來源可回溯，滿足 datasheet-grounded 天條。

**拒絕的替代方案**：只回裸 float 距離——下游無法把 verdict 回溯到幾何來源，
`ValidationEvidence` 封套會缺 provenance 欄位。

### DD-6: core/worker 邊界——深解析預設留 core，heavy 重解析才評估 worker

primitive 化 + 幾何查詢是純 python 數學，預設留 `packages/gerber-core`（core）。
若日後實測「大板重解析」成本過高需隔離，才依 AGENTS.md §4 評估搬 worker（經 `_forward_to_worker`），
但 **core 不得硬依賴 worker-only 套件**（monolith 缺 worker 時 summary 能力仍可用）。
本 plan 定案：深解析與查詢 API 落 core，worker 化為 backlog 觀察點而非本 plan 交付。

**拒絕的替代方案**：一開始就把深解析放 worker——會讓 core-only 場景（monolith）
拿不到銅距查詢，且違反「gerber-core 是 core 套件」的定位。

## Risks / Trade-offs

- **曲線跳過導致 clearance 覆蓋不完整** — mitigation：provenance 明列 `skipped_curves`，
  caller 據此判 `unverifiable`（誠實不完整 > 臆造完整）；日後 tessellation 契約另計。
- **net 歸屬依賴 gerber 本身缺 net 語意** — mitigation：gerber 無原生 net 名，net 歸屬以
  「連通 copper 幾何群組（connected-copper island）」為單位標識，非邏輯 net 名；
  邏輯 net role 判定明確劃給 `design-ir_net-role-extension` plan（本 plan Non-Goal）。
- **大板 primitive 化成本** — mitigation：DD-6 把 worker 化留為 backlog 觀察點；
  core 版本先確保正確性與 determinism，效能隔離後評估。
- **與既有 summary parser 雙路徑漂移** — mitigation：DD-1 深解析消費既有 `parse_gerber_file`
  產出，不另立第二套語法解析，單一真相。

## Critical Files

- `packages/gerber-core/bodesign_gerber_core/contracts.py` — 既有 summary 級 dataclass
  （`GerberGeometrySummary`/`GerberDrawSegment`/`GerberFlash`/`GerberAperture`）與 `parse_gerber_file`；
  新 copper-geometry primitive/query API 在此擴充（新增 dataclass + 查詢函式），不改既有型別語義。
- `packages/workflow-core/bodesign_workflow_core/checkers/board_outline.py` — **PARSER 範本**：
  `edges_to_segments`(29) / `point_to_segment_distance`(67) / `min_clearance_to_edge`(92)
  的純 python、消費已解析 artifact、curve-skip、無線段回 inf 要求 fail-fast 的紀律，本 parser 全程比照。
- `packages/workflow-core/bodesign_workflow_core/checkers/` — clearance/creepage checker 落點；
  對應 T-B control（`ipc-clearance-voltage`/`safety.creepage-clearance`/
  `safety.functional-spacing-formula`/`rf.antenna-keepout`）改讀本 parser 的查詢 API。
- `packages/workflow-core/.../validation_evidence.py` — `ValidationEvidence` 封套（DD-2）；
  查詢 provenance 對齊其 `source_anchor`/`threshold_provenance`。
- `specs/architecture.md` — gerber-core 能力演進 + Verification Baseline 解鎖數更新（What Changes）。
