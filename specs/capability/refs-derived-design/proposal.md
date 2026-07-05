# Proposal: capability_refs-derived-design

## Why

- bodesign 目前的 C00~C04 是「**從薄空氣生成 artifact**」範式：它假設物理決策、placement、腳位、元件清單都已由上游人工凍結，但**它自己既不提供產生這些決策的工具，也不強制設計必須回溯 owner 的權威 refs**。結果 agent 被迫憑空發明，產出「看似完整、實則造假」的交付物。
- 硬證據（aiguard N6_X01 真實模組）：owner 權威來源（說明文件 PDF + 正式需求書 PPTX）= 11 元件 / Stamp Hole X1(18)+X2(18)=36 pad dual-edge；agent 憑空發明版 = 8 元件（漏 WiFi/BT LBEE5KL1YN、Ethernet PHY RTL8211FI-CG、IMU LSM6DSMTR）/ 三面 28-pin。**座標、腳位數、元件清單全錯**。
- 這不是零星缺口，是**同一個範式錯誤的多個切面**（燒掉數十輪暴露）。aiguard C00-C07 專案已 **BLOCKING 暫停**，等 bodesign 完成核心能力翻轉後回來。
- 天條對齊：refs-derived 是「fail-fast + 顯式報錯 + 缺項清單」哲學的直接落地（repo 天條 2「No fabrication」、天條 1「No silent fallback」），把「憑空生成的假完整」擋在 gate 前。

## Original Requirement Wording (Baseline)

- 來源 session（aiguard scope）收斂為總綱 BR：「bodesign 必須翻轉為 refs-derived 設計範式：先逆向拆解 owner 權威來源 → 建各層 SSOT → 下游只能消費、不能發明。」
- 使用者本 session 決策：「先開完整 plan（plan-builder）涵蓋全 7 BR」（EPIC 範式翻轉，非逐點修補）。

## Requirement Revision History

- 2026-07-04: initial draft created via plan-init.ts
- 2026-07-04: filled from EPIC BR 總綱 + 6 切面分項 BR + 2 emitter/consumer BR（8 筆 session BR triage 結論）

## Effective Requirement Description

翻轉完成 = 以下 7 項全部成立（EPIC 驗收定義），才可讓 aiguard 回來繼續：

1. **refs-first gate 存在且強制**（切面 1，範式核心）：無各層 `01_refs/` SSOT 時，下游生成 verb **fail-fast 拒絕**（非 warn）；SSOT 必須可追溯到 owner 權威來源（PDF/PPTX），非 agent 自撰。
2. **約束驅動 placement 引擎存在**（切面 2）：C04 能消費 C01 face-layout（哪邊/哪面）+ C02 envelope/開孔約束產生 placement；連接器面向/邊緣是**上游凍結的物理約束，非 C04 自由度**（「USB 插不進去」根因）。
3. **castellated / stamp-module 原生 verb 存在**（切面 2/3）：不需徒手 pcbnew scripting；castellated PTH 半孔走安全的 S-expression text-layer 注入 wrapper。
4. **lifecycle 方向性工具化**（切面 4）：下游 stage 的 verb 以上游凍結約束 JSON（face-layout、envelope、mechanical-constraint）為**必要輸入**，缺上游約束則拒絕生成。
5. **DoD 檢查涵蓋 refs 回溯**（切面 5）：交付驗證不再只看表面存在性/state，而檢查是否回溯真實 refs；修既有 6 裂縫（status.json location、C00 DoD RF 不對稱、compose NC flaky、netlist line-count misreport、workers infra gap、PRD/BOM crosscheck gap）。
6. **工具介面摩擦修掉**（切面 6）：gate.py stdout 乾淨（✅ 已修）、ragbase id 契約 --help 直覺化、query 結果結構穩定 accessor。
7. **知識介面走 KB skill**（切面 7）：翻轉後能力透過 `bodesign-kb` skill 暴露給客戶端工作 agent，而非要求它們直接懂 schema。

## Scope

### IN

- **refs-decomposition gate**：C00-refs 逆向拆解 gate + 各層 `01_refs/` SSOT 契約 + 下游 verb fail-fast 前置檢查。
- **約束驅動 placement 引擎**：消費 C01 face-layout + C02 envelope 產生 placement（與既有 `quality_deterministic-preplacement` plan 互補——那管「電氣感知擺件品質 vs grid」，本 EPIC 管「約束來源與面/邊綁定」）。
- **castellated / stamp-module 原生 verb** + 安全 board-surgery wrapper（禁止徒手 pcbnew scripting 當隱含路徑）。
- **lifecycle 方向性鏈**：下游 verb 讀取上游凍結約束 JSON 作必要輸入。
- **DoD gate 修補**（6 個 20260703 裂縫）+ **ragbase 介面摩擦**修。
- **`bodesign-kb` skill** 暴露翻轉後能力。
- **驗收案例**：aiguard 已建 5 個各層 SSOT（C01 物理配置 / C02 envelope / C03 元件腳位 / C04 物理約束 / C05 韌體腳位）為第一個真實回歸案例。

