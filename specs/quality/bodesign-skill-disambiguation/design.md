# Design: quality_bodesign-skill-disambiguation

## Context

bodesign 的 `skills/` 是 C00-C07 硬體設計 workflow 的「腦」——62 個 md、~17751 行，裝的是 KiCad 規則、電氣數值、DRC、標準符規、時序預算等**可驗證硬知識**。這些 skill 以散文寫成，容易出現三種讓 agent 誤判的文字缺陷：模棱兩可用語、誤導命名、裸數值（無 SPEC-REF）。最近 BR_20260705 三修全部佐證此模式。同時 `skill-creator` 剛升級出 Engineer Mode，提供「可驗證硬知識 → UNIT shell + SPEC-REF」的工程等級規格，正好是這批 skill 的目標標準。

## Goals / Non-Goals

**Goals**

- 定位 bodesign skills 的誤導源（可追溯 檔:行），產出清單 SSOT。
- 用 Engineer Mode 重構高誤導密度 skill，量化驗證降低誤判。
- 沉澱可複製的反誤導寫作 pattern。

**Non-Goals**

- 不地毯式重寫 62 檔；只改高誤導密度部分 + 建 pattern。
- 不改 C00-C07 功能語義/workflow 結構。
- 不動程式碼（.py），只碰 md 知識文字。
- 不新增 fallback、不動天条。

## Decisions

- **DD-1: 範圍限 bodesign/skills 的 md，排除 opencode 治理文件與程式碼。** 使用者明示先攻 bodesign skills；治理文件（SYSTEM.md/AGENTS.md/drivers）影響面更大但另立 plan，避免單 plan 跨太多語料庫失焦。程式碼命名缺陷（如 vault 的 `explicit_path`）已在 BR_20260705 修過，本 plan 不重複碰程式碼。

- **DD-2: 採 Engineer Mode 為目標品質標準，而非自訂尺。** skill-creator 昨日升級的 Engineer Mode 已是「工程等級 skill」的權威定義（UNIT shell + 六 core + SPEC-REF gate + assertion 化 eval）。重用它，不另造輪子。

- **DD-3: 驗收尺 = 「可指認誤導」+ SPEC-REF gate（雙門檻）。** (a) 每處重構須能指認「原本會誘導 agent 做出什麼錯誤推論」——指認不出就不動（防為改而改，對齊使用者「不是每個失誤都有文字修法，但每次都要去找」的紀律）。(b) 硬知識 UNIT 的事實斷言須有 SPEC-REF——裸數值 = drafting defect。

- **DD-4: Engineer Mode 的 Override clause 僅對「可驗證契約」啟用 rigid FORBID/INVARIANT。** rationale/背景仍走 why-first 散文。rigidity 合法性檢測 = 有無 SPEC-REF。避免把 skill 改成「musty MUST」堆疊。

- **DD-5: 先 pilot 一份範本並跑 eval loop，再推廣。** 對齊 skill-creator 的迭代邏輯：先證明範本真的降低誤判（with-skill vs baseline），再複製 pattern。不一次改全部。

- **DD-6: 稽核用 subagent，結論型唯讀掃描。** 62 檔掃描屬純結論工作，丟 subagent 只回清單，最省 orchestrator context。

## Risks / Trade-offs

- **過度形式化風險** — 把 rationale 也 UNIT 化會讓 skill 更長更差。緩解：DD-4 明確劃線，只 formalize 可驗證契約。
- **SPEC-REF 補不齊** — 部分裸數值可能查不到權威源（skill 作者當初憑經驗寫）。緩解：查不到就標記為待補 + 記 issue，不臆造來源（no-fabrication 天条）。
- **pilot 選錯範本** — 選了低流量/低誤導密度的 skill，pattern 不具代表性。緩解：由稽核 subagent 依「高流量+高誤導密度+硬知識為主」推薦，使用者拍板。
- **eval 難以量化 skill 文字改善** — 誤導降低較難用單一 assertion 測。緩解：Engineer Mode 的 assertion 化 DONE-WHEN + 針對「agent 是否讀對契約」設計 eval 任務。

## Critical Files

- `skills/bodesign/SKILL.md` — C00-C07 workflow 總腦，最高流量。
- `skills/bodesign/stages/c0X-*/GUIDE.md` — 7 個 stage guide，各 stage agent 入口。
- `skills/bodesign/engines/kicad/**` — 硬知識大宗（DRC/gerber/schematic/standards），SPEC-REF gate 主戰場。
- `plans/quality_bodesign-skill-disambiguation/tasks.md` — 待稽核回報後填具體目標。

