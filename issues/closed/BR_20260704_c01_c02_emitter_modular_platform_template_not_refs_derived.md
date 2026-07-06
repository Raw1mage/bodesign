# BR_20260704 — 【消費端第二波】bodesign 的 c01/c02 emitter 預設吐「5 埠 modular-platform 骨架」，非 refs-derived — EPIC 切面 1 的 emitter 級硬證據

- **類型**：consumer-follow-up（承 `BR_20260704_EPIC_capability_inversion_refs_derived_design.md` **切面 1（無 refs-first gate → 設計從 design root 旁路）**，補上 C01/C02 emitter 級的具體證據；配合同日 `BR_20260704_aiguard_c04_consumer_input_contract_and_acceptance_case.md`）
- **來源 session**：aiguard C01/C02 deck v3 對齊（scope=aiguard，2026-07-04）
- **軸**：A（工具缺）— 缺的是「emitter 產出必須回溯 refs、不得套用內建 variant 模板」的 gate
- **嚴重度**：High（C01/C02 是 C04 placement 的**物理約束來源**；來源本身是臆造模板 → 即使 placement 引擎落地，也會照著錯的六面/插槽約束擺件）

---

## 1. 現象（含硬證據）

本 session 複查 aiguard C01-ID / C02-ME 文件層，發現**整層**建自一個 pre-deck 的「modular platform」模板，且該模板**貫穿 bodesign 自己的 emitter 輸出**：

- `Interface_Constraints.json`（c01 emitter 產物）`product_name: "aiguard (modular platform)"`、`exposed_components[0] = expansion_socket_x5`（5 面各一 universal socket）、`camera_module_fixed.placement_preference: "any socket"`、`_variant_note: "Modular platform: host with 5 universal sockets..."`、`_skeleton_note` 明說「Corrected from **generic C01 template** to the real component set」——**即 emitter 起手是 generic template，再手 patch**。
- `Mechanical_Constraints.json`（c02 emitter 產物）`product_name: "aiguard host (modular platform)"`、`component_heights[] 含 J_SOCK(x5) + U_MUX(MIPI 5→2 mux)`、`connector_openings[] 含 5 個 expansion socket A~E`、charger 標 `BQ24075`（C03 早已改 BQ25890）。
- C01 檔名本身：`aiguard__modular_platform_ID_skeleton` / `..._CMF_Direction` / `..._UIUX_Flow`——**emitter 用 variant slug 命名**。

**與 deck v3 的衝突**（deck = V1 scope authority，owner adjudication 2026-07-02）：
| emitter 吐出 | deck v3 權威 |
|---|---|
| 5 埠 universal socket 模組平台 | **三件式單一整合產品**（核心郵票 + 產品板 + 開發板），無模組插槽 |
| MIPI 5→2 mux + 相機任插一面 | **單一固定相機**，直連 dual-lane CSI-2（S9） |
| host=大樂高/模組=小樂高 | 單一密封整合盒 |
| BQ24075 | BQ25890（S8 I2C 充電/電量計） |

## 2. RCA

這正是 EPIC 切面 1（design-root bypass）的 emitter 級根因，但比 EPIC 當時的描述更具體：

**bodesign 的 c01/c02 emitter 內建一個 "modular platform" variant 模板，且以它為預設起手**，再靠 agent 手 patch 成真實元件集。問題有二：

1. **起手模板不是空的、更不是 refs-derived**：它已經預載了「5 socket + MIPI mux + host/module 大小樂高」這套**特定產品架構假設**。agent 若不逐項對照 owner 權威來源，就會把模板的架構當成需求交下去（本 session 前就是這樣，一路傳到 C03/C05/C06/C07）。
2. **emitter 無 refs 回溯 gate**：`c01_readiness` / `Interface_Constraints.json` 只檢「每個 deliverable 有非空 script / 元件集非空」，**不檢元件集是否回溯 owner refs**。所以「modular platform 模板 + 手 patch」能通過 readiness（本 session 實測 `c01_readiness` dod_ok:True，即使內容是 pre-deck 臆造）。

→ 缺口：emitter 應**從各層 `01_refs/` SSOT 生成**，而非套用內建 variant 模板；readiness 應檢「exposed_components / openings 是否每項回溯 refs」，而非只檢存在性。

