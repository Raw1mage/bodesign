# Proposal: knowledge_c03-ee-design-kb

## Why

- 使用者盤查提問「bodesign 的 C03 電路設計層是否缺乏功能和知識」。實測後定性：**功能不缺、知識(KB)有真實不對稱缺口**。
- `bodesign_kb_query`（ragbase FTS）對 C03 EE 設計術語幾乎全 **0 命中**：`regulator / LDO / buck / decoupling / signal integrity / return path / crystal / oscillator / EMC / EMI / derating / θJA` verified 層皆查無。唯一沾邊的 `EMC ground plane return path` 只回 1 筆 partial（且屬 C04 layout-scoring-rubric）。
- 對照組——**C04/DFM 知識在 KB 裡很厚**：`concept.pcb.*`、`control.dfm.ipc-trace-width-current`、`control.pcb.ipc2221-clearance`、`control.safety.functional-spacing-formula`、`pcb-layout-rules-compendium.md`（P1–P14+ 帶數值 + machine-checkable + IPC canon）皆 verified/partial 可查。C03 的電氣設計判斷層在同一個 KB 內卻是空的。
- 結果：cold-context 的 agent 在做 C03 時，`kb_query` 一顆 regulator/decoupling/SI 規則都撈不到，只能回退去讀散文 reference 檔——KB 作為「被動資產、靠調用拉到眼前」的價值在 C03 這一段沒有兌現。

## Original Requirement Wording (Baseline)

- "bodesign的C03電路設計層是否缺乏功能和知識"

## Requirement Revision History

- 2026-07-23: initial draft created via plan-init.ts
- 2026-07-23: 盤查定性後收斂為「補 C03 EE 設計知識層 KB」——功能面確認不缺，本 plan 只處理知識缺口。
- 2026-07-23: **使用者把問題升級**（兩問）。深度診斷（`research/c03-capability-diagnosis.md`）後確認缺口分**兩層**，本 proposal 原始範圍只涵蓋缺口 A：
  - **缺口 A（知識可查詢）**：C03 EE 設計規則進不了 `kb_query`（萃取檔已在 disk 未 ingest）。**本 plan 目前 scope。**
  - **缺口 B（設計合成能力）**：pin-obligation → 輔助被動件/RC/LC/分壓/功能電路的**合成**目前零工具化、純 LLM reasoning，撞上 bodesign「LLM 不做設計/驗證」核心哲學。**待使用者定調是否立案**，非本 plan 現有範圍。
  - Q1 架構層已查證：串 KB = 改 ragbase（opencms 早 drop，不涉入）。

## Effective Requirement Description

1. 把**已存在但未進可查詢 KB** 的 C03 EE 設計知識，蒸餾/ingest 成 graded（confidence + source_weight）、可 `bodesign_kb_query` 命中的 `control.*` / `concept.*` 物件。
2. 驗收標準 = C03 核心設計術語（regulator/decoupling/SI/crystal/derating/protection）在 `bodesign_kb_query` 至少能命中對應的 verified/partial 規則，且每筆帶來源錨點（no-fabrication）。
3. `ee-design-advisory.md` 未覆蓋、且無來源可蒸的主題，以**誠實掛帳**（UNVERIFIED + 需何來源）記錄，不臆造、不蒸空殼。

## Scope

### IN

- **Ingest 既有 verified-grade 萃取檔**（磁碟已存在、FTS 查無 → 未 ingest 進 ragbase store）：
  - `specs/quality/verify-knowledge-hardening/research/batch14`：`control.protection.fuse-ptc-derating`、`control.power.decoupling-pdn-strategy`（Littelfuse Fuseology / TI SPRABV2 原廠原文級）
  - `batch15`：`control.protection.mov-surge-selection`、`control.protection.ntc-inrush-selection`（Littelfuse Varistor AN / Vishay-Ametherm）
  - `batch18`：`control.si.stackup-impedance-control`、`control.si.crystal-oscillator-layout`（Multi-CB / NXP AN1706 + Microchip AN826）
  - `batch12` family U 中屬 C03 電氣的 `control.protection.reverse-polarity-layout`（onsemi AND90146 + MPS RPP）
- **升格已在 KB 但卡 `confidence: todo` 的 C03 distill 資產**：`kicad-schematic-review-skill` 的 checklists（`dcdc.md` / `mcu_adc.md` / `current_sensing.md` / `power_entry_inrush.md` / `half_bridge_gate_drive.md`）、`datasheet_summary_template.md`——裁決哪些可升 verified/partial、哪些留 todo。
- **蒸餾 `ee-design-advisory.md` prose 的可判定規則**：regulator 拓撲選型（LDO/buck/boost 適用條件 + watch）、decoupling cascade、SI 需求數值（Z0 / 3W / λ/10 / termination）、thermal θJA sizing、RF link budget——成為可 kb_query 的 `concept.*`/`control.*`（保留 heuristic vs datasheet-backed 的 provenance 分級）。
- **誠實掛帳缺口清單**：batch14/15 已標的 UNVERIFIED（PTC hold/trip、GDT/TVS 協調等）沿用，補記 C03 尚無來源的主題。