## Appendix: 誤導源稽核清單（2026-07-05，18 筆）

稽核背景判定：全語料 505 筆 `should/must/always/never` 命中，逾九成是**刻意的 honesty-model 契約語**（非誤導）；`standards-compliance.md` 是 SPEC-REF 模範（VERIFIED + 頁碼錨點）。真正誤導源高度集中於 2 份 rule-base。

| # | 檔案:行號 | 類型 | 會誤導出什麼錯誤推論 |
|---|---|---|---|
| 1 | pcb-layout-rules-compendium.md:74 | UNSOURCED-HARD-CLAIM | HV 間距 `0.005 mm/V` vs 主源已訂正 `0.0025/V`，差 2 倍 → 間距算錯一半 |
| 2 | pcb-layout-rules-compendium.md:55 | UNSOURCED-HARD-CLAIM | `1A/20mil` 掛 IPC-2152 名實為 2221 粗記法 → 當正式值定電流線寬 |
| 3 | pcb-layout-rules-compendium.md:39 | UNSOURCED-HARD-CLAIM | 熱過孔 `1 via/100mW` 裸經驗值當可驗證規格寫進 DRC |
| 4 | pcb-layout-rules-compendium.md:89 | UNSOURCED-HARD-CLAIM | FR-4 傳播延遲 `150-180 ps/in` 當定值，忽略疊構相依 |
| 5 | standards-compliance.md:64 | UNSOURCED-HARD-CLAIM | 7351B courtyard 值 secondary source，compendium:43 當已核實重述 |
| 6 | c04-layout/GUIDE.md:95 | MISLEADING-NAME | 「mirror」暗示與 MCP 1:1，實為獨立副本可漂移（案例2 型） |
| 7 | kicad-interactive-layout.md:73 | MISLEADING-NAME | 「manual mirror」暗示與 net2pcb 等價，無漂移警語 |
| 8 | pcb-layout-rules-compendium.md:141 | OVERTRUST-CLAIM | soldermask `1:1` 無失效邊界，pre-2025/非LDI 非 1:1 |
| 9 | datasheet-verification.md:305 | OVERTRUST-CLAIM | 不查負電壓，verify PASS 誤判負電壓 pin 已驗（案例3 型） |
| 10 | datasheet-verification.md:19 | AMBIGUOUS | datasheet 缺欄位時 pass/unknown 未界定 |
| 11 | scripts/README.md:385 | UNSOURCED-HARD-CLAIM | Vref 猜值清單推 Vout，當實值；清單外調節器全錯 |
| 12 | scripts/README.md:360 | MISLEADING-NAME | 「pin-net mapping」暗示精確，實為 12mm 吸附啟發式 |
| 13 | methodology_schematic.md:862 | OVERTRUST-CLAIM | 「1053板未觀察」暗示零誤併，忽略密板風險 |
| 14 | manual-schematic-parsing.md:3 | AMBIGUOUS/OVERTRUST | 「always works if valid」未界定 valid |
| 15 | report-manufacturing.md:60 | AMBIGUOUS | 預設 1.6mm/1oz/Class2 用 should 未強制，恐當實測值送廠（案例1 型） |
| 16 | report-manufacturing.md:16 | MISLEADING-NAME | 「Skipped when: never」語意反轉易誤讀為「從不觸發」 |
| 17 | pcb-layout-rules-compendium.md:106 | UNSOURCED-HARD-CLAIM | PDN 範例 `5mΩ` 當某實 rail 定值抄用 |
| 18 | mechanical-design-advisory.md:63 | UNSOURCED-HARD-CLAIM | FDM 硬幾何值 `1.2mm` 前提條件（@0.4 nozzle）未逐列標 |

類型統計：UNSOURCED-HARD-CLAIM 8 / MISLEADING-NAME 4 / OVERTRUST-CLAIM 4 / AMBIGUOUS 3（部分重疊）。

Pilot 推薦：`pcb-layout-rules-compendium.md`（8/18 源於此、含唯一與主源數值衝突、純硬知識表、同 repo `standards-compliance.md` 已示範理想 SPEC-REF 形態可對照）。
