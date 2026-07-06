# BR_20260706 — 四個新落地 verb 未寫進 SKILL.md / stage GUIDE 工作流：能力落地、文件滯後，照 GUIDE 走的 agent 會漏用

- **類型**：workflow / documentation drift
- **發起端**：aiguard 消費端 session（thesmart_products/03.aiguard）
- **日期**：2026-07-06
- **嚴重度**：Medium-High（不擋 code，但擋「照文件走」的 agent 正確使用新能力——正是 EPIC 翻轉要服務的對象）
- **關聯**：`BR_20260704_EPIC_capability_inversion_refs_derived_design.md`（切面 1/2/3/5 的 verb 已落地）、`HANDOVER_20260705_aiguard_c04_blocked_on_bodesign_generation_verbs.md`

---

## 現象（含硬證據）

`capability/refs-derived-design` 已 graduated（tasks 18/18 全勾），四個新 verb 已進 `gate.py` LANDED_VERBS（verb 數 52→56）：

- `refs_ingest`（切面 1：掃 `01_refs/` SSOT 出 manifest）
- `c04_face_placement`（切面 2：連接器綁 C01 凍結面，DD-4）
- `c04_castellation`（切面 3：segfault-free S-expr 半孔注入，DD-5）
- `c04_dod_traceback`（切面 5：DoD 從存在性升級為 SSOT 回溯）

但在**工作流文件層**零記載：

```
grep -rln "refs_ingest|c04_face_placement|c04_castellation|c04_dod_traceback" \
  skills/bodesign/SKILL.md skills/bodesign/stages/
→ 0 命中（2026-07-06 實測）
```

對照組：同批落地的 `route_net2pcb strategy="deterministic"` **有**寫進 c04 GUIDE SOP step 3；c01/c02 GUIDE 的 refs-first gate 段也隨 commit `c790e8b` 同步更新了。獨漏這四個 verb。

## RCA

三個 plan（refs-derived-design / deterministic-preplacement / refs-first-emitters）的文件同步只覆蓋了「該 plan 直接改到的 GUIDE 段落」，沒有一個收尾步驟是「新 LANDED_VERBS 必須反映到 SKILL.md verb 清單 + 對應 stage GUIDE 的 SOP/Gate 段」。verb 註冊（gate.py）與 verb 教學（SKILL/GUIDE）之間沒有同步 gate。

## 影響範圍

1. **`refs_ingest` 無入口**：沒有任何 GUIDE 教「開工先掃 `01_refs/`」。refs gate 掛在 C00~C04 全部 emit verb 前置（task 1.3），但 C00/C03 GUIDE 完全沒有 refs-first 段——agent 會在 emit 時才撞 `REFS_SSOT_MISSING`，而不是照 SOP 前置準備。
2. **C04 GUIDE 無 castellated/stamp-module 工作流**（`stamp|castellat` 關鍵字 = 0）：三件式核心板（aiguard 核心形態、EPIC 驗收案例）在 C04 SOP 裡沒有對應步驟，`c04_castellation` 是孤兒 verb。
3. **`c04_face_placement` 不在 SOP step 3 前置**：GUIDE 只教 `route_net2pcb` 的 placement 參數，沒教「先跑 face_placement 把連接器綁定 C01 凍結面、其輸出餵 `placement=` map」這條鏈（正是 review F4/F7 修的 pinned 餵入路徑）。
4. **`c04_dod_traceback` 不在 Gate/done-criteria 段**：切面 5 的核心檢查不會被照 GUIDE 走的 agent 觸發，DoD 實務上退回存在性檢查。

## 建議修復

1. **SKILL.md**：verb 對照表補這 4 個 verb（含一句話用途 + 所屬切面）。
2. **c04-layout GUIDE**：
   - SOP step 3 前插「3a. Face placement」：`c04_face_placement`（輸入 C01 face_layout，輸出綁定凍結面的 placement bands）→ `placement_to_coords` → 餵 `route_net2pcb(placement=...)`。
   - 新增「stamp-module / castellated 板」小節：`c04_castellation`（spec + board_outline → S-expr 注入），標明拒絕 pcbnew mutation 路徑的理由（DD-5）。
   - Gate 段加 `c04_dod_traceback`：untraceable / unfulfilled 任一非空 → blocking。
3. **c00-prd / c03-ee GUIDE**：加 refs-first 前置段（如 c01/c02 已有的），教 `refs_ingest` 為 SOP 第 0 步。
4. **制度性防再犯**：LANDED_VERBS 變更的 PR/commit checklist 加一條「SKILL.md verb 表 + 對應 stage GUIDE 已同步」；或加一個 lint（gate.py verb 清單 diff SKILL.md 記載）。

## 驗證手段

- `grep -c` 四個 verb 名於 SKILL.md 與對應 GUIDE ≥ 1。
- 冷啟 agent 只讀 c04 GUIDE 照 SOP 走 aiguard 三件式案例，能自然走到 `refs_ingest → c04_face_placement → c04_castellation → route_net2pcb(deterministic) → c04_dod_traceback + layout_drc_gate` 全鏈，不需口頭補課。

## Resolution（2026-07-06）

四項建議修復全部落地：

1. **SKILL.md**：C04 stage 家族行補 `c04_face_placement` / `c04_castellation` / `c04_dod_traceback`，files/orchestration 行補 `refs_ingest`，並新增「Refs-derived design verbs」對照表（verb + 切面 + 一句話用途）。
2. **c04-layout GUIDE**：
   - 新增 SOP step 0「Ingest the refs SSOT first」（`refs_ingest` 為前置，anchor 供 face_placement/castellation/dod_traceback 回溯）。
   - Step-by-step 插入 step 1「Bind connectors to their frozen faces first」：`c04_face_placement` → `placement_to_coords` → `route_net2pcb(placement=...)` 全鏈（含 DD-4、天條 2 fail-fast 語義），原步驟順延。
   - 新增「3b. Stamp-module / castellated boards」小節：spec/board_outline/輸出契約 + DD-5 拒絕 pcbnew mutation 理由（引 BR_20260704_pcbnew_scripting_segfault_hazards）+ 跨界 net 紀律。
   - Gate 段 HARD FAIL 清單加 `c04_dod_traceback`（untraceable/unfulfilled 任一非空 → blocking）。
   - Tools 段granular 工具鏈同步補齊。
3. **c00-prd / c03-ee GUIDE**：各加 SOP step 0 refs-first 前置段（`refs_ingest`；c00 講 authority-rank 引用 + 下游 emitter refs gate；c03 講 provenance anchor `<ssot_file>:<locator>` 供 C04 traceback）。
4. **制度性防再犯**：新增 `tests/test_skill_verb_sync.py` — 自動 lint：gate.py LANDED_VERBS 每個 verb 必須出現在 SKILL.md / stage GUIDEs / references 至少一次；既有 17 個 legacy 未記載 verb 進顯式 burn-down allowlist（加新 verb 進 allowlist = 缺陷；文件化後必須從 allowlist 移除，第二條 test 強制）。2 tests pass。

驗證：四 verb grep 矩陣全達標（SKILL ≥2；c04 GUIDE 各 ≥1；c00/c03 GUIDE `refs_ingest` ≥1；c04 GUIDE `stamp|castellat` 關鍵字 9 命中）；`python3 -m unittest tests.test_skill_verb_sync` OK。

## 消費端脈絡（為什麼現在報）

aiguard 端即將「從 C00 用新能力重走到 C04」（refs-derived 全鏈第一次實跑）。本輪會以顯式指定 verb 鏈繞過文件缺口，但這不可持續——下一個照 GUIDE 走的 agent 仍會漏用。