### OUT

- **aiguard 專案本身內容**（那是 bodesign 的 consumer / 驗收案例，非本 plan 交付物）。
- **RL/ML 擺件、多板型泛化調參、autorouter 更換**（既有 preplacement plan 已列 OUT，本 EPIC 沿用）。
- **既有 `quality_deterministic-preplacement` plan 的內部演算法**（該 plan 獨立推進，本 EPIC 只定義它消費的約束介面）。
- aiguard 端 source gap 的最終裁決（Ethernet 保留與否、envelope 收斂數值、V1 PPTX 重讀）——翻轉後以工具鏈一併解，非本 plan 設計對象。

## Non-Goals

- 不追求商用 EDA 級擺件品質；目標是「每個座標/腳位/元件可追溯到 SSOT，SSOT 可追溯到 owner 權威來源」。
- 不做互動式手動擺件/refs 編輯 UI。
- 不在本 plan 內重寫 aiguard——只把它當第一個驗收案例跑通全鏈。

## Constraints

- **No silent fallback / No fabrication（repo 天條 1/2）**：缺 refs SSOT → fail-fast + 缺項清單，不以預設值/第一個可用值/泛用模型續跑。
- **確定性驗證哲學**：refs 回溯鏈必須可重現、可追溯（每個數字 → SSOT → PDF/PPTX 錨點）。LLM 只做上游抽取/裁決，gate 與比對不參與。
- **Core vs Worker 邊界（repo AGENTS.md §4）**：refs gate / 約束組裝屬 core（pure-python）；placement / castellated / board-surgery 屬 ee worker（重 toolchain）。
- castellated PTH 半孔走 S-expression text-layer 注入，禁止 `fp.Reference().SetTextSize()` 等已知 segfault path。
- 規則值/約束值必須帶來源錨點；無錨點不硬編碼。

## What Changes

- `packages/workflow-core/`：refs-decomposition gate + 各層 `01_refs/` SSOT 契約 + lifecycle 上游約束讀取。
- `packages/eda-bridge/`（ee worker）：約束驅動 placement 引擎 + castellated/stamp verb + 安全 board-surgery wrapper。
- `services/mcp/server.py`：新 verb 的 handler + schema（refs gate、placement、castellated/stamp）。
- DoD gate 修補：`skills/bodesign/scripts/gate.py` DoD 檢查段 + 6 個 20260703 裂縫對應處。
- ragbase producer/query 介面 --help 契約 + 穩定 accessor（specbase repo 協調）。
- 新 `skills/bodesign-kb/` skill 暴露翻轉後能力。

## Capabilities

### New Capabilities

- **refs-decomposition gate**：逆向拆解 owner 權威來源，把各層資料落 `01_refs/` SSOT；SSOT 不存在則下游 verb fail-fast 拒絕。
- **constraint-driven placement**：消費 C01 face-layout + C02 envelope，連接器綁定其面/邊，C04 不可任意移動。
- **castellated / stamp-module verb**：原生半孔 / stamp 模組生成，安全 board-surgery wrapper。
- **lifecycle constraint chain**：下游 verb 以上游凍結約束 JSON 為必要輸入。
- **bodesign-kb skill**：翻轉後能力的知識介面。

### Modified Capabilities

- **C00~C04 生成 verb**：全部前置 refs-first gate（無 SSOT 拒絕執行）。
- **DoD 檢查**：從「表面存在性」升級為「refs 回溯驗證」。
- **gate.py / ragbase 介面**：stdout 契約（已修）、id/query 契約直覺化。

## Impact

- **bodesign**：C00~C04 生成範式重構（非單點修補）——新增 5 類能力、修 DoD gate 與工具介面摩擦。
- **aiguard 專案**：暫停中；翻轉達標後以其 5 個 SSOT 為第一驗收案例回歸。應丟棄 place1~place5 五版憑空 placement。
- **既有 `quality_deterministic-preplacement` plan**：本 EPIC 定義其消費的約束介面，兩者互補推進。
- **證據鏈**：aiguard N6_X01 PDF / 正式需求書 PPTX 為 refs 回溯終點；ragbase `workflow.preplacement-deterministic` 為 placement 骨架 SSOT。
- **統攝 BR**：`BR_20260704_EPIC_capability_inversion_refs_derived_design` + 6 切面分項 + 2 emitter/consumer BR。
