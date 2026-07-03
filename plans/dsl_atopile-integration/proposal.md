# Proposal: dsl_atopile-integration

## Why

- bodesign 目前的電路生成路徑（C03 原理圖、C04 佈局）由 LLM 直接產出 KiCad 工件，缺一層「編譯期正確性把關」：連接性、單位、公差、約束在進 KiCad 前沒有靜態驗證，錯誤要到 ERC/DRC（甚至更晚）才暴露。
- 使用者需求：引入一套**宣告式電路描述 DSL 標準**，讓腳本正確性在編譯期就被機器驗證，再落地 KiCad pipeline。
- 選型調查（2026-07-03，比較 atopile / SKiDL / circuit-synth / tscircuit）定案 **atopile**：唯一具備真正編譯期驗證（單位型別 + 公差區間運算 + `assert` 約束求解 + 選料可行性檢查）且 KiCad 原生（直接寫 `.kicad_pcb`）的開源選項（MIT、3.5k★、活躍維護）。

## Original Requirement Wording (Baseline)

- 「如果tcl to pcb layout有好的開源compiler，整合進來有助腳本的正確性，再轉kicad的cli腳本」
- 「同意，這就是我需要的，一套標準。」（採納：以既有開源宣告式 DSL 取代不存在的 TCL compiler 路線）

## Requirement Revision History

- 2026-07-03: initial draft created via plan-init.ts
- 2026-07-03: 選型定案 atopile（使用者於 question gate 選「採用 atopile，開 plan spec」）

## Effective Requirement Description

1. 將 atopile 編譯器整合進 bodesign，作為 C03 電路生成的**驗證前端**：AI 生成 `.ato` 原始碼（帶 units / tolerances / assert 約束）→ `ato build` 編譯期把關 → 產出 `.kicad_pcb` 進入既有 C04 pipeline（`route_net2pcb` / `pour_planes` / `layout_drc_gate`）。
2. 編譯期驗證成為 bodesign 的**第五層信任證據**（約束求解證明），與既有 ERC/DRC、對照組交叉檢核、SPICE、EMC 並列。
3. atopile toolchain 安裝於 **ee worker** 容器（重依賴隔離原則），core 僅做 forwarding；monolith 環境缺 atopile 時顯式報錯（no silent fallback）。
4. 選料來源相容性：確認 atopile parametric picking 能否接 bodesign Component Vault / 離線運作；不可行時 fail fast 並回報缺項，不靜默退回 cloud registry。

## Scope

### IN
- ee worker 容器安裝 atopile toolchain（Dockerfile.ee）
- 新 MCP 工具：`.ato` 原始碼 build / 編譯期驗證 / 錯誤回報（結構化缺項清單）
- `ato build` 產物接入既有 C04 pipeline 與 readiness 追蹤
- atopile registry ↔ Component Vault 相容性調查與整合點設計
- 編譯期驗證證據納入 verification 報告（第五層信任證據）

### OUT
- tscircuit / SKiDL / circuit-synth 整合（調查已排除；SKiDL 僅列為未來 netlist 備援選項）
- 自動佈線（atopile 不做 layout；維持既有 C04 路徑）
- `.ato` 語言的 LLM 生成品質優化（prompt engineering 屬 bodesign skill 層，另案）
- 中期「spec→ato→kicad 與 spec→kicad 雙路徑交叉驗證」（列為後續 extend）

## Non-Goals

- 不取代既有 C03 直接生成 KiCad 原理圖的路徑；atopile 是**新增的**驗證前端選項，兩條路徑並存。
- 不自建 TCL→PCB compiler（原始提問路線；經討論確認無開源生態，已放棄）。

## Constraints

- No silent fallback 天條：atopile 不可用、選料無解、約束不滿足 → 顯式報錯 + 缺項清單。
- ee worker 隔離：core 不得硬依賴 atopile 套件。
- Datasheet-grounded：`.ato` 內的元件電氣參數仍須走 `bodesign_datasheet_lookup` / vault 證據鏈。
- atopile docs repo 已 archived（2026-04）；整合時以主 repo 與實測行為為準，pin 版本（v0.14.x 系列）。
- 選料 cloud registry 依賴需評估離線 / 自架場景（bodesign 可獨立對外營運）。

## What Changes

- `Dockerfile.ee`：新增 atopile toolchain。
- `services/mcp/server.py`：新增 `_h_*` handler + schema（ato build / validate 工具，core→ee forwarding）。
- `packages/workflow-core`：C03 生成流程新增 ato 路徑分支與 readiness 欄位。
- verification 報告 schema：新增 constraint-solving 證據層。

## Capabilities

### New Capabilities
- `ato_build`（暫名）：編譯 `.ato` 專案，回傳編譯期驗證結果（單位/公差/assert/選料）與 `.kicad_pcb` 產物路徑。
- constraint-evidence：verification 報告的第五層信任證據（約束求解證明）。

### Modified Capabilities
- C03 電路生成：新增「宣告式 DSL 前端」入口，與既有直接生成路徑並存。
- C04 pipeline：接受 ato build 產出的 `.kicad_pcb` 作為輸入。

## Impact

- 受影響：`Dockerfile.ee`、`services/mcp/server.py`、`packages/workflow-core`（C03/C04 邊界）、readiness/verification schema、`specs/architecture.md`（新資料流）。
- 營運：ee worker image 變大（atopile + 依賴）；離線部署需解決選料來源。
- 文件：bodesign skill（C00-C07 workflow 腦）需新增 ato 路徑指引（另案同步）。
