# Proposal: design-ir_net-role-extension

## Why

- `quality_verify-checker-skillification`（verified）的盡職查核（event 2026-07-04
  `t-b-12-stub-ir-native-land-backlog`）證實：6-7 個 verified `control.*` 的判斷力清楚，
  卻無法技能化成確定性 checker，唯一 blocker 是 **design IR 的 `Net` dataclass 沒有 role 欄**——
  分不出哪條 net 是 power / ground / RF / high-current。
- 這些 control 全屬 placement/拓樸類，門檻語義都要先知道 net 角色才能判（如「high-current
  via 要接 ground plane」「RF trace 旁要有 ground」「charger IC 的 power/ground 拓樸」）。
- 目前唯一「解法」是靠 net 名 heuristic（VBUS/GND…）猜 role，但這**直接違反 no-fabrication
  天條**（bodesign AGENTS.md §2.1）——臆造沒有 datasheet/schematic 依據的分類。正解是讓
  role 由上游 schematic net-class **明確供給**，成為 IR 的一等公民欄位。

## Original Requirement Wording (Baseline)

- 使用者 2026-07-04：「把未來的兩個 plan 先寫起來」——其一為 verify-checker T-B backlog 盡職查核
  指出的 `Net.role` IR 擴充上游工（解鎖 6-7 個 placement 類 T-B control）。

## Requirement Revision History

- 2026-07-04: initial draft created via plan-init.ts
- 2026-07-04: proposal 填實（backlog 佔位，需求/範圍定案；designed 待未來啟動）

## Effective Requirement Description

1. 在 `packages/design-ir/bodesign_design_ir/contracts.py` 的 `Net` dataclass 新增
   **明確、可選、datasheet/schematic-grounded 的 `role` 欄位**（如 `power` / `ground` /
   `high_current` / `rf` / `signal` / `differential` 的閉集 enum），role 由上游 schematic
   net-class / 使用者標註**明確供給**，缺失時為 `None`（不猜）。
2. role 必須帶 provenance（來源 evidence_ref），呼應 `ValidationEvidence` 的
   `source_anchor` 契約——checker 讀 role 時可回溯它從哪來。
3. 提供 role-aware 的讀取介面，讓 verify-checker 的 placement 類 checker 能以 role 篩選
   net（而非 net 名 heuristic），解鎖對應的 T-B control。

## Scope

### IN
- `Net` dataclass 加 `role`（閉集 enum）+ role provenance 欄位。
- role 的閉集定義 + 缺失 = `None`（fail-fast，不預設、不猜）語義。
- 上游供給路徑：schematic net-class → IR role 的明確映射（來源必為 schematic/使用者標註）。
- 解鎖並 land 這批 T-B control（依實測，語義夠純者）：
  `ddr.ddr3-flyby-routing`、`protection.tvs-esd-layout`、`protection.reverse-polarity-layout`、
  `placement.power-stage-hot-loop`、`power.charger-ic-layout`、`power.current-sense-layout`、
  `power.high-current-via-ground`、`rf.transmission-line-ground`。
- 對應 checker 在 `verify-checker-skillification` spec 以 `extend`/`amend` 掛入 registry。

### OUT
- **不做 net 名 heuristic 猜 role**（天條禁止；role 必須明確供給）。
- 不做 copper 幾何解析（那是 `gerber-core_copper-geometry-parser` plan 的範圍）。
- 不改寫既有 `Net.constraints` / `connected_pads` 語義（只加欄，向後相容）。
- 不在本 plan 補齊全部 12 個 T-B（copper 幾何類與需設計意圖類另計）。

## Non-Goals

- 不建立平行的 net 分類系統；role 是 `Net` 的一等欄位，單一真相。
- 不讓 LLM 參與 role 判定（role 來自 schematic net-class 的確定性映射或使用者明確標註）。

## Constraints

- **No silent fallback / No fabrication**（bodesign 天條）：role 缺失 → `None` + fail-fast，
  絕不預設或猜測。
- 向後相容：現有 `Net` 呼叫端不受影響（role 為 optional，default `None`）。
- role 值必帶 provenance（evidence_ref），對齊 datasheet-grounded / source_anchor 契約。
- 落點在 core（`design-ir` package），純 python，不引入 worker-only 依賴。

## What Changes

- `design-ir` `Net` schema + role provenance。
- `verify-checker-skillification` registry：對應 T-B binding 由 stub → landed（跨 spec，
  以 extend 模式）。
- `specs/architecture.md`：IR schema 演進 + Verification Baseline 解鎖數更新。

## Capabilities

### New Capabilities
- `Net.role`（閉集 enum + provenance）：net 角色成為 IR 一等公民，checker 可 role-aware 篩選。
- role-aware net 查詢介面：placement 類 checker 的 role 過濾基礎。

### Modified Capabilities
- verify-checker registry：6-7 個 placement T-B binding 從 stub → landed T-A。

## Impact

- `packages/design-ir/bodesign_design_ir/contracts.py`（`Net` dataclass）。
- 上游 IR 生成路徑（schematic net-class → role 映射）。
- `packages/workflow-core/.../checkers/`（placement checker 改讀 role）+ registry。
- `specs/architecture.md`、`quality_verify-checker-skillification` spec（extend）。
- Traceability：本 plan 是 `quality_verify-checker-skillification` DD-7 揭示的兩筆上游工之一。
