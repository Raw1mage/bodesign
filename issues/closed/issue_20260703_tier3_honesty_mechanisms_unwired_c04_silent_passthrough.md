# BR: Tier-3 誠實機制（feasibility 分診 + si_handoff）為孤兒，未接進 C04 emit/readiness/orchestration；C04 對缺 C03 netlist 靜默續跑、無 PRD↔落板履約 gate

- Date: 2026-07-03
- Session: opencode `ses_0db8f20d1ffe9Jyjzd1sFEb1Go`（aiguard 驗收踩坑觸發的工具層審查）
- Severity: High（結構性 no-silent-fallback 天條違反；工具讓「C00 定義的晶片從未落板」的產品看起來像已交付 C04）
- Status: **RESOLVED**（2026-07-03，同 session；P1+P2 全數接線，見末段「修復紀錄」）

## 觸發情境（真實踩坑）

使用者驗收 aiguard 產品（C00 PRD 定義 STM32N657+NPU、PSRAM、NOR、microSD、Wi-Fi/BLE、
BQ24075 充電…），質疑「C04 交付物錯了——板上什麼晶片都沒放」。實查 `.work/aiguard/`：
- C03-EE **完全不存在**（無原理圖、無 netlist、無 BOM）。
- C04-Layout **只有** `Layout_Constraints.json` + `Placement_Constraints.md`。
- C00 定義的 NPU/SRAM/NOR **一顆都沒落板**——但沒有任何工具訊號把這個狀態標為「未完成/blocking」。

## 現象（含硬證據，均 grep 實證）

**① feasibility 分診是孤兒。** `classify_product_feasibility`（`feasibility.py`）能正確把
aiguard 判為 firm Tier-3（HDI/0.5mm BGA/8 層/12 高速net/RF）。但：
```
grep -rn classify_product_feasibility packages/ services/ | 排除 def/__init__/test → 零筆
```
生產碼**從不呼叫它**。tier 從不自動計算、從不強制標記在任何交付物上。feasibility-triage.md
規則明令「declare the tier up front / state it in the C01 handoff / package README」——但沒有
任何 emitter/readiness 這樣做。

**② si_handoff（Tier-3 SI 約束交手）是孤兒。** `emit_si_constraint_export`（`si_handoff.py`）
是為 Tier-3「乾淨交手 pro-EDA」寫的完整 library。但：
```
grep -rn emit_si_constraint_export packages/ services/ | 排除 def/__init__/test → 零筆
```
生產碼零呼叫。Tier-3 產品該產出的 SI 約束集，工作流沒有任何路徑觸發它。

**③ C04 emitter 對缺 C03 靜默續跑。** `c04_layout_constraints.py:196-198` 註解白紙黑字：
> "absent upstream data simply leaves a constraint group empty and pending."

`emit_c04_layout_package(c03=None)` 在沒有 C03 netlist 時**照樣產出** `Layout_Constraints.json`
+ `Placement_Constraints.md`，不 fail-fast、不提示「C00 定義的元件尚未經 C03 落成電氣連接」。

**④ C04 readiness 誤導性綠燈。** `assess_c04_layout_readiness`（同檔:221-255）在 constraints
群組非空時回 `status="layout_constraints_drafted"`（聽起來像正常進度）。全函數**不提** tier /
feasibility / netlist / C00 main_components 履約。它只數「約束群組非不非空」，把「上游電氣全空、
晶片從未落板」報成 drafted 而非 blocking。

## RCA（三層失效鏈，與上一輪 prd_bom_crosscheck BR 同源但更上游）

1. **誠實機制存在但未接線**：feasibility + si_handoff 都寫好且有 test，卻是 library-only 孤兒，
   沒接進 emit/readiness/orchestration 主幹。宣稱能力（tier declaration、Tier-3 clean handoff）
   在 code 存在，在 runtime 從不發生。
2. **C04 無「PRD→落板履約」gate**：上一輪補的 `prd_bom_crosscheck` 驗的是「netlist 元件 vs PRD
   main_components」，但它跑在**有 netlist**的前提上。當 C03 根本沒做、netlist 不存在時，C04 仍能
   產出約束文件而不觸發任何履約檢查——履約 gate 沒有覆蓋「C03 缺席」這個更上游的洞。
3. **readiness 只驗自身群組非空，不驗跨階段因果**：C04 readiness 不問「我的上游 C03 電氣連接在
   嗎？C00 定義的元件落板了嗎？」——違反 SKILL.md「dod_ok 應驗 GUIDE Required-deliverable +
   跨階段 blocker」的精神，也違反 repo 天條 §2.1 no-silent-fallback。