- **【新接入 BR_B】C03 passive-completeness gate**（`BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate.md`，severity high）——這是選項 4「用 A 織密 B 校驗面」的**具體落地**，也是診斷「缺口 B」在守哲學前提下能動的那一子集：
  - **問題**：consumer(aiguard C03) 實測——composer 忠實畫出 pinout-only spec，ERC/fidelity/check_c03 全 PASS，卻是 STM32N657 零去耦、memory bus 零 pull-up/termination、radio 零 matching 的不可用板。根因=method 是 load-bearing prose、無 machine backstop；沒有任何 gate 斷言「每顆 active IC 有否帶必要被動件」。
  - **修法（守哲學）**：新增一道 passive-completeness 校驗閘——把 `pinout-to-circuit-method.md` 的 9-class per-pin obligation 表機器投影到已組出的圖上（power pin→≥1 去耦、clock→load cap、boot-strap→定態 pull…），零支援的 active IC = HARD FAIL 或顯式 waiver。**這是校驗（審查已組出的圖）非合成**，不代 LLM 決定要哪些件；gate 判準 threshold 正好引用 BR_A 修好後可 kb_query 的 KB 規則（decoupling 每 2 pin 0.1µF、crystal load cap 公式、I²C pull-up 區間）。
  - **seam 由 bodesign 架構裁決**（三候選）：`compose_schematic(passive_completeness=True)` 回 `passive_gaps[]` / `analyze_schematic` 新規則 `PC-001(high)` / `check_c03` R5。統一 invariant：已組出的 active IC 零必要被動件 = 非靜默 PASS。
  - **必須支援 honest-subset waiver**：interface-subset / reverse-eng baseline 可用 `Netlist_Status.md` 宣告 documented gap + provenance waiver 通過，不強塑被動件到刻意 partial 的交付物。

### OUT

- **不新增任何 C03 執行工具/功能**——功能面已確認完整（compose_schematic+fidelity、ato_build、analyze_schematic、prd_bom_crosscheck、check_c03、emit host/partition diagram、simulate、spice_model_card、mechanical bridge）。
- **不碰 C04 layout / DFM KB**——那一段已厚，非本案缺口。
- 不改 stage guide 的 SOP 流程（除非 ingest 後需在 GUIDE 補一行「設計規則已可 kb_query」指引）。
- 不做網路新爬取為主線；以 recall-before-crawl 為原則，只在既有素材確有缺且使用者批准時才補爬。

## Non-Goals

- 不追求「把整個 EE 教科書灌進 KB」；聚焦 bodesign C03 SOP 實際會用到的設計判斷點。
- 不把 heuristic/rule-of-thumb 偽裝成 datasheet-backed 規格值（provenance 分級鐵律，對齊 `pcb-layout-rules-compendium.md` 的 `[primary]`/`[fab]`/`[rot]` grade）。

## Constraints

- **no-fabrication 天條**：每筆 ingest 的規則必帶逐字來源引文 + 出處錨點；查無來源標 UNVERIFIED。
- **provenance 分級**：verified（原廠原文級/標準轉述）vs partial（二手/curve-fit）vs todo（未裁決）——ingest 時如實帶 confidence + source_weight。
- ingest 走 plan-builder 的 `ragbase_ingest_source` / `register_asset` / `record_extract` / `distill` producer 鏈（`producer.ts --repo <bodesign abs>`），不手改 ragbase sqlite。
- scope 一律帶 `repo:/home/pkcs12/projects/bodesign`（否則跑去 opencode repo）。

## What Changes

**使用者定調 = 選項 4（補 A + 用 A 織密 B 的校驗面）。雙軌 scope：**

### 軌 A：KB ingest（知識可查詢）
- ragbase KB store（`.specbase` / ragbase）新增/升格一批 C03 EE `control.*`/`concept.*` 物件，使 `bodesign_kb_query` 對 C03 設計術語有 verified/partial 命中。

### 軌 B：用 A 織密「輔助件完備性」反向校驗（守哲學，非合成）
- ingest 後，讓 C03 的 review / analyzer 流程能**引用可查詢規則**做更硬的反向檢查：例如 decoupling 每 2 power pin 0.1µF / 每 10 pin bulk、crystal load cap `2·(CL−Cstray)`、I²C pull-up 區間、fuse 25% derating ——當作「輔助件是否齊備」的機檢依據。
- **邊界釘死（守哲學）**：這是《校驗一張已存在/已起草的圖的完備性》，**不是合成**（不代 LLM 決定要哪些件）。缺口 B 的合成面仍存、待日後定調；本 plan 只把 A 的知識用來把現有校驗網織密，不跨哲學紅線。
- （可能）`stages/c03-ee/GUIDE.md` 或 `references/ee-design-advisory.md` 補一行指引：設計規則現可用 `bodesign_kb_query` 撈取；step 5 輔助件完備性檢查可引 KB 規則。
- `specs/architecture.md` 若 KB 覆蓋圖譜屬架構觀測點，收尾時同步；否則註記 Verified (No doc changes)。

## Capabilities

### New Capabilities

- **C03 EE 設計知識可 kb_query**：regulator 選型 / decoupling PDN / 保護電路(fuse/MOV/NTC/RPP) / SI 需求數值 / stackup 阻抗 / crystal layout / thermal sizing 成為 graded、帶來源的可檢索知識，而非只存在於散文 reference。

### Modified Capabilities

- **`bodesign_kb_query` 對 C03 段的召回率**：從近乎 0 提升到能命中核心設計規則。
- **kicad-schematic-review distill 資產**：從 `todo` 裁決升格為可用的 verified/partial 設計規則（或明確保留 todo 並記原因）。

## Impact

- 受影響知識庫：ragbase / `.specbase` KB store（bodesign repo scope）。
- 受影響檔案（唯讀來源）：`specs/quality/verify-knowledge-hardening/research/batch{12,14,15,18}.md`、`skills/bodesign/stages/c03-ee/references/ee-design-advisory.md`、`~/.cache/kb-distill-c/kicad-schematic-review-skill/**`。
- 受影響使用者/agent：未來所有走 C03 stage 的任務（cold-context 也能 kb_query 撈到設計規則）。
- 不影響任何 C03 執行工具、C04+ 流程、送廠閘。
