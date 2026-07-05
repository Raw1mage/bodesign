# Proposal: quality_bodesign-skill-disambiguation

## Why

使用者的核心信念（本 plan 的第一性原理）：**agent 的失誤，根因通常不在 agent「不小心」，而在文字層的缺陷**——skill / system prompt 的模棱兩可用語、誤導的命名、宣稱某契約卻沒寫失效邊界；甚至原始碼裡容易讓人誤會的變數命名。runtime（我們）要負責，不是怪 agent。

這信念有**新鮮的實證**。上一節（BR_20260705 三修 + RS 覆盤）三個失誤全部落在文字層，無一是「agent 不小心」：

1. **誤導命名**：`resolve_vault_dir(explicit_path)` 內部是 `env or explicit_path`，名字暗示「explicit 優先」實際「env 優先」→ 直接誘發 no-silent-fallback 天条 bug（vault D2）。
2. **過度信任的契約宣稱**：`server.py` 註解「mirrors 1:1 (drift-guarded by tests)」沒警告「XDG **mirror** 這份複本會過期」→ 上一個 agent 誤判假 drift（landing_verb）。
3. **輸出契約無自我說明**：批次工具沒說「先讀 `ok` 再讀 `skipped`」→ 我讀截斷輸出就誤判整批失敗（RS 自我更正）。

同一時間，`skill-creator` 剛升級出 **Engineer Mode**——針對「可驗證硬知識」的工程等級規格（UNIT shell + 六種 knowledge-kind core + SPEC-REF gate + assertion 化 eval）。bodesign 的 skills 正是它的目標體質：裝的是 KiCad 規則、電氣數值、DRC、標準符規、時序預算——**可驗證的硬知識，裸數值就是幻覺溫床**。

兩件事撞在一起 → 趁機把 bodesign 最容易誤導 agent 的 skill 語句，用 Engineer Mode 標準系統性重構。

## Original Requirement Wording (Baseline)

- "任何agent的失誤都是runtime的責任，不是工具沒寫好，就是說明沒寫好。尤其是我們的skills或system prompts常常有一些模棱兩可的用語，甚至原始碼裏也有一些容易讓人誤會的變數命名方式。昨天我們才剛剛改好skill-creator讓它能產出工程等級的skills。我覺得可以趁這個機會把容易產生問題的system prompts/skills重構一下"
- 範圍決策（澄清問答）：先從 **bodesign 本 repo 的 skills（62 個 md）** 下手；正式立成 **plan-builder spec**。

## Requirement Revision History

- 2026-07-05: initial draft created via plan-init.ts
- 2026-07-05: 依使用者澄清鎖定範圍 = bodesign/skills；採 Engineer Mode 為目標品質標準

## Effective Requirement Description

1. 稽核 bodesign `skills/` 語料庫（62 md / ~17751 行），定位「會誤導 agent 做出錯誤推論」的語句/命名，產出**誤導源清單**（檔:行 + 誤導類型 + 具體誤導推論 + 修法方向）。
2. 挑 1 份高流量、誤導密度高、硬知識為主的 skill，重構成 **Engineer Mode 範本**（UNIT shell + 對應 core + SPEC-REF gate）。
3. **驗證範本確實降低誤判**（Engineer Mode 的 with-skill vs baseline eval loop + assertion 化 DONE-WHEN）。
4. 把驗證過的 pattern **推廣**到其餘高誤導密度 skill。
5. 沉澱可重用的「反誤導寫作規範」（哪些 pattern 該改、怎麼改）進 KB。

## Scope

### IN

