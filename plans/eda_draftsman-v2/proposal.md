# Proposal: eda_draftsman-v2

## Why

- 舊 schematic draftsman 幾何引擎（`kicad_emit.py` 2141 LOC + `composer.py` 1529 LOC + `kicad_symbol.py` 441 LOC，合計 ~4100 LOC）經多輪補丁仍無法通過人工審圖，aiguard C03 審閱 gate 三次打回：
  1. 左 pin 外接件畫進 symbol 本體（BR_20260706_left_pin_stub_orientation_blind）
  2. 只支援左右兩側 pin，違業界四邊排位慣例（BR_20260706_symbol_geometry_two_side_only）
  3. placement 無圖紙面積規劃——全部元件擠中央窄帶（~20% 利用率）、label 貼線疊字（BR_20260706_placement_no_sheet_fill）
- **RCA（為何補丁原地踏步）**：引擎是**純手搓 f-string S-expression + 手算座標**，零成熟 EDA 庫依賴。每個幾何約束（pin 邊、label 避讓、面積分佈）都要自己算座標自己拼字串，無底層抽象可依賴 → 每輪修的都是局部症狀，架構前提（兩側式世界觀、無面積規劃層）從未被質疑 → 症狀驅動補丁循環。且「單一符號畫對」與「整頁排版」兩個正交問題被混在同一條 compose→emit 鏈裡一起迭代，任何一層的錯都要整頁重產才看得到。
- 使用者裁定：放棄舊幾何引擎原始碼，重構 v2。

## Original Requirement Wording (Baseline)

- 2026-07-07 使用者：「我覺得生成原理圖是非常單純的事情，為什麼會花幾十個小時燒token原地踏步？每次修改無效有沒有檢討RCA？持續修改無效有沒有換個方法？現在我決定放棄原來的原始碼，重構一套新的。」
- 2026-07-07 使用者（分期裁決）：「我認為先解決『單一pinout圖』的繪製，再解決『多個pinout圖排列拼成一頁』的問題」
- 2026-07-06 使用者（審閱 gate）：「一個block應該四個邊都有pin腳吧？為什麼你畫的只有左右有腳」
- 2026-07-06 使用者（審閱 gate）：「C03_原理圖_01_power.pdf 不合格。你只用了圖紙的20%，其他全空白。非常沒有效率，而且字都擠在線上」

## Requirement Revision History

- 2026-07-07: initial draft created via plan-init.ts
- 2026-07-07: proposal filled from recon report（explore 棒 ses_0c5f8c279）+ 三次審閱 gate 裁決
- 2026-07-07: 使用者定分期骨架——Phase 1 單一 pinout 圖先做對，Phase 2 才做多圖排頁

## Effective Requirement Description

**兩階段架構（使用者裁定，順序不可倒）：**

1. **Phase 1 — 單一 pinout 圖繪製**（對應舊 kicad_symbol + kicad_emit 病灶）：
   - 一個元件 symbol + 其 pin 排位 + pin 外接件（電源符號/label/stub）= 一張可獨立渲染、獨立驗收的 pinout 圖。
   - 四邊 pin 排位：VDD/電源上緣、VSS/GND 下緣、訊號 IO 左右——對齊 KiCad 官方 symbol 慣例。
   - label / 電源符號零貼線疊字（render_qa SVG text-bbox 閘機檢）。
   - 單圖驗收通過（機檢 + 人工抽查）才准進 Phase 2。
2. **Phase 2 — 多 pinout 圖排列成頁**（對應舊 composer 病灶）：
   - 把 N 張已驗收的單圖排進一頁：圖紙面積規劃（sheet-fill），利用率可機檢（ink_metrics 沿用為量測）。
   - 排頁只做「擺放 + 頁間連線」，不得回頭改動單圖內部幾何——單圖是不可變積木。
3. **站在成熟外部基礎上**：引入成熟 EDA 庫（kiutils / skidl / KiCad 官方 symbol lib 等，design 階段定案），消除手搓 sexp 與手算座標。
4. **驗收雙閘為 TDD 紅線**：fidelity 連通分量保真閘 + render_qa 疊字閘（皆為保留資產、零幾何依賴）先接上，再寫幾何；每輪迭代必過雙閘才呈人工審閱。

## Scope

### IN
- Phase 1：symbol 四邊 pin 幾何 + 單一 pinout 圖 emit/render/驗收迴路
- Phase 2：多 pinout 圖排頁（sheet-fill placement）+ 頁間 wiring
- 外部 EDA 基礎庫選型與引入
- fidelity / render_qa 補獨立單元測試（現況無，靠 session fixture）
- `__init__.py` 對外 API 相容：替換 `emit_kicad_schematic` / `compose_schematic` / `emit_kicad_symbol` 三個 export，其餘 re-export 不動
- 驗收：aiguard C03 CCM 5 頁重產通過雙機檢閘 + 人工審閱 gate

### OUT
- fidelity.py / render_qa.py / ink_metrics.py（保留資產，只補測試不改行為）
- component_fetch / footprint_map / bom_export / impedance / simulate / fab / routing / layout / pcb_verify / preplace（與 schematic 幾何無關）
- BR_20260707_ccm_workflow_webdav（workflow/部署層，獨立處理）
- PCB placement/routing（本次僅 schematic）

## Non-Goals

- 不追求自動 routing 美學最佳化（wiring 以正確 + 不疊字為準，美學迭代後續再議）
- 不做舊引擎向後相容（舊產出檔不需 v2 重現 byte-level）

## Constraints

- no-fallback 天條：缺資料誠實標示，不捏造 pin/net/幾何
- 禁止症狀驅動補丁：措施無效 → 先質疑前提（code-thinker 契約）
- 排版慣例先寫成可機檢規格（合約先行），不靠事後人工看圖迭代
- **分期硬閘**：Phase 1 單圖未通過驗收前，不得動 Phase 2 排頁；Phase 2 不得反向修改單圖內部
- 保留區檔案不得被幾何重寫波及（單向依賴既有事實，須維持）

## What Changes

- `packages/eda-bridge/bodesign_eda_bridge/` 內 kicad_emit.py、composer.py、kicad_symbol.py 被 v2 模組取代（單圖引擎 + 排頁引擎兩個獨立模組）
- tests：test_composer.py / test_density_budget.py 隨砍重寫；test_bom_export.py 改接 v2 compose；test_eda_bridge.py / test_companion_render.py 保留
- `plans/eda-bridge_occupancy-ledger`（舊補丁路線）作廢或併入 v2

## Capabilities

### New Capabilities
- single-pinout renderer: 一元件一圖，四邊 pin 幾何，獨立驗收單位（Phase 1）
- sheet-fill composer: 已驗收單圖的排頁引擎，面積利用率機檢（Phase 2）
- mature-lib emit: 成熟庫序列化，消除手搓 sexp

### Modified Capabilities
- schematic compose/emit API: 介面簽名維持，實作全換

## Impact

- 影響 aiguard C03（thesmart_products）的 CCM/product 板 schematic 交付鏈
- 三份 open 幾何 BR 天然閉環（left_pin_stub / two_side_only / no_sheet_fill）
- MCP tool 介面層（services/mcp/server.py）不變