## 建議修復（分優先序）

- **P1 接線 feasibility**：`emit_c04_layout_package` / `assess_c04_layout_readiness` 讀
  C00/C03 signals 跑 `classify_product_feasibility`，把 tier + c04_target 寫進交付物與 readiness
  輸出；Tier-3 時 readiness 明示「C04 交付上限=placement+SI 約束，繞線交 pro-EDA」。
- **P1 C04 缺 C03 fail-fast**：`emit_c04_layout_package(c03=None)` 或 c03 無 netlist 時，
  回顯式 blocking 狀態（如 `C04_UPSTREAM_C03_MISSING`）+ 缺項清單，而非靜默產空約束群組。
- **P1 履約 gate 覆蓋 C03 缺席**：readiness/gate 加一條「C00 main_components 是否經 C03 落成
  netlist 元件」的檢查；C03 缺席 → BLOCKING，不報 drafted。
- **P2 接線 si_handoff**：Tier-3 產品的 C04 路徑自動觸發（或 readiness 明示 next_step 指向）
  `emit_si_constraint_export`，讓 Tier-3 的正解交付物真的被產出。
- **P2 readiness 措辭**：`layout_constraints_drafted` 在上游空時改為 blocking 語意，避免
  「drafted」被誤讀為「已交付草案」。

## 影響範圍

- 所有 Tier-3（及任何 C03 未完成就進 C04）的產品：C04 會產出看似交付、實則晶片從未落板的
  「約束文件」，且無工具訊號揭示缺口。
- 誠實模型可信度：feasibility/si_handoff 這兩個「展示可靠度」的核心機制形同未部署。

## 驗證手段

- 建一個只有 C00（含 main_components）、無 C03 的專案 → `emit_c04_layout_package` 應回
  blocking + 缺項清單，`assess_c04_layout_readiness` 應回 blocking 且輸出含 tier=3 + Tier-3
  交付邊界，不得回 `layout_constraints_drafted`。
- Tier-3 專案跑 C04 readiness → next_step 應指向 SI 約束交手（si_handoff），而非泛泛
  「hand to layout engineer」。
- 迴歸：Tier-1 完整專案（有 C03 netlist）行為不變，仍正常 drafted → routable。

## 備註（scope 邊界）

本 BR 是 **bodesign 工具層**缺陷，屬本 repo。aiguard 的 C03→C04 電路設計實作是**產品交付物**，
屬產品 repo，不在此 session 進行（使用者已明確界定）。本 session 僅落此 BR 回饋工具層。

## 修復紀錄（2026-07-03，RESOLVED）

全數在 `packages/workflow-core/bodesign_workflow_core/c04_layout_constraints.py` + `skills/bodesign/scripts/gate.py` 接線：

- **P1 履約 gate（③④ 治本）**：新增 `_assess_upstream_fulfilment(root)` — 跨階段 disk-of-truth
  檢查（C03-EE/ 存在、`*.net` netlist 存在=C00 元件已落成電氣連接、Mechanical_Constraint_Export.json
  存在），產出顯式 `gaps[]`。缺 netlist 時 `assess_c04_layout_readiness` 回
  `status=blocked_upstream_c03_missing`（不再 `layout_constraints_drafted`），emit 的
  `Layout_Constraints.json` 帶 `state=blocked_on_upstream`。**與 tier 正交**（無 netlist 一律 blocking）。
- **P1 接線 feasibility（①）**：`emit_c04_layout_package` / `assess_c04_layout_readiness` 新增
  `feasibility_signals` optional arg，跑 `classify_product_feasibility` 標 `feasibility_tier` +
  `c04_target`。**signals 缺 → tier=not-assessed，不臆測**（no-silent-fallback）。
- **P2 接線 si_handoff（②）+ readiness 措辭**：Tier-3 且上游齊備 → `status=`
  `layout_constraints_drafted_tier3_handoff`，`next_step` 明示呼叫 `emit_si_constraint_export`；
  上游空時走 blocking 語意（drafted 不再被誤讀為「已交付草案」）。
- **驗證**：`tests/test_c04_layout_constraints.py` 補 4 測（缺 netlist→blocking、tier-3→SI handoff、
  no-signals→not-guessed、有 netlist→正常 drafted）；C04+feasibility+si_handoff+readiness+
  package_readiness+guide_dod 共 41 tests 綠。4 個既有失敗（test_c02_* loader import、httpx
  missing）為 pre-existing baseline，與本輪零交集。
- **架構同步**：`specs/architecture.md` C04 段已補此 gate 條目。