## 3. 建議修復

1. **c01/c02 emitter 去除內建 variant 模板預設**：不以 "modular platform" / "generic C01 template" 起手。改為**吃 `01_refs/` SSOT**（本 session 已備妥乾淨的 `C01_物理配置SSOT.md` / `C02_Envelope開孔映射SSOT.md`，deck-derived）→ 投影成 `Interface_Constraints.json` / `Mechanical_Constraints.json`，每個 component/opening 帶 `provenance` 指回 SSOT 行。
2. **readiness 加 refs-回溯檢查**：`c01_readiness` / `c02_readiness` 應對每個 `exposed_components[]` / `connector_openings[]` 驗證 `provenance` 非空且可解析到 `01_refs/` SSOT；缺回溯則 `dod_ok:false`（fail-fast，非只檢存在性）。這直接實現 EPIC 驗收定義第 5 條（DoD 涵蓋 refs 回溯）。
3. **variant 命名去除**：emitter 不應把 `modular_platform` 這類架構假設寫進 slug/product_name；產品架構應由 refs 決定。

## 4. 影響範圍

- **bodesign**：c01/c02 emitter + 對應 readiness gate（是 EPIC 切面 1 + 切面 5 的具體落點）。
- **通用性**：任何非「模組平台」形態的產品（單一整合產品、SoM、固定功能裝置）在 bodesign 走 C01/C02 都會被內建模板汙染——這不是 aiguard 專屬。
- **與 placement 引擎的關係**：即使 `place_components`（第一波 BR）落地，它消費的 C01 六面約束 / C02 開孔若來自 modular-platform 模板，placement 仍會照錯的架構擺件。**修這個 emitter gap 是 placement 引擎能正確運作的前提。**

## 5. 驗證手段

- c01/c02 emitter 對 aiguard 乾淨 SSOT（本 session 產物）重跑 → 產出的 `Interface_Constraints.json` **不含** `expansion_socket_x5` / `U_MUX`，每個 component 帶 `provenance` 指回 SSOT。
- `c01_readiness` 對一個「元件集存在但無 refs 回溯」的假 package → `dod_ok:false`（現況錯誤地回 true）。
- 端到端：從 deck → C01 SSOT → emitter → Interface_Constraints，全程無 variant 模板注入的架構假設。

## 6. 與既有 BR 的關係

| 既有 BR | 本 BR 的補充 |
|---|---|
| `EPIC...refs_derived_design` 切面 1（design-root bypass） | 提供 **emitter 級**具體證據：不是 agent 憑空發明，是 **emitter 內建 modular-platform 模板**誘導的；並給出修法（emitter 吃 SSOT + readiness 檢回溯） |
| `aiguard_c04_consumer_input_contract_and_acceptance_case`（第一波） | 那份給 C04 placement 輸入合約；本份指出**該輸入的上游（C01/C02 約束）本身的生成器有模板汙染**，需先修才不會 GIGO |
| `no_refs_decomposition_gate_design_root_bypass` | 承其 refs-first gate 主張，落到 c01/c02 emitter + readiness 兩個具體修點 |

**aiguard 端已自行清乾淨**（C01/C02 SSOT + 兩個 constraint JSON 已 deck 對齊、gate 綠、殘留複查 0）——本 BR 是把「為什麼會髒」的根因回饋給 bodesign emitter，避免下個產品重踩。

## Resolution（2026-07-06 closed）

Spec `specs/capability/refs-first-emitters/`（living）三修全落地：

1. **emitter 去模板**：C01/C02 emit 入口掛 refs gate——無 `01_refs/` SSOT 不得起手，不再以 "modular platform" variant 模板為預設（commit c790e8b）。
2. **per-item provenance**：`Interface_Constraints.json` / `Mechanical_Constraints.json` 每個 component/opening 帶 provenance 指回 SSOT；readiness 驗 provenance 非空且可解析，缺回溯 → `dod_ok:false`（commit c790e8b + 硬化 3c27725 F1/F2/F3/F5/F6 + 0a8dc04 F4/F7）。
3. **variant 命名去除**：產品架構由 refs 決定，slug/product_name 不再注入架構假設。
