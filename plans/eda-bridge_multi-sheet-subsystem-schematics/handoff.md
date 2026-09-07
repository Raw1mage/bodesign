# Handoff: eda-bridge_multi-sheet-subsystem-schematics

## Execution Contract

實作者必須交付：**1 root + N 葉的 hierarchical schematic 產出能力**，且

1. **Phase 1（跨檔連通驗證）先做完才動其餘 Phase。** 整包其餘工作都預設「同名 global_label
   跨檔連得起來」，而這件事從未被測過。若 Phase 1 不成立，(a)(b)(d) 全部白做。
2. **N=1 必須 byte-stable**（`WIRE_GEOM_SHA` 與 HEAD 逐字相同）。否則舊包 30 輪的量測基線全部作廢。
3. **每個交付的讀數帶母體宣告**：哪個構法、政策 ON/OFF、分紙或整圖。母體不同的數字不可互比。

**Done 的定義**：`spec.md` §Acceptance Checks 六格 AC-1..AC-6 全綠，且 AC-4 的
treatment 與 control **兩格都做**（只做 treatment 不算）。

## Required Reads

- 本包 `proposal.md`（射程與使用者裁示逐字）、`design.md`（K1–K11 已知數與母體）、
  `errors.md`（Outcome Codomain：每個狀態的排放點）
- 舊包 `plans/eda-bridge_draftsman-series-divider-wireable/errors.md` —— 特別是
  **⑤（同一政策有兩份實作，pass-through 控制組結構性無效）** 與
  **⑦（instrument 分支，不是 instrument 結果）**。tasks 5.2 與 5.4 直接依賴這兩則。
- `AGENTS.md` §5（讀 `Ran N tests` 的 N，不讀 rc）、§6.1（共用工作樹紀律）、§6.3（stale pyc）
- `specs/architecture.md`（C03 模組邊界，收尾要同步）

## Stop Gates In Force

- **Q1（`group` 語意 C-1 vs C-2）待使用者裁決。** tasks 2.1 之前不得選定，
  也不得以「先做 C-1 之後再改」繞過——C-1 是破壞性變更（K11：33 筆中 21 筆是佈局佔位標籤）。
- **`M6-8d` 是使用者裁示，不得自行修改。** (e) 的射程已縮小為「判定範圍降到 sheet 層級」，
  **不含放寬政策**（K8：放寬後多 sheet 交叉數仍達單張紙的 80%）。
- **A1 三選項（維持現況／關閉豁免／復活 A1）代價未量完**，屬舊包範圍，本包不處理（Q4）。
- 送廠輸出前需確定性驗證 + 使用者明確批准（repo 天條 §2.3）——本包不觸及該路徑。

## Execution-Ready Checklist

- [ ] Q1 已由使用者裁決，`data-schema.json` 的 `open_decision.status` 已從 `awaiting-user-ruling` 更新
- [ ] `kicad-cli` 在執行環境可用（不可用時跨檔連通性只能記 `indeterminate`，不得記 `ok`）
- [ ] 已讀舊包 `errors.md` ⑤ 與 ⑦，理解 tasks 5.2 為何要求「兩處實作都改」
- [ ] 已確認工作樹狀態並依 `AGENTS.md` §6.1 錨定自己的工作（本樹長期有多顆 session 並行、大量未 commit）