- `skills/bodesign/**/*.md`（SKILL.md / stages/c0X-*/GUIDE.md / engines/kicad|kidoc/**/*.md / references/**）。
- 四類誤導源的定位與重構：`MISLEADING-NAME` / `UNSOURCED-HARD-CLAIM` / `AMBIGUOUS` / `OVERTRUST-CLAIM`。
- 硬知識 UNIT 化 + SPEC-REF 補齊（電氣值/DRC/標準符規/時序引 datasheet/IPC/JEDEC/IEEE 章節）。
- 至少 1 個範本 skill 走完整 Engineer Mode eval loop（量化 with-skill vs baseline）。
- 具體 IN 目標清單（稽核 2026-07-05 定位，18 筆誤導源，高度集中於 2 份 rule-base）：
  - **P0 學位（pilot）**：`references/pcb-layout-rules-compendium.md`—8/18 筆源於此，含全 repo 唯一「與已訂正主源直接數值衝突」（#1 HV 間距 0.005 vs 0.0025 mm/V，差 2 倍）。純硬知識表，重構收益最大。
  - **P1 契約缺口**：`engines/kicad/references/datasheet-verification.md`（#9 負電壓不查、#10 缺欄語意）——直接對應使用者案例 3「讀不完整輸出判整批」。
  - **P1 命名誤導**：`stages/c04-layout/GUIDE.md` + `references/kicad-interactive-layout.md`（#6,7 「mirror」命名）——直接對應案例 2「假 drift」。
  - **P2 啟發式當精確**：`engines/kicad/scripts/README.md`（#11 Vref 猜值、#12 12mm 吸附）。
  - **P2 前提條件不齊**：`stages/c02-me/references/mechanical-design-advisory.md`（#18 FDM 幾何值）。
  - 完整 18 筆清單見 `design.md` 附錄。

### OUT

- opencode 的 SYSTEM.md / AGENTS.md / driver prompts（使用者選 bodesign skills 優先；治理文件另立 plan）。
- `skills/bodesign/scripts/*.py`、`engines/*/scripts/*.py` 等**程式碼**重構（本 plan 只碰 skill 的 md 知識文字；程式碼命名缺陷若發現，記 issue 另處理，不在本 plan 動）。
- bodesign-kb skill（獨立 skill，非 C00-C07 workflow 腦）。
- 為改而改的純文字潤飾——**指認不出具體誤導的語句不動**。

## Non-Goals

- 不追求「改完所有 62 檔」。目標是把**高誤導密度**的部分改到位 + 建立可複製的 pattern，不是地毯式重寫。
- 不改變 skill 的功能語義/workflow 結構——只**消除誤導**、**補 SPEC-REF**，不重設計 C00-C07 流程。
- 不新增 fallback、不動天条（no-silent-fallback / no-fabrication / datasheet-grounded）。

## Constraints

- **驗收尺（硬性）**：每一處重構都要能指認「原本會誘導 agent 做出什麼錯誤推論」。指認不出誤導 → 不動（防為改而改）。
- **SPEC-REF gate（Engineer Mode）**：硬知識 UNIT 的每個事實斷言必須指向權威源（公開標準 or 內部 datasheet/design doc/量測報告）。裸數值 = drafting defect。
- **Override clause 適用**：僅對「可驗證契約」允許 rigid FORBID/INVARIANT/require；rationale/背景仍走 why-first 散文。rigidity 的合法性檢測 = 有沒有 SPEC-REF。
- 不 graduate（`/plans/→/specs/`）除非使用者明示。

## What Changes

- bodesign skills 中被指認的誤導語句 → 重寫為無歧義 / UNIT 化 / 補 SPEC-REF。
- 至少 1 份 skill 升級為 Engineer Mode 範本，帶 eval 佐證。
- 新增可重用「反誤導寫作規範」知識（KB failure-mode / control）。

## Capabilities

### New Capabilities

- bodesign skills 誤導源清單（可追溯 檔:行）：讓後續維護有 SSOT。
- Engineer Mode 範本 skill：可被其餘 skill 仿寫的工程等級樣板。

### Modified Capabilities

- 高誤導密度 skill：從「散文式易誤讀」→「UNIT 化 + SPEC-REF 可驗證」，降低 agent 誤判率（eval 佐證）。

## Impact

- 受影響：`skills/bodesign/**`（md 知識文字）、下游任何載入這些 skill 的 C00-C07 workflow agent。
- 不影響：程式碼路徑、MCP 工具行為、容器 runtime（本 plan 純知識文字層）。
- 需同步：若重構觸及架構級知識邊界，收尾同步 `specs/architecture.md`。
