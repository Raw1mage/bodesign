# BR — bodesign DoD gate：`dod_status.json` honest-deferral 覆寫檔的位置隱性敏感、放錯位置被靜默忽略

- **Date**: 2026-07-03
- **Repo**: bodesign (workflow-core / guide_dod / stage GUIDEs)
- **Severity**: medium（honest-deferral 機制正確但難用；三個獨立行動者都先放錯位置）
- **Scope**: `assess_guide_dod` / `package_readiness` roll-up / `dod_status.json` 契約 / stage GUIDE 文件

## 現象（含硬證據）

`dod_status.json`（記錄 honest 延遲交付物：`pending` / `not-run` / `blocked` + reason）的**放置位置隱性敏感**：`package_readiness` roll-up 對每個 stage 都以 **product-root（`03.aiguard/`）為 base** 求值（manifest `base: project-root`），因此覆寫檔只從 **`03.aiguard/dod_status.json`** 讀、以 **deliverable id 為 key**；放在 stage 子資料夾（`C0x-*/dod_status.json`）會被**靜默忽略**、無任何 warning。

三個獨立行動者本次都先踩坑：

1. **C06 subagent**（ses_0d7c1fe21）：先把檔寫在 `C06-Verification/dod_status.json` → gate 不認、cross_check 仍 missing；自行查出「gate reads from product root」後 move 到 `03.aiguard/dod_status.json` 才生效。硬證據（其 result）：
   > "gate reads `dod_status.json` from the **product root** (`03.aiguard/dod_status.json`), not the stage dir — initial placement under `C06-Verification/` did not register; moved to root."
2. **C04 subagent**（ses_0d7b804c6）：獨立再次確認同一機制，且指出 C06 之所以早先「碰巧成功」是因為它剛好寫在 root。硬證據：
   > "the `package_readiness` roll-up evaluates **every** stage against the **repo-root base**, so it reads `dod_status.json` **only from `03.aiguard/` root**, keyed by deliverable id — **NOT** from stage subfolders (`C0x-*/dod_status.json` is silently ignored)."
3. **Orchestrator（我）**：誤在 `C04-Layout/dod_status.json` 重寫一份 → 無效 clutter，事後刪除。

## RCA

- `assess_guide_dod(base, stage)` 對 roll-up 傳入的 `base` 是 product-root，`dod_status.json` 從 `base/dod_status.json` 讀，key = deliverable id。這在**單一全域覆寫檔**設計下是自洽的，但：
  - **直覺衝突**：交付物是 stage-local（`C04-Layout/...`），人與 subagent 的第一直覺都是把 stage 的 honest-status 放在 stage 夾裡。
  - **失敗模式是靜默**：放錯位置不報錯、不 warn，deliverable 仍顯示 `missing`，看不出「你其實寫了、只是位置錯」。debug 成本全轉嫁給行動者逐一試錯。
  - **文件缺口**：各 stage `GUIDE.md` 都提到 `dod_status.json`，但（依本次三方踩坑推斷）未明確載明「必須放 product-root、以 deliverable id 為 key、stage 夾副本無效」。

## 建議修復

1. **gate 主動 warn 放錯位置**：`assess_guide_dod` 掃到任何 `C0x-*/dod_status.json`（stage 子夾）時，emit 一條 warning：「found stage-scoped dod_status.json at <path>; roll-up only honors <product-root>/dod_status.json (id-keyed) — this file is ignored」。把靜默失敗變成響亮提示。
2. **GUIDE.md 明載契約**：在每個 stage GUIDE 的 honest-deferral 段落寫清楚：覆寫檔路徑 = product-root、schema = `{ "<deliverable_id>": {status, reason, owner} }`、status 需 ∈ 該 deliverable 的 `honest_states`、stage 夾副本無效。
3.（optional）**接受 stage-scoped 覆寫並 merge**：若產品傾向 stage-local 檔案佈局，可讓 gate 同時讀 stage 夾副本並 merge 進 root 視圖（但需定義衝突優先序）；比 (1)(2) 重，非必須。

## 影響範圍

- 任何用 honest-deferral 誠實延遲交付物的 stage（C04 routed/fab pending、C06 cross_check not-run 等）都會踩；每個 stage 首次都要重新試錯位置。
- 對 subagent 委派尤其貴：每個 cold-context subagent 都獨立重踩、燒 round 才查出機制。

## 驗證手段

- 重現：把有效 `dod_status.json` 放 `C0x-*/` stage 夾、跑 `gate.py package_readiness`，觀察 deliverable 仍 `missing` 且無 warning。
- 修復後：(1) 同場景應出現「stage-scoped dod_status.json ignored」warning；(2) `grep -n dod_status stages/*/GUIDE.md` 應載明 product-root + id-keyed schema。
- 回歸：product-root 的 `dod_status.json`（id-keyed、status ∈ honest_states）仍正確被認、deliverable → `honest-status`、`dod_ok=true`。
